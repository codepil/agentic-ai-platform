package com.codepil.platform.repository;

import com.codepil.platform.domain.AgentRun;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Spring Data MongoDB repository for {@link AgentRun} documents.
 *
 * <p>The primary query pattern is by {@code runId} (the stable UUID), not MongoDB's
 * internal {@code _id}. Custom finders are auto-implemented by Spring Data from the
 * method name conventions.</p>
 */
@Repository
public interface AgentRunRepository extends MongoRepository<AgentRun, String> {

    /**
     * Find a run by its stable UUID (not MongoDB's internal _id).
     *
     * @param runId the UUID assigned at run creation
     * @return the run document, or empty if not found
     */
    Optional<AgentRun> findByRunId(String runId);

    /**
     * Find all runs with a given status.
     *
     * <p>Used to list all running, waiting, or completed runs for the dashboard.</p>
     *
     * @param status {@code running} | {@code waiting_approval} | {@code completed} | {@code failed} | {@code escalated}
     * @return list of matching run documents, ordered by MongoDB's natural sort
     */
    List<AgentRun> findByStatus(String status);

    /**
     * Find all runs for a specific product.
     *
     * <p>Used to show the run history for a product on the agent dashboard.</p>
     *
     * @param productId the platform product ID (e.g. {@code SelfCare-001})
     * @return list of runs for the product, all statuses
     */
    List<AgentRun> findByProductId(String productId);

    /**
     * Find all runs initiated by a specific Okta user.
     *
     * @param initiatedByUserId the Okta subject claim (user ID)
     * @return list of runs created by this user
     */
    List<AgentRun> findByInitiatedByUserId(String initiatedByUserId);
}
