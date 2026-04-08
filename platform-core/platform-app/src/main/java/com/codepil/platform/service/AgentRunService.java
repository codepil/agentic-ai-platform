package com.codepil.platform.service;

import com.codepil.platform.api.dto.RunStatusResponse;
import com.codepil.platform.api.dto.StartRunRequest;
import com.codepil.platform.api.dto.StartRunResponse;
import com.codepil.platform.domain.AgentRun;
import com.codepil.platform.repository.AgentRunRepository;
import com.codepil.platform.websocket.AgentEventBroadcaster;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.scheduler.Schedulers;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Core orchestration service for SDLC run lifecycle management.
 *
 * <h3>Responsibilities</h3>
 * <ol>
 *   <li>Accept a run start request, persist the {@link AgentRun} to MongoDB, and forward
 *       the request to the Python agent-engine.</li>
 *   <li>Subscribe to the SSE event stream from the agent-engine and:
 *     <ul>
 *       <li>Broadcast each event to the ReactJS MFE via STOMP WebSocket</li>
 *       <li>Record every event to the audit trail (async)</li>
 *       <li>Handle {@code approval_requested} events by creating an {@link com.codepil.platform.domain.ApprovalRequest}</li>
 *       <li>Handle {@code run_complete} events by updating the run status</li>
 *       <li>Handle SSE errors by updating the run status to {@code failed} and alerting on-call</li>
 *     </ul>
 *   </li>
 *   <li>Expose a status query method that merges MongoDB state with a live agent-engine call.</li>
 * </ol>
 */
@Service
public class AgentRunService {

    private static final Logger log = LoggerFactory.getLogger(AgentRunService.class);

    private final AgentRunRepository agentRunRepository;
    private final AuditTrailService auditTrailService;
    private final ApprovalService approvalService;
    private final AgentEventBroadcaster agentEventBroadcaster;
    private final SlackNotificationService slackNotificationService;
    private final WebClient agentEngineWebClient;
    private final ObjectMapper objectMapper;

    public AgentRunService(
            AgentRunRepository agentRunRepository,
            AuditTrailService auditTrailService,
            ApprovalService approvalService,
            AgentEventBroadcaster agentEventBroadcaster,
            SlackNotificationService slackNotificationService,
            @Qualifier("agentEngineWebClient") WebClient agentEngineWebClient,
            ObjectMapper objectMapper) {
        this.agentRunRepository = agentRunRepository;
        this.auditTrailService = auditTrailService;
        this.approvalService = approvalService;
        this.agentEventBroadcaster = agentEventBroadcaster;
        this.slackNotificationService = slackNotificationService;
        this.agentEngineWebClient = agentEngineWebClient;
        this.objectMapper = objectMapper;
    }

