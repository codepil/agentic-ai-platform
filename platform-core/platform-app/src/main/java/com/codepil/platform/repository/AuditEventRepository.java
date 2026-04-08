package com.codepil.platform.repository;

import com.codepil.platform.domain.AuditEvent;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Spring Data MongoDB repository for {@link AuditEvent} documents.
 *
 * <p>The audit trail is append-only. The primary query pattern is "all events for run X
 * in chronological order" — supported by the compound index {@code (runId, timestampMs)}
 * defined on the {@link AuditEvent} document class.</p>
 */
@Repository
public interface AuditEventRepository extends MongoRepository<AuditEvent, String> {

    /**
     * Return all audit events for a run in chronological order.
     *
     * <p>This is the primary query for the audit log MFE and debugging tools.
     * The compound index on {@code (runId, timestampMs)} makes this efficient.</p>
     *
     * @param runId the UUID of the SDLC run
     * @return all events ordered by ascending timestamp (earliest first)
     */
    List<AuditEvent> findByRunIdOrderByTimestampMsAsc(String runId);

    /**
     * Return all audit events of a specific type for a run.
     *
     * <p>Useful for filtering the audit log to, for example, only {@code error} events
     * or only {@code approval_requested} events.</p>
     *
     * @param runId     the UUID of the SDLC run
     * @param eventType the event type to filter on
     * @return matching events ordered by ascending timestamp
     */
    List<AuditEvent> findByRunIdAndEventTypeOrderByTimestampMsAsc(String runId, String eventType);

    /**
     * Count the number of events of a given type for a run.
     *
     * <p>Used to count QA iterations or tool calls for LLM usage analytics.</p>
     *
     * @param runId     the UUID of the SDLC run
     * @param eventType the event type to count
     * @return the count
     */
    long countByRunIdAndEventType(String runId, String eventType);
}
