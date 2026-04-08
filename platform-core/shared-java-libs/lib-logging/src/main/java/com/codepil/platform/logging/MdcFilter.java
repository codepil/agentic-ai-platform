package com.codepil.platform.logging;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Servlet filter that injects run and product context into the SLF4J MDC.
 *
 * <p>This filter runs once per request (via {@link OncePerRequestFilter}) and
 * extracts two custom HTTP headers from the request, placing their values into
 * the SLF4J Mapped Diagnostic Context (MDC):
 * <ul>
 *   <li>{@code X-Run-Id} → MDC key {@code runId}</li>
 *   <li>{@code X-Product-Id} → MDC key {@code productId}</li>
 * </ul>
 * </p>
 *
 * <p>The {@code application.yml} logging pattern references these MDC keys:
 * <pre>
 * logging.pattern.console: "%d{ISO8601} [%thread] %-5level [%X{runId}] [%X{productId}] %logger{36} - %msg%n"
 * </pre>
 * This means every log line emitted during a request automatically includes the run ID
 * and product ID — without any per-method MDC.put() calls — enabling log correlation
 * in CloudWatch Insights or Kibana across dozens of log lines per agent event.
 * </p>
 *
 * <h3>MDC cleanup</h3>
 * <p>MDC keys are cleared in the {@code finally} block after the filter chain completes.
 * This is critical in thread-pool-based servers: without cleanup, MDC values leak into
 * subsequent requests handled by the same thread.</p>
 *
 * <h3>Usage</h3>
 * <p>The ReactJS MFE passes these headers when it knows the current run context:
 * <pre>
 * axios.get('/api/v1/runs/' + runId + '/artifacts', {
 *   headers: { 'X-Run-Id': runId, 'X-Product-Id': productId }
 * });
 * </pre>
 * </p>
 */
@Component
public class MdcFilter extends OncePerRequestFilter {

    /** HTTP header name for the SDLC run ID. */
    public static final String HEADER_RUN_ID = "X-Run-Id";

    /** HTTP header name for the platform product ID. */
    public static final String HEADER_PRODUCT_ID = "X-Product-Id";

    /** MDC key for the run ID. */
    public static final String MDC_RUN_ID = "runId";

    /** MDC key for the product ID. */
    public static final String MDC_PRODUCT_ID = "productId";

    /**
     * Extract {@code X-Run-Id} and {@code X-Product-Id} headers and put them in the MDC.
     *
     * <p>MDC keys are always cleared in the {@code finally} block, even if an exception
     * is thrown downstream in the filter chain.</p>
     *
     * @param request     the incoming HTTP request
     * @param response    the HTTP response
     * @param filterChain the remaining filter chain
     * @throws ServletException if the filter chain throws a servlet error
     * @throws IOException      if an I/O error occurs
     */
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String runId = request.getHeader(HEADER_RUN_ID);
        String productId = request.getHeader(HEADER_PRODUCT_ID);

        try {
            if (runId != null && !runId.isBlank()) {
                MDC.put(MDC_RUN_ID, runId);
            }
            if (productId != null && !productId.isBlank()) {
                MDC.put(MDC_PRODUCT_ID, productId);
            }

            filterChain.doFilter(request, response);

        } finally {
            MDC.remove(MDC_RUN_ID);
            MDC.remove(MDC_PRODUCT_ID);
        }
    }
}
