package com.codepil.platform.repository;

import com.codepil.platform.domain.ApprovalRequest;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Spring Data MongoDB repository for {@link ApprovalRequest} documents.
 *
 * <p>Supports the two primary query patterns for the approval portal:
 * <ul>
 *   <li>Find all pending approvals (for the dashboard list)</li>
 *   <li>Find a specific approval for a run at a given stage (to prevent duplicate approvals)</li>
 * </ul>
 * </p>
 */
@Repository
public interface ApprovalRequestRepository extends MongoRepository<ApprovalRequest, String> {

    /**
     * Find the approval request for a specific run and stage with a given status.
     *
     * <p>Used to look up the pending approval when processing a decision, and to
     * check whether an approval gate has already been opened for a run+stage combination.</p>
     *
     * @param runId  the UUID of the SDLC run
     * @param status {@code pending} | {@code approved} | {@code rejected}
     * @return matching approval requests (should typically be 0 or 1)
     */
    List<ApprovalRequest> findByRunIdAndStatus(String runId, String status);

    /**
     * Find all approval requests with a given status across all runs.
     *
     * <p>The primary query for the approval portal dashboard — returns all {@code pending}
     * approvals that need human attention.</p>
     *
     * @param status {@code pending} | {@code approved} | {@code rejected}
     * @return all matching approval requests
     */
    List<ApprovalRequest> findByStatus(String status);

    /**
     * Find the approval request for a run at a specific stage.
     *
     * <p>Uses an explicit MongoDB query to avoid ambiguity when both fields are combined.
     * Called by {@link com.codepil.platform.service.ApprovalService} when re-querying
     * after a resume to confirm state.</p>
     *
     * @param runId         the UUID of the SDLC run
     * @param approvalStage {@code requirements} | {@code staging}
     * @return the approval request, or empty if none exists
     */
    @Query("{ 'runId': ?0, 'approvalStage': ?1 }")
    Optional<ApprovalRequest> findByRunIdAndApprovalStage(String runId, String approvalStage);

    /**
     * Find all approval requests for a run, ordered by creation time.
     *
     * <p>Used to display the approval history for a run in the audit log.</p>
     *
     * @param runId the UUID of the SDLC run
     * @return all approval requests for the run
     */
    List<ApprovalRequest> findByRunId(String runId);
}
