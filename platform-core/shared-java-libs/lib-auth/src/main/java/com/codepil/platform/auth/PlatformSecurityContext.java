package com.codepil.platform.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Static utility class providing convenient access to the current user's security context.
 *
 * <p>All methods read from Spring's {@link SecurityContextHolder} — they are safe to call
 * from any {@code @Service} or {@code @Component} that is executing within a request thread
 * (i.e. after the Spring Security filter chain has populated the context).</p>
 *
 * <h3>Usage in generated product services</h3>
 * <pre>
 * // In any @Service method, during a request:
 * String userId = PlatformSecurityContext.getCurrentUserId();
 * log.info("Creating order for userId={}", userId);
 *
 * if (!PlatformSecurityContext.hasScope("orders:write")) {
 *     throw new AccessDeniedException("Missing scope orders:write");
 * }
 * </pre>
 *
 * <p>This is an alternative to injecting {@code Authentication} as a method parameter,
 * which is less ergonomic in deep service-layer code. The trade-off is testability —
 * tests must call {@code SecurityContextHolder.setContext()} to set up the context.</p>
 */
public final class PlatformSecurityContext {

    private static final Logger log = LoggerFactory.getLogger(PlatformSecurityContext.class);

    private PlatformSecurityContext() {
        // Utility class — not instantiable
    }

    /**
     * Return the Okta user ID (JWT subject claim) of the current authenticated user.
     *
     * @return the subject claim value (Okta user ID),
     *         or {@code "anonymous"} if no authentication context is present
     */
    public static String getCurrentUserId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) {
            return "anonymous";
        }
        if (auth.getPrincipal() instanceof Jwt jwt) {
            return jwt.getSubject();
        }
        return auth.getName();
    }

    /**
     * Return all OAuth2 scopes granted to the current authenticated user.
     *
     * <p>Scopes are returned as strings without the {@code SCOPE_} prefix
     * (e.g. {@code ["agents:run", "agents:read"]} rather than
     * {@code ["SCOPE_agents:run", "SCOPE_agents:read"]}).</p>
     *
     * @return list of scope strings, or an empty list if not authenticated
     */
    public static List<String> getCurrentScopes() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null) {
            return Collections.emptyList();
        }

        Collection<? extends GrantedAuthority> authorities = auth.getAuthorities();
        return authorities.stream()
                .map(GrantedAuthority::getAuthority)
                .filter(a -> a.startsWith("SCOPE_"))
                .map(a -> a.substring("SCOPE_".length()))
                .collect(Collectors.toList());
    }

    /**
     * Check whether the current user has a specific OAuth2 scope.
     *
     * <p>Equivalent to Spring Security's {@code @PreAuthorize("hasAuthority('SCOPE_{scope}')")}
     * but callable programmatically from service-layer code.</p>
     *
     * @param scope the scope to check (without {@code SCOPE_} prefix, e.g. {@code "agents:run"})
     * @return {@code true} if the current user's JWT contains the specified scope
     */
    public static boolean hasScope(String scope) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null) {
            return false;
        }
        String requiredAuthority = "SCOPE_" + scope;
        return auth.getAuthorities().stream()
                .anyMatch(a -> requiredAuthority.equals(a.getAuthority()));
    }

    /**
     * Return the raw {@link Jwt} from the security context, if available.
     *
     * @return the JWT, or {@code null} if not authenticated or if the principal is not a JWT
     */
    public static Jwt getCurrentJwt() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwtAuth &&
                jwtAuth.getPrincipal() instanceof Jwt jwt) {
            return jwt;
        }
        return null;
    }
}
