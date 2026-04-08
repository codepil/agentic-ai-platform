package com.codepil.platform.service;

import com.codepil.platform.domain.AuditEvent;
import com.codepil.platform.repository.AuditEventRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * Service for recording and querying the SDLC audit trail.
 *
 * <p>Every SSE event from the agent-engine is recorded to the {@code audit_trail}
 * MongoDB collection. Recording is asynchronous ({@code @Async}) so it does not
 * block the SSE consumption thread or delay WebSocket broadcasting.</p>
 *
 * <p>The audit trail is append-only — events are never updated or deleted.
 * It provides a full replay of every agent action for compliance, debugging,
 * and the {@code mfe-audit-logs} ReactJS MFE.</p>
 */
@Service
public class AuditTrailService {

    private static final Logger log = LoggerFactory.getLogger(AuditTrailService.class);

    private final AuditEventRepository auditEventRepository;
    private final ObjectMapper objectMapper;

    public AuditTrailService(AuditEventRepository auditEventRepository,
                             ObjectMapper objectMapper) {
        this.auditEventRepository = auditEventRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Record a single SSE event to the audit trail.
     *
     * <p>This method is annotated {@code @Async} so it executes on a separate thread
     * from Spring's task executor pool. This ensures that MongoDB write latency does not
     * affect the SSE→WebSocket broadcast path.</p>
     *
     * <p>If JSON parsing fails, the raw event is still recorded in the {@code rawPayload}
     * field with a fallback event type — audit completeness is prioritised over parsing.</p>
     *
     * @param runId    the UUID of the SDLC run this event belongs to
     * @param rawEvent the raw JSON string from the SSE stream
     */
    @Async
    public void record(String runId, String rawEvent) {
        try {
            Map<String, Object> event = objectMapper.readValue(rawEvent,
                    new TypeReference<Map<String, Object>>() {});

            AuditEvent auditEvent = new AuditEvent();
            auditEvent.setRunId(runId);
            auditEvent.setAgentName((String) event.getOrDefault("agent", "unknown"));
            auditEvent.setEventType((String) event.getOrDefault("event_type", "unknown"));
            auditEvent.setStage((String) event.getOrDefault("stage", ""));
            auditEvent.setRawPayload(rawEvent);

            Object ts = event.get("ts");
            if (ts instanceof Number tsNum) {
                auditEvent.setTimestampMs(tsNum.longValue());
            } else {
                auditEvent.setTimestampMs(System.currentTimeMillis());
            }

            auditEventRepository.save(auditEvent);

        } catch (Exception e) {
            // Best-effort fallback: save the raw event even if parsing fails
            log.warn("Audit event parse failed runId={} — saving raw payload", runId, e);
            AuditEvent fallback = new AuditEvent();
            fallback.setRunId(runId);
            fallback.setEventType("parse_error");
            fallback.setRawPayload(rawEvent);
            fallback.setTimestampMs(System.currentTimeMillis());
            try {
                auditEventRepository.save(fallback);
            } catch (Exception saveEx) {
                log.error("Failed to save fallback audit event runId={}", runId, saveEx);
            }
        }
    }

    /**
     * Return all audit events for a run in chronological order.
     *
     * <p>Used by the audit log MFE ({@code mfe-audit-logs}) and debugging tools.</p>
     *
     * @param runId the UUID of the SDLC run
     * @return all events ordered by ascending timestamp (earliest first)
     */
    public List<AuditEvent> getAuditTrail(String runId) {
        return auditEventRepository.findByRunIdOrderByTimestampMsAsc(runId);
    }
}
