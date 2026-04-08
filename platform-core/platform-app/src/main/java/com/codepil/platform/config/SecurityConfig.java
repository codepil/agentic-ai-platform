package com.codepil.platform.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.oauth2.server.resource.web.BearerTokenAuthenticationEntryPoint;
import org.springframework.security.oauth2.server.resource.web.access.BearerTokenAccessDeniedHandler;
import org.springframework.security.web.SecurityFilterChain;

import java.util.Collection;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Spring Security configuration for the platform control plane.
 *
 * <p>All endpoints require a valid Okta JWT except:
 * <ul>
 *   <li>{@code /actuator/health} — health check for load balancers and Kubernetes probes</li>
 *   <li>{@code /ws/**} — WebSocket handshake endpoint (STOMP over SockJS)</li>
 * </ul>
 * </p>
 *
 * <p>Scope-based access control is enforced at the HTTP filter chain level via
 * {@code authorizeHttpRequests()}. Okta's {@code scp} claim is mapped to Spring Security
 * {@link org.springframework.security.core.GrantedAuthority} objects prefixed with
 * {@code SCOPE_} by the custom {@link JwtAuthenticationConverter}.</p>
 *
 * <p>Required scopes per endpoint:
 * <ul>
 *   <li>{@code POST /api/v1/runs} - {@code SCOPE_agents:run}</li>
 *   <li>{@code GET  /api/v1/runs/**} - {@code SCOPE_agents:read}</li>
 *   <li>{@code GET  /api/v1/approvals} - {@code SCOPE_agents:read}</li>
 *   <li>{@code POST /api/v1/approvals/{id}/decide} - {@code SCOPE_agents:approve}</li>
 * </ul>
 * </p>
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    /**
     * Defines the HTTP security filter chain.
     *
     * <p>Sessions are stateless — the platform is purely JWT-based.
     * CSRF protection is disabled because API clients (ReactJS SPA and curl)
     * use the {@code Authorization} header, not cookie-based sessions.</p>
     *
     * @param http the {@link HttpSecurity} builder
     * @return the configured {@link SecurityFilterChain}
     * @throws Exception if the security DSL configuration fails
     */
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health", "/actuator/info").permitAll()
                .requestMatchers("/ws/**").permitAll()   // WebSocket handshake
                .requestMatchers(HttpMethod.POST, "/api/v1/runs")
                    .hasAuthority("SCOPE_agents:run")
                .requestMatchers(HttpMethod.GET, "/api/v1/runs/**")
                    .hasAuthority("SCOPE_agents:read")
                .requestMatchers(HttpMethod.GET, "/api/v1/approvals")
                    .hasAuthority("SCOPE_agents:read")
                .requestMatchers(HttpMethod.POST, "/api/v1/approvals/*/decide")
                    .hasAuthority("SCOPE_agents:approve")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthenticationConverter()))
            )
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint(new BearerTokenAuthenticationEntryPoint())
                .accessDeniedHandler(new BearerTokenAccessDeniedHandler())
            );

        return http.build();
    }

    /**
     * Converts Okta JWT {@code scp} claim into Spring Security {@code GrantedAuthority}
     * objects prefixed with {@code SCOPE_}.
     *
     * <p>Example: Okta token with {@code "scp": ["agents:run", "agents:read"]} results in
     * authorities {@code [SCOPE_agents:run, SCOPE_agents:read]}, which can be matched
     * by {@code hasAuthority("SCOPE_agents:run")} in {@code authorizeHttpRequests()}.</p>
     *
     * @return the configured {@link JwtAuthenticationConverter}
     */
    @Bean
    public JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(jwt -> {
            Object scpClaim = jwt.getClaims().get("scp");
            Collection<String> scopes;

            if (scpClaim instanceof List<?> scopeList) {
                scopes = scopeList.stream()
                    .filter(s -> s instanceof String)
                    .map(s -> (String) s)
                    .collect(Collectors.toList());
            } else if (scpClaim instanceof String scopeString) {
                scopes = List.of(scopeString.split(" "));
            } else {
                scopes = List.of();
            }

            return scopes.stream()
                .map(scope -> new SimpleGrantedAuthority("SCOPE_" + scope))
                .collect(Collectors.toList());
        });
        return converter;
    }
}
