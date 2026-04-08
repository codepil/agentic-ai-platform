package com.codepil.platform.auth;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Method-level annotation for declarative OAuth2 scope enforcement at the service layer.
 *
 * <p>This annotation is the service-layer counterpart to Spring Security's
 * {@code @PreAuthorize("hasAuthority('SCOPE_agents:run')")} controller-level annotation.
 * Use it to enforce scopes on service methods that are called from multiple entry points
 * (REST controllers, scheduled jobs, messaging listeners) where controller-level checks
 * alone are insufficient.</p>
 *
 * <h3>Usage</h3>
 * <pre>
 * {@literal @}Service
 * public class AgentRunService {
 *
 *     {@literal @}RequiresScope("agents:run")
 *     public StartRunResponse startRun(StartRunRequest request, String userId) {
 *         // This method will throw AccessDeniedException if the caller
 *         // does not have the agents:run scope
 *     }
 * }
 * </pre>
 *
 * <h3>Enforcement</h3>
 * <p>Enforcement is provided by a Spring AOP {@code @Aspect} that intercepts methods
 * annotated with {@code @RequiresScope} and calls
 * {@link PlatformSecurityContext#hasScope(String)}. The aspect is activated when
 * the {@code lib-auth} library is on the classpath and {@code @EnableAspectJAutoProxy}
 * is present (enabled by default in Spring Boot).</p>
 *
 * @see PlatformSecurityContext#hasScope(String)
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface RequiresScope {

    /**
     * The OAuth2 scope required to call this method.
     *
     * <p>Specify the scope string without the {@code SCOPE_} prefix.
     * Example: {@code "agents:run"}, {@code "agents:approve"}, {@code "admin:manage"}.</p>
     *
     * @return the required scope string
     */
    String value();
}