    /**
     * Start a new SDLC run.
     *
     * <ol>
     *   <li>Generate {@code runId} and {@code threadId} UUIDs.</li>
     *   <li>Persist an {@link AgentRun} document with {@code status=running}.</li>
     *   <li>POST the run request to the agent-engine.</li>
     *   <li>Subscribe to the SSE event stream in a background thread.</li>
     * </ol>
     *
     * @param request           the run configuration from the REST API
     * @param initiatedByUserId the Okta user ID who initiated the run
     * @return the run ID and initial status
     */
    public StartRunResponse startRun(StartRunRequest request, String initiatedByUserId) {
        String runId = UUID.randomUUID().toString();
        String threadId = UUID.randomUUID().toString();

        // Persist the run document
        AgentRun run = new AgentRun();
        run.setRunId(runId);
        run.setThreadId(threadId);
        run.setProductId(request.productId());
        run.setJiraEpicId(request.jiraEpicId());
        run.setStatus("running");
        run.setCurrentStage("requirements");
        run.setQaIteration(0);
        run.setInitiatedByUserId(initiatedByUserId);
        agentRunRepository.save(run);

        log.info("SDLC run created runId={} productId={} jiraEpicId={} initiatedBy={}",
                 runId, request.productId(), request.jiraEpicId(), initiatedByUserId);

        // Build the request payload for the agent-engine
        Map<String, Object> engineRequest = new HashMap<>();
        engineRequest.put("run_id", runId);
        engineRequest.put("thread_id", threadId);
        engineRequest.put("jira_epic_id", request.jiraEpicId());
        engineRequest.put("product_id", request.productId());
        engineRequest.put("figma_url", request.figmaUrl());
        engineRequest.put("prd_s3_url", request.prdS3Url());
        engineRequest.put("max_qa_iterations", request.maxQaIterations());

        // POST to agent-engine to start the run (fire-and-subscribe)
        agentEngineWebClient.post()
                .uri("/api/v1/runs")
                .bodyValue(engineRequest)
                .retrieve()
                .bodyToMono(String.class)
                .subscribeOn(Schedulers.boundedElastic())
                .subscribe(
                    response -> {
                        log.info("Agent engine accepted run runId={}", runId);
                        subscribeToEventStream(runId);
                    },
                    error -> {
                        log.error("Agent engine rejected run runId={}", runId, error);
                        updateRunStatus(runId, "failed");
                        slackNotificationService.alertOncall(runId,
                            "Agent engine rejected run start: " + error.getMessage());
                    }
                );

        return new StartRunResponse(runId, "started");
    }

    /**
     * Subscribe to the SSE event stream from the agent-engine for a run.
     *
     * <p>Each received event is:
     * <ul>
     *   <li>Broadcast to the WebSocket topic {@code /topic/runs/{runId}}</li>
     *   <li>Recorded to the audit trail (asynchronously)</li>
     *   <li>Processed for special event types (approval_requested, run_complete, error)</li>
     * </ul>
     * </p>
     *
     * <p>The SSE subscription is long-lived and runs on the {@code boundedElastic} scheduler
     * to avoid blocking the Netty event loop.</p>
     *
     * @param runId the UUID of the SDLC run to subscribe to
     */
    public void subscribeToEventStream(String runId) {
        log.info("Subscribing to SSE stream runId={}", runId);

        agentEngineWebClient.get()
                .uri("/api/v1/runs/{runId}/events", runId)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .retrieve()
                .bodyToFlux(String.class)
                .subscribeOn(Schedulers.boundedElastic())
                .subscribe(
                    event -> handleSseEvent(runId, event),
                    error -> handleSseError(runId, error),
                    () -> log.info("SSE stream completed runId={}", runId)
                );
    }

    /**
     * Handle a single SSE event from the agent-engine.
     *
     * @param runId the run this event belongs to
     * @param rawEvent the raw JSON string from the SSE stream
     */
    private void handleSseEvent(String runId, String rawEvent) {
        try {
            MDC.put("runId", runId);

            // Broadcast to WebSocket first (lowest latency for UI)
            agentEventBroadcaster.broadcast(runId, rawEvent);

            // Record to audit trail asynchronously (non-blocking)
            auditTrailService.record(runId, rawEvent);

            // Parse event for special handling
            Map<String, Object> event = objectMapper.readValue(rawEvent,
                    new TypeReference<Map<String, Object>>() {});
            String eventType = (String) event.getOrDefault("event_type", "");

            switch (eventType) {
                case "approval_requested" -> {
                    log.info("Approval gate triggered runId={}", runId);
                    updateRunStatus(runId, "waiting_approval");
                    approvalService.createApprovalRequest(runId, rawEvent);
                }
                case "run_complete" -> {
                    log.info("Run completed runId={}", runId);
                    updateRunStatus(runId, "completed");
                }
                case "stage_complete" -> {
                    String stage = (String) event.getOrDefault("payload", "");
                    log.info("Stage complete runId={} stage={}", runId, stage);
                    updateCurrentStage(runId, stage);
                }
                case "error" -> {
                    String errorMsg = (String) event.getOrDefault("payload", "unknown error");
                    log.warn("Agent error runId={} message={}", runId, errorMsg);
                    appendError(runId, errorMsg);
                }
                default -> {
                    // thinking, tool_call, state_update — already broadcast and recorded
                }
            }
        } catch (JsonProcessingException e) {
            log.warn("Could not parse SSE event runId={} raw={}", runId, rawEvent, e);
        } finally {
            MDC.remove("runId");
        }
    }

