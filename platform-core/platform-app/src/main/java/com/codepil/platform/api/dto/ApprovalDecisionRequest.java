package com.codepil.platform.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

/**
 * Request body for {@code POST /api/v1/approvals/{approvalId}/decide}.
 *
 * <p>Submitted by a human approver (operator, PM, or stakeholder) to approve or reject
 * an agent crew's output at a human gate checkpoint. The decision is persisted to MongoDB,
 * forwarded to the agent-engine's {@code /api/v1/runs/{runId}/resume} endpoint, and logged
 * in the audit trail with the approver's Okta user ID.</p>
 *
 * @param decision {@code "approved"} to allow the SDLC to proceed;
 *                 {@code "rejected"} to send the output back with feedback
 * @param feedback Optional human-readable feedback — required when decision is {@code "rejected"}
 *                 so the agent crew knows what to fix
 */
public record ApprovalDecisionRequest(

        @NotBlank(message = "decision is required")
        @Pattern(regexp = "approved|rejected", message = "decision must be 'approved' or 'rejected'")
        String decision,

        String feedback

) {}
