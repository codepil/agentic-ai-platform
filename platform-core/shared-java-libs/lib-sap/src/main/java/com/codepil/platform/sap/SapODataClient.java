package com.codepil.platform.sap;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.Base64;
import java.util.List;
import java.util.Map;

/**
 * Generic OData v4 client for SAP Integration Suite / SAP Gateway.
 *
 * <p>Provides a simple, reusable interface for the two most common OData operations:
 * reading entity collections and creating new entities. All calls are made via Spring's
 * {@link WebClient} and are non-blocking (Mono/Flux).</p>
 *
 * <h3>Authentication</h3>
 * <p>Uses OAuth2 client credentials flow to obtain a bearer token from the SAP Gateway
 * token endpoint before each set of calls. Tokens are not cached in this implementation —
 * add a token cache (e.g. Caffeine) if call volume justifies it.</p>
 *
 * <h3>Retry policy</h3>
 * <p>All calls retry up to 3 times with exponential backoff (1s, 2s, 4s) on transient
 * errors (5xx responses, connection timeouts). 4xx errors (Bad Request, Not Found,
 * Forbidden) are not retried.</p>
 *
 * <h3>Usage in generated product services</h3>
 * <pre>
 * {@literal @}Service
 * public class ProductService {
 *     private final SapODataClient sapODataClient;
 *
 *     public ProductResponse getProductFromSap(String materialId) {
 *         List&lt;Map&lt;String, Object&gt;&gt; results = sapODataClient.getEntities(
 *             "API_PRODUCT_SRV",
 *             "A_Product",
 *             Map.of("$filter", "Product eq '" + materialId + "'",
 *                    "$select", "Product,ProductType,BaseUnit")
 *         ).block();
 *         // map to ProductResponse...
 *     }
 * }
 * </pre>
 */
@Component
public class SapODataClient {

    private static final Logger log = LoggerFactory.getLogger(SapODataClient.class);

    private static final int MAX_RETRIES = 3;
    private static final Duration RETRY_BASE_DELAY = Duration.ofSeconds(1);

    private final SapClientProperties properties;
    private final WebClient webClient;

    public SapODataClient(SapClientProperties properties) {
        this.properties = properties;
        this.webClient = WebClient.builder()
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .codecs(codecs -> codecs.defaultCodecs().maxInMemorySize(8 * 1024 * 1024))
                .build();
    }

