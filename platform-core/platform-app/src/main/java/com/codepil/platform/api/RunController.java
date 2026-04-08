package com.codepil.platform.api;

import com.codepil.platform.api.dto.StartRunRequest;
import com.codepil.platform.api.dto.StartRunResponse;
import com.codepil.platform.api.dto.RunStatusResponse;
import com.codepil.platform.service.AgentRunService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
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
import java.util.Map;

/**
 * REST controller for SDLC run lifecycle management.
 *
 * <h3>Endpoints</h3>
 * <pre>
 * POST   /api/v1/runs              — start a new SDLC run (scope: agents:run)
 * GET    /api/v1/runs/{runId}      — get current run status (scope: agents:read)
 * GET    /api/v1/runs/{runId}/artifacts — list generated artifacts (scope: agents:read)
 * </pre>
 *
 * <p>This controller is intentionally thin — all business logic lives in
 * {@link AgentRunService}. The controller is responsible only for:
 * <ul>
 *   <li>Deserialising and validating the request body</li>
 *   <li>Enforcing the required OAuth2 scope via {@code @PreAuthorize}</li>
 *   <li>Delegating to the service</li>
 *   <li>Returning the correct HTTP status code</li>
 * </ul>
 * </p>
 */
@RestController
@RequestMapping("/api/v1/runs")
public class RunController {

    private static final Logger log = LoggerFactory.getLogger(RunController.class);

    private final AgentRunService agentRunService;

    public RunController(AgentRunService agentRunService) {
        this.agentRunService = agentRunService;
    }

    /**
     * Start a new SDLC run for a given Jira epic.
     *
     * <p>Returns HTTP 202 Accepted immediately — the run executes asynchronously.
     * Callers should subscribe to {@code /topic/runs/{runId}} via WebSocket to receive
     * live agent events, or poll {@code GET /api/v1/runs/{runId}} for status.</p>
     *
     * @param request  the run configuration (jiraEpicId, productId, figmaUrl, etc.)
     * @param jwt      the authenticated user's JWT — used to extract the initiating user ID
     * @return 202 Accepted with run ID and initial status
     */
    @PostMapping
    public ResponseEntity<StartRunResponse> startRun(
            @RequestBody @Valid StartRunRequest request,
            @AuthenticationPrincipal Jwt jwt) {

        String userId = jwt != null ? jwt.getSubject() : "anonymous";
        log.info("Start run requested by userId={} jiraEpicId={} productId={}",
                 userId, request.jiraEpicId(), request.productId());

        StartRunResponse response = agentRunService.startRun(request, userId);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
    }

    /**
     * Get the current status of an SDLC run.
     *
     * <p>Merges persisted MongoDB state with a live status call to the agent-engine.
     * Returns the current SDLC stage, LangGraph next nodes, QA iteration count,
     * LLM token usage, and any errors.</p>
     *
     * @param runId the run UUID returned by {@code POST /api/v1/runs}
     * @return 200 OK with run status details, or 404 if run not found
     */
    @GetMapping("/{runId}")
    public ResponseEntity<RunStatusResponse> getRunStatus(@PathVariable String runId) {
        log.debug("Run status requested runId={}", runId);
        RunStatusResponse response = agentRunService.getRunStatus(runId);
        return ResponseEntity.ok(response);
    }

    /**
     * List SDLC artifacts produced by a run.
     *
     * <p>Returns metadata for all generated artifacts (Java services, React components,
     * OpenAPI specs, test suites, ADRs, pipeline YAML). Artifact content can be fetched
     * from the SDLCArtifact collection via the artifact ID.</p>
     *
     * @param runId the run UUID
     * @return 200 OK with list of artifact metadata maps
     */
    @GetMapping("/{runId}/artifacts")
    public ResponseEntity<List<Map<String, Object>>> getArtifacts(@PathVariable String runId) {
        log.debug("Artifacts requested runId={}", runId);
        List<Map<String, Object>> artifacts = agentRunService.getArtifacts(runId);
        return ResponseEntity.ok(artifacts);
    }
}
