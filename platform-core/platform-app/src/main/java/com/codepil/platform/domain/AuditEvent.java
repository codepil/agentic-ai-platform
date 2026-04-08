package com.codepil.platform.domain;

import com.codepil.platform.mongodb.BaseDocument;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * MongoDB document recording a single agent event in the SDLC audit trail.
 *
 * <p>Stored in the {@code audit_trail} collection. One document is written for every
 * SSE event received from the Python agent-engine, including thinking steps, tool calls,
 * stage completions, approval requests, and errors.</p>
 *
 * <p>The audit trail is append-only — events are never updated or deleted.
 * It provides a complete replay of every agent action and reasoning step for compliance,
 * debugging, and the {@code mfe-audit-logs} MFE.</p>
 *
 * <p>Compound index on {@code (runId, timestampMs)} supports the primary query pattern:
 * "give me all events for run X, ordered by time."</p>
 */
@Document(collection = "audit_trail")
@CompoundIndexes({
    @CompoundIndex(name = "run_timestamp_idx", def = "{'runId': 1, 'timestampMs': 1}")
})
public class AuditEvent extends BaseDocument {

    /** FK to {@code agent_runs.runId}. */
    @Indexed
    private String runId;

    /** Name of the CrewAI agent that produced this event (e.g. {@code RequirementsParser}). */
    private String agentName;

    /**
     * Type of event.
     * Values: {@code thinking} | {@code tool_call} | {@code state_update} |
     *         {@code stage_complete} | {@code approval_requested} | {@code run_complete} | {@code error}
     */
    private String eventType;

    /** SDLC stage at the time of the event (e.g. {@code requirements}, {@code dev}). */
    private String stage;

    /** Full raw JSON payload from the SSE event — preserved for replay and debugging. */
    private String rawPayload;

    /** Epoch milliseconds from the SSE event timestamp field. */
    private long timestampMs;

    // -------------------------------------------------------------------------
    // Constructors
    // -------------------------------------------------------------------------

    public AuditEvent() {}

    // -------------------------------------------------------------------------
    // Getters and Setters
    // -------------------------------------------------------------------------

    public String getRunId() {
        return runId;
    }

    public void setRunId(String runId) {
        this.runId = runId;
    }

    public String getAgentName() {
        return agentName;
    }

    public void setAgentName(String agentName) {
        this.agentName = agentName;
    }

    public String getEventType() {
        return eventType;
    }

    public void setEventType(String eventType) {
        this.eventType = eventType;
    }

    public String getStage() {
        return stage;
    }

    public void setStage(String stage) {
        this.stage = stage;
    }

    public String getRawPayload() {
        return rawPayload;
    }

    public void setRawPayload(String rawPayload) {
        this.rawPayload = rawPayload;
    }

    public long getTimestampMs() {
        return timestampMs;
    }

    public void setTimestampMs(long timestampMs) {
        this.timestampMs = timestampMs;
    }
}
