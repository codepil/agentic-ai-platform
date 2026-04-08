package com.codepil.platform.api;

import com.codepil.platform.api.dto.ApprovalDecisionRequest;
import com.codepil.platform.domain.ApprovalRequest;
import com.codepil.platform.service.ApprovalService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * REST controller for human approval gate management.
 *
 * <h3>Endpoints</h3>
 * <pre>
 * GET    /api/v1/approvals                        — list pending approvals (scope: agents:read)
 * POST   /api/v1/approvals/{approvalId}/decide    — submit decision (scope: agents:approve)
 * </pre>
 *
 * <p>This controller is used by the {@code mfe-approval-portal} ReactJS MFE and
 * can also be called directly via the REST API (e.g. from a Slack webhook integration).</p>
 *
 * <p>The controller is thin — all business logic (decision validation, MongoDB update,
 * agent-engine resume call, Slack notification) lives in {@link ApprovalService}.</p>
 */
@RestController
@RequestMapping("/api/v1/approvals")
public class ApprovalController {

    private static final Logger log = LoggerFactory.getLogger(ApprovalController.class);

    private final ApprovalService approvalService;

    public ApprovalController(ApprovalService approvalService) {
        this.approvalService = approvalService;
    }

    /**
     * List all pending approval requests across all SDLC runs.
     *
     * <p>The approval portal polls this endpoint to render the pending approvals dashboard.
     * Returns only {@code status=pending} requests — approved and rejected requests are
     * visible in the audit trail.</p>
     *
     * @return 200 OK with list of pending {@link ApprovalRequest} documents
     */
    @GetMapping
    public ResponseEntity<List<ApprovalRequest>> getPendingApprovals() {
        log.debug("Fetching all pending approvals");
        List<ApprovalRequest> approvals = approvalService.getPendingApprovals();
        return ResponseEntity.ok(approvals);
    }

    /**
     * Submit an approval or rejection decision for a pending gate.
     *
     * <p>On success, the service:
     * <ol>
     *   <li>Updates the {@code approval_requests} MongoDB document</li>
     *   <li>POSTs the decision to the agent-engine's {@code /api/v1/runs/{runId}/resume}</li>
     *   <li>Re-subscribes to the SSE event stream so Java continues relaying events</li>
     * </ol>
     * </p>
     *
     * @param approvalId the MongoDB document ID of the pending {@link ApprovalRequest}
     * @param request    the decision body ({@code "approved"} or {@code "rejected"} + optional feedback)
     * @param jwt        the approver's JWT — Okta user ID is recorded in the audit trail
     * @return 200 OK on success
     */
    @PostMapping("/{approvalId}/decide")
    public ResponseEntity<Void> decide(
            @PathVariable String approvalId,
            @RequestBody @Valid ApprovalDecisionRequest request,
            @AuthenticationPrincipal Jwt jwt) {

        String decidedBy = jwt != null ? jwt.getSubject() : "anonymous";
        log.info("Approval decision approvalId={} decision={} decidedBy={}",
                 approvalId, request.decision(), decidedBy);

        approvalService.processDecision(approvalId, request, decidedBy);
        return ResponseEntity.ok().build();
    }
}
