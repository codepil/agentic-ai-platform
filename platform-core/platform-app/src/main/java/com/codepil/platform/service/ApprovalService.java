package com.codepil.platform.service;

import com.codepil.platform.api.dto.ApprovalDecisionRequest;
import com.codepil.platform.domain.ApprovalRequest;
import com.codepil.platform.repository.ApprovalRequestRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Service for managing human approval gates in the SDLC workflow.
 *
 * <h3>Approval flow</h3>
 * <pre>
 * 1. agent-engine sends SSE event: event_type=approval_requested
 * 2. AgentRunService calls createApprovalRequest() → saved to MongoDB (status=pending)
 * 3. Slack notification sent to approver channel
 * 4. Human reviews in mfe-approval-portal or REST API
 * 5. POST /api/v1/approvals/{id}/decide → processDecision()
 *    → MongoDB updated (status=approved/rejected, approvedBy, decidedAt)
 *    → agent-engine POST /api/v1/runs/{runId}/resume
 *    → SSE subscription re-established
 * </pre>
 */
@Service
public class ApprovalService {

    private static final Logger log = LoggerFactory.getLogger(ApprovalService.class);

    private final ApprovalRequestRepository approvalRequestRepository;
    private final SlackNotificationService slackNotificationService;
    private final AgentRunService agentRunService;
    private final WebClient agentEngineWebClient;
    private final ObjectMapper objectMapper;

    public ApprovalService(
            ApprovalRequestRepository approvalRequestRepository,
            SlackNotificationService slackNotificationService,
            AgentRunService agentRunService,
            @Qualifier("agentEngineWebClient") WebClient agentEngineWebClient,
            ObjectMapper objectMapper) {
        this.approvalRequestRepository = approvalRequestRepository;
        this.slackNotificationService = slackNotificationService;
        this.agentRunService = agentRunService;
        this.agentEngineWebClient = agentEngineWebClient;
        this.objectMapper = objectMapper;
    }

    /**
     * Return all pending approval requests across all SDLC runs.
     *
     * <p>Used by the approval portal dashboard to show approvers what needs attention.</p>
     *
     * @return list of {@code status=pending} approval requests
     */
    public List<ApprovalRequest> getPendingApprovals() {
        return approvalRequestRepository.findByStatus("pending");
    }

    /**
     * Create a new approval request when the agent-engine raises a gate.
     *
     * <p>Called by {@link AgentRunService} when it receives an {@code approval_requested}
     * SSE event. Parses the event payload to extract the approval stage and artifact summary,
     * persists the request to MongoDB, and sends a Slack notification.</p>
     *
     * @param runId        the UUID of the SDLC run
     * @param eventPayload the raw JSON payload from the SSE event
     */
    public void createApprovalRequest(String runId, String eventPayload) {
        try {
            Map<String, Object> event = objectMapper.readValue(eventPayload,
                    new TypeReference<Map<String, Object>>() {});

            String approvalStage = (String) event.getOrDefault("approval_stage", "requirements");
            String artifactSummary = (String) event.getOrDefault("payload", "No summary provided");

            ApprovalRequest request = new ApprovalRequest();
            request.setRunId(runId);
            request.setApprovalStage(approvalStage);
            request.setStatus("pending");
            request.setArtifactSummary(artifactSummary);

            approvalRequestRepository.save(request);

            log.info("Approval request created runId={} stage={}", runId, approvalStage);

            slackNotificationService.notifyApprover(runId, approvalStage, artifactSummary);

        } catch (Exception e) {
            log.error("Failed to create approval request runId={}", runId, e);
        }
    }

    /**
     * Process an approval or rejection decision for a pending gate.
     *
     * <ol>
     *   <li>Load the {@link ApprovalRequest} by ID — throw if not found or not pending.</li>
     *   <li>Update the document with decision, feedback, approvedBy, decidedAt.</li>
     *   <li>POST the decision to the agent-engine's {@code /api/v1/runs/{runId}/resume}.</li>
     *   <li>Re-subscribe to the SSE event stream.</li>
     * </ol>
     *
     * @param approvalId     the MongoDB document ID of the {@link ApprovalRequest}
     * @param decisionRequest the decision (approved/rejected) and optional feedback
     * @param decidedByUserId the Okta user ID of the approver
     */
    public void processDecision(String approvalId,
                                ApprovalDecisionRequest decisionRequest,
                                String decidedByUserId) {

        ApprovalRequest approval = approvalRequestRepository.findById(approvalId)
                .orElseThrow(() -> new IllegalArgumentException(
                        "Approval request not found: " + approvalId));

        if (!"pending".equals(approval.getStatus())) {
            throw new IllegalStateException(
                    "Approval request " + approvalId + " is already " + approval.getStatus());
        }

        // Update the approval document
        approval.setStatus(decisionRequest.decision().equals("approved") ? "approved" : "rejected");
        approval.setDecision(decisionRequest.decision());
        approval.setFeedback(decisionRequest.feedback());
        approval.setApprovedBy(decidedByUserId);
        approval.setDecidedAt(Instant.now());
        approvalRequestRepository.save(approval);

        log.info("Approval decision recorded approvalId={} decision={} decidedBy={}",
                 approvalId, decisionRequest.decision(), decidedByUserId);

        // POST resume to agent-engine
        String runId = approval.getRunId();
        Map<String, Object> resumeRequest = new HashMap<>();
        resumeRequest.put("decision", decisionRequest.decision());
        resumeRequest.put("feedback", decisionRequest.feedback());
        resumeRequest.put("approved_by", decidedByUserId);

        agentEngineWebClient.post()
                .uri("/api/v1/runs/{runId}/resume", runId)
                .bodyValue(resumeRequest)
                .retrieve()
                .bodyToMono(String.class)
                .subscribe(
                    response -> {
                        log.info("Agent engine resumed runId={} decision={}", runId, decisionRequest.decision());
                        // Re-subscribe to SSE stream to continue receiving events
                        agentRunService.subscribeToEventStream(runId);
                    },
                    error -> log.error("Failed to resume agent engine runId={}", runId, error)
                );
    }
}
