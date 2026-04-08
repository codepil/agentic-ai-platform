package com.codepil.platform.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

/**
 * WebClient configuration for communication with the Python agent-engine (FastAPI).
 *
 * <p>A single named {@link WebClient} bean is configured with:
 * <ul>
 *   <li>Base URL from {@code AGENT_ENGINE_BASE_URL} environment variable (default: {@code http://localhost:8000})</li>
 *   <li>Default {@code Content-Type: application/json} header</li>
 *   <li>30-second response timeout (SSE streams use a separate long-lived connection)</li>
 * </ul>
 * </p>
 *
 * <h3>Usage</h3>
 * <p>Inject as {@code @Qualifier("agentEngineWebClient") WebClient webClient} in
 * {@link com.codepil.platform.service.AgentRunService} and
 * {@link com.codepil.platform.service.ApprovalService}.</p>
 */
@Configuration
public class WebClientConfig {

    /**
     * WebClient pre-configured to call the Python FastAPI agent-engine.
     *
     * @param baseUrl base URL of the agent-engine, typically {@code http://localhost:8000}
     *                in development and the internal service DNS in Kubernetes.
     * @return configured {@link WebClient} instance
     */
    @Bean("agentEngineWebClient")
    public WebClient agentEngineWebClient(
            @Value("${agent.engine.base-url:http://localhost:8000}") String baseUrl) {

        return WebClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .codecs(codecs -> codecs
                    .defaultCodecs()
                    .maxInMemorySize(16 * 1024 * 1024)  // 16 MB — large payloads from code gen
                )
                .build();
    }
}