    /**
     * Fetch a list of OData entities from a SAP service.
     *
     * <p>Constructs the OData URL as:
     * {@code {gatewayUrl}/{serviceName}/{entitySet}?{queryParams}}</p>
     *
     * @param serviceName the SAP OData service name (e.g. {@code API_PRODUCT_SRV})
     * @param entitySet   the OData entity set name (e.g. {@code A_Product})
     * @param queryParams OData query options map (e.g. {@code $filter}, {@code $select}, {@code $top})
     * @return a {@link Mono} emitting the list of entity maps from the {@code value} array
     */
    @SuppressWarnings("unchecked")
    public Mono<List<Map<String, Object>>> getEntities(String serviceName,
                                                       String entitySet,
                                                       Map<String, String> queryParams) {
        String uri = buildUri(serviceName, entitySet, queryParams);
        log.info("SAP OData GET serviceName={} entitySet={}", serviceName, entitySet);

        return webClient.get()
                .uri(uri)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + obtainAccessToken())
                .retrieve()
                .bodyToMono(Map.class)
                .map(response -> {
                    Object value = response.get("value");
                    if (value instanceof List<?> list) {
                        return (List<Map<String, Object>>) list;
                    }
                    return List.<Map<String, Object>>of();
                })
                .retryWhen(Retry.backoff(MAX_RETRIES, RETRY_BASE_DELAY)
                        .filter(this::isRetryable)
                        .doBeforeRetry(signal ->
                            log.warn("Retrying SAP OData GET serviceName={} attempt={}",
                                     serviceName, signal.totalRetries() + 1)))
                .doOnError(e -> log.error("SAP OData GET failed serviceName={} entitySet={}",
                                          serviceName, entitySet, e));
    }

    /**
     * Create a new OData entity in a SAP service.
     *
     * <p>Constructs the OData URL as {@code {gatewayUrl}/{serviceName}/{entitySet}}
     * and POSTs the body as JSON.</p>
     *
     * @param serviceName the SAP OData service name
     * @param entitySet   the OData entity set name
     * @param body        the entity fields as a map — serialised to JSON in the request body
     * @return a {@link Mono} emitting the created entity map returned by SAP
     */
    @SuppressWarnings("unchecked")
    public Mono<Map<String, Object>> createEntity(String serviceName,
                                                  String entitySet,
                                                  Map<String, Object> body) {
        String uri = buildUri(serviceName, entitySet, Map.of());
        log.info("SAP OData POST serviceName={} entitySet={}", serviceName, entitySet);

        return webClient.post()
                .uri(uri)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + obtainAccessToken())
                .bodyValue(body)
                .retrieve()
                .bodyToMono(Map.class)
                .map(response -> (Map<String, Object>) response)
                .retryWhen(Retry.backoff(MAX_RETRIES, RETRY_BASE_DELAY)
                        .filter(this::isRetryable)
                        .doBeforeRetry(signal ->
                            log.warn("Retrying SAP OData POST serviceName={} attempt={}",
                                     serviceName, signal.totalRetries() + 1)))
                .doOnError(e -> log.error("SAP OData POST failed serviceName={} entitySet={}",
                                          serviceName, entitySet, e));
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Build the full OData URI with query parameters.
     *
     * @param serviceName the OData service name
     * @param entitySet   the entity set name
     * @param queryParams optional OData query parameters
     * @return the full URI string
     */
    private String buildUri(String serviceName, String entitySet,
                            Map<String, String> queryParams) {
        StringBuilder sb = new StringBuilder();
        sb.append(properties.getGatewayUrl())
          .append("/").append(serviceName)
          .append("/").append(entitySet);

        if (!queryParams.isEmpty()) {
            sb.append("?");
            queryParams.forEach((k, v) -> sb.append(k).append("=").append(v).append("&"));
            // Remove trailing &
            sb.deleteCharAt(sb.length() - 1);
        }
        return sb.toString();
    }

    /**
     * Obtain an OAuth2 access token from the SAP Gateway token endpoint using client credentials.
     *
     * <p>This is a synchronous blocking call — acceptable here because token acquisition
     * is infrequent and the token should be cached in production usage.</p>
     *
     * @return the bearer access token string
     */
    @SuppressWarnings("unchecked")
    private String obtainAccessToken() {
        if (properties.getOauthTokenUrl() == null || properties.getOauthTokenUrl().isBlank()) {
            log.warn("SAP OAuth token URL not configured — using empty token");
            return "";
        }

        String credentials = properties.getClientId() + ":" + properties.getClientSecret();
        String encoded = Base64.getEncoder().encodeToString(credentials.getBytes());

        try {
            Map<String, Object> tokenResponse = webClient.post()
                    .uri(properties.getOauthTokenUrl())
                    .header(HttpHeaders.AUTHORIZATION, "Basic " + encoded)
                    .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_FORM_URLENCODED_VALUE)
                    .bodyValue("grant_type=client_credentials")
                    .retrieve()
                    .bodyToMono(Map.class)
                    .map(m -> (Map<String, Object>) m)
                    .block(Duration.ofSeconds(10));

            if (tokenResponse != null) {
                return (String) tokenResponse.getOrDefault("access_token", "");
            }
        } catch (Exception e) {
            log.error("Failed to obtain SAP OAuth token", e);
        }
        return "";
    }

    /**
     * Determine whether a throwable warrants a retry.
     *
     * <p>Only 5xx server errors and connection exceptions are retried.
     * 4xx client errors (Bad Request, Not Found, Unauthorized) are not — they indicate
     * a bug in the request and would fail on retry anyway.</p>
     *
     * @param throwable the error from the WebClient pipeline
     * @return {@code true} if the error is retryable
     */
    private boolean isRetryable(Throwable throwable) {
        if (throwable instanceof WebClientResponseException responseEx) {
            return responseEx.getStatusCode().is5xxServerError();
        }
        // Retry on connection errors, timeouts etc.
        return !(throwable instanceof WebClientResponseException);
    }
}
