package com.codepil.platform.auth;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.source.JWKSource;
import com.nimbusds.jose.jwk.source.RemoteJWKSet;
import com.nimbusds.jose.proc.BadJOSEException;
import com.nimbusds.jose.proc.JWSKeySelector;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.MalformedURLException;
import java.net.URI;
import java.text.ParseException;
import java.util.Collections;
import java.util.List;

/**
 * Validates Okta JWTs using the Okta JWKS (JSON Web Key Set) endpoint.
 *
 * <h3>Validation steps</h3>
 * <ol>
 *   <li>Fetch and cache the Okta JWKS from {@code {issuerUri}/.well-known/openid-configuration}</li>
 *   <li>Verify the JWT signature using the appropriate key from the JWKS</li>
 *   <li>Validate standard claims: {@code iss}, {@code exp}, {@code iat}</li>
 *   <li>Extract the {@code scp} claim as a list of scope strings</li>
 * </ol>
 *
 * <h3>JWKS caching</h3>
 * <p>The {@link RemoteJWKSet} implementation from Nimbus caches the JWKS in memory
 * and refreshes it automatically when a key ID is encountered that is not in the cache.
 * This avoids repeated HTTP calls to Okta's JWKS endpoint on every request.</p>
 *
 * <p>In Spring Boot applications, the {@code spring-boot-starter-oauth2-resource-server}
 * starter handles JWT validation automatically via the {@code SecurityConfig}.
 * This class is an alternative lower-level validator for use in non-Spring contexts
 * (e.g. CLI tools, service-to-service calls).</p>
 */
@Component
public class OktaJwtValidator {

    private static final Logger log = LoggerFactory.getLogger(OktaJwtValidator.class);

    private final ConfigurableJWTProcessor<SecurityContext> jwtProcessor;

    /**
     * Initialises the JWT processor with the Okta JWKS endpoint.
     *
     * @param issuerUri the Okta authorization server issuer URI
     *                  (e.g. {@code https://dev-12345.okta.com/oauth2/default})
     * @throws MalformedURLException if the JWKS URI cannot be constructed from the issuer URI
     */
    public OktaJwtValidator(
            @Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri}") String issuerUri)
            throws MalformedURLException {

        String jwksUri = issuerUri + "/v1/keys";
        log.info("Initialising OktaJwtValidator with JWKS endpoint: {}", jwksUri);

        JWKSource<SecurityContext> jwkSource = new RemoteJWKSet<>(
                URI.create(jwksUri).toURL());

        JWSKeySelector<SecurityContext> keySelector =
                new JWSVerificationKeySelector<>(JWSAlgorithm.RS256, jwkSource);

        jwtProcessor = new DefaultJWTProcessor<>();
        jwtProcessor.setJWSKeySelector(keySelector);
    }

    /**
     * Validate a raw JWT string and return its claims if valid.
     *
     * @param rawJwt the compact serialised JWT (three base64url-encoded parts separated by dots)
     * @return the parsed and validated {@link JWTClaimsSet}
     * @throws ParseException      if the JWT is malformed
     * @throws BadJOSEException    if the JWT signature is invalid or claims are rejected
     * @throws JOSEException       if a cryptographic error occurs during signature verification
     */
    public JWTClaimsSet validate(String rawJwt)
            throws ParseException, BadJOSEException, JOSEException {
        return jwtProcessor.process(rawJwt, null);
    }

    /**
     * Extract the list of OAuth2 scopes from the {@code scp} claim.
     *
     * <p>Okta's access tokens carry scopes in the {@code scp} claim as a list of strings
     * (e.g. {@code ["agents:run", "agents:read"]}). This is different from the standard
     * {@code scope} claim (a space-delimited string) used by some providers.</p>
     *
     * @param claims the validated JWT claims set
     * @return list of scope strings, or an empty list if {@code scp} is absent
     */
    @SuppressWarnings("unchecked")
    public List<String> extractScopes(JWTClaimsSet claims) {
        try {
            Object scpClaim = claims.getClaim("scp");
            if (scpClaim instanceof List<?> scopeList) {
                return (List<String>) scopeList;
            }
        } catch (Exception e) {
            log.warn("Failed to extract scp claim", e);
        }
        return Collections.emptyList();
    }

    /**
     * Extract the subject (user ID) from the JWT.
     *
     * @param claims the validated JWT claims set
     * @return the Okta user ID (subject claim value)
     */
    public String extractSubject(JWTClaimsSet claims) {
        return claims.getSubject();
    }
}
