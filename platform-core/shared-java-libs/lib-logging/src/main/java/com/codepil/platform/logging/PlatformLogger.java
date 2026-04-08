package com.codepil.platform.logging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Structured JSON logger wrapper for platform services.
 *
 * <p>Wraps SLF4J's {@link Logger} to produce log events as JSON objects.
 * This format is consumed directly by:
 * <ul>
 *   <li>AWS CloudWatch Logs Insights (JSON field extraction)</li>
 *   <li>ELK Stack (Logstash JSON codec)</li>
 *   <li>Datadog (automatic JSON parsing)</li>
 * </ul>
 * </p>
 *
 * <h3>Log event format</h3>
 * <p>Each log call produces a single JSON line:
 * <pre>
 * {
 *   "timestamp": "2026-04-07T10:30:00Z",
 *   "level": "INFO",
 *   "logger": "com.codepil.catalog.service.ProductService",
 *   "message": "Listing products",
 *   "runId": "550e8400-...",       // from MDC (set by MdcFilter)
 *   "productId": "SelfCare-001",   // from MDC (set by MdcFilter)
 *   "page": 0,                     // additional key-value pairs
 *   "size": 20
 * }
 * </pre>
 * </p>
 *
 * <h3>Usage</h3>
 * <pre>
 * private static final PlatformLogger log = PlatformLogger.getLogger(ProductService.class);
 *
 * log.info("Listing products", "page", page, "size", size);
 * log.warn("Product not found in SAP", "materialId", materialId);
 * log.error("SAP call failed", "serviceName", service, "error", e.getMessage());
 * </pre>
 *
 * <h3>Migration from plain SLF4J</h3>
 * <p>Replace {@code private static final Logger log = LoggerFactory.getLogger(Foo.class);}
 * with {@code private static final PlatformLogger log = PlatformLogger.getLogger(Foo.class);}
 * — the method signatures are similar but {@code PlatformLogger} accepts varargs key-value pairs.</p>
 */
public final class PlatformLogger {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final Logger delegate;
    private final String loggerName;

    private PlatformLogger(Class<?> clazz) {
        this.delegate = LoggerFactory.getLogger(clazz);
        this.loggerName = clazz.getName();
    }

    /**
     * Create a {@link PlatformLogger} for the given class.
     *
     * @param clazz the class that owns the logger
     * @return a new {@link PlatformLogger} instance
     */
    public static PlatformLogger getLogger(Class<?> clazz) {
        return new PlatformLogger(clazz);
    }

    // -------------------------------------------------------------------------
    // Public log methods
    // -------------------------------------------------------------------------

    /**
     * Log at INFO level with additional structured key-value context.
     *
     * @param message the human-readable log message
     * @param kvPairs alternating key-value pairs to include in the JSON event (key, value, key, value, ...)
     */
    public void info(String message, Object... kvPairs) {
        if (delegate.isInfoEnabled()) {
            delegate.info(buildJsonEvent("INFO", message, null, kvPairs));
        }
    }

    /**
     * Log at WARN level with additional structured key-value context.
     *
     * @param message the human-readable log message
     * @param kvPairs alternating key-value pairs
     */
    public void warn(String message, Object... kvPairs) {
        if (delegate.isWarnEnabled()) {
            delegate.warn(buildJsonEvent("WARN", message, null, kvPairs));
        }
    }

    /**
     * Log at ERROR level with exception and additional structured key-value context.
     *
     * @param message   the human-readable log message
     * @param throwable the exception to include in the log event
     * @param kvPairs   alternating key-value pairs
     */
    public void error(String message, Throwable throwable, Object... kvPairs) {
        if (delegate.isErrorEnabled()) {
            delegate.error(buildJsonEvent("ERROR", message, throwable, kvPairs));
        }
    }

    /**
     * Log at ERROR level with additional structured key-value context (no exception).
     *
     * @param message the human-readable log message
     * @param kvPairs alternating key-value pairs
     */
    public void error(String message, Object... kvPairs) {
        error(message, null, kvPairs);
    }

    /**
     * Log at DEBUG level with additional structured key-value context.
     *
     * @param message the human-readable log message
     * @param kvPairs alternating key-value pairs
     */
    public void debug(String message, Object... kvPairs) {
        if (delegate.isDebugEnabled()) {
            delegate.debug(buildJsonEvent("DEBUG", message, null, kvPairs));
        }
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Build a JSON log event string from the provided parameters and MDC context.
     *
     * @param level     the log level string
     * @param message   the log message
     * @param throwable optional exception (may be null)
     * @param kvPairs   alternating key-value pairs
     * @return JSON string representing the log event
     */
    private String buildJsonEvent(String level, String message,
                                  Throwable throwable, Object[] kvPairs) {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("timestamp", Instant.now().toString());
        event.put("level", level);
        event.put("logger", loggerName);
        event.put("message", message);

        // Include MDC context (runId, productId from MdcFilter)
        String runId = MDC.get(MdcFilter.MDC_RUN_ID);
        String productId = MDC.get(MdcFilter.MDC_PRODUCT_ID);
        if (runId != null) {
            event.put("runId", runId);
        }
        if (productId != null) {
            event.put("productId", productId);
        }

        // Add key-value pairs
        if (kvPairs != null && kvPairs.length >= 2) {
            for (int i = 0; i + 1 < kvPairs.length; i += 2) {
                Object key = kvPairs[i];
                Object value = kvPairs[i + 1];
                if (key instanceof String keyStr) {
                    event.put(keyStr, value);
                }
            }
        }

        // Add exception details
        if (throwable != null) {
            event.put("errorType", throwable.getClass().getName());
            event.put("errorMessage", throwable.getMessage());
        }

        try {
            return MAPPER.writeValueAsString(event);
        } catch (JsonProcessingException e) {
            // Fallback to plain text if JSON serialisation fails
            return level + " " + message;
        }
    }
}