    /**
     * Handle SSE stream errors (connection failure, timeout, agent crash).
     *
     * @param runId the run whose stream errored
     * @param error the error from the reactive pipeline
     */
    private void handleSseError(String runId, Throwable error) {
        log.error("SSE stream error runId={}", runId, error);
        updateRunStatus(runId, "failed");
        appendError(runId, "SSE stream disconnected: " + error.getMessage());
        slackNotificationService.alertOncall(runId,
            "Agent run failed — SSE stream disconnected: " + error.getMessage());
    }

    /**
     * Get the current status of a run by merging MongoDB state with a live agent-engine call.
     *
     * @param runId the UUID of the SDLC run
     * @return merged status response
     */
    public RunStatusResponse getRunStatus(String runId) {
        AgentRun run = agentRunRepository.findByRunId(runId)
                .orElseThrow(() -> new IllegalArgumentException("Run not found: " + runId));

        // Attempt a live status call to the agent-engine (best-effort — may be unavailable)
        List<String> nextNodes = new ArrayList<>();
        try {
            Map<String, Object> liveStatus = agentEngineWebClient.get()
                    .uri("/api/v1/runs/{runId}/status", runId)
                    .retrieve()
                    .bodyToMono(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {})
                    .block(java.time.Duration.ofSeconds(5));

            if (liveStatus != null && liveStatus.get("next_nodes") instanceof List<?> nodes) {
                nodes.forEach(n -> nextNodes.add(String.valueOf(n)));
            }
        } catch (Exception e) {
            log.debug("Live status call failed runId={} — using cached state", runId, e);
        }

        return new RunStatusResponse(
                run.getRunId(),
                run.getCurrentStage(),
                nextNodes,
                run.getQaIteration(),
                run.getLlmUsage(),
                run.getErrors() != null ? run.getErrors() : List.of()
        );
    }

    /**
     * List SDLC artifacts produced by a run.
     *
     * <p>Delegates to the agent-engine's artifact API — artifacts are stored there
     * in the {@code sdlc_artifacts} collection managed by Python.</p>
     *
     * @param runId the UUID of the SDLC run
     * @return list of artifact metadata maps
     */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> getArtifacts(String runId) {
        try {
            List<Map<String, Object>> result = agentEngineWebClient.get()
                    .uri("/api/v1/runs/{runId}/artifacts", runId)
                    .retrieve()
                    .bodyToMono(new org.springframework.core.ParameterizedTypeReference<List<Map<String, Object>>>() {})
                    .block(java.time.Duration.ofSeconds(10));
            return result != null ? result : List.of();
        } catch (Exception e) {
            log.warn("Could not fetch artifacts runId={}", runId, e);
            return List.of();
        }
    }

    // -------------------------------------------------------------------------
    // Private helpers — MongoDB update methods
    // -------------------------------------------------------------------------

    private void updateRunStatus(String runId, String status) {
        agentRunRepository.findByRunId(runId).ifPresent(run -> {
            run.setStatus(status);
            agentRunRepository.save(run);
        });
    }

    private void updateCurrentStage(String runId, String stage) {
        agentRunRepository.findByRunId(runId).ifPresent(run -> {
            run.setCurrentStage(stage);
            agentRunRepository.save(run);
        });
    }

    private void appendError(String runId, String errorMessage) {
        agentRunRepository.findByRunId(runId).ifPresent(run -> {
            run.addError(errorMessage);
            agentRunRepository.save(run);
        });
    }
}
