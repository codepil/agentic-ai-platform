package com.codepil.platform.api.dto;

import java.util.List;
import java.util.Map;

/**
 * Response body for {@code GET /api/v1/runs/{runId}}.
 *
 * <p>Merges data from two sources:
 * <ol>
 *   <li>The {@code agent_runs} MongoDB document — persisted state managed by Java</li>
 *   <li>A live call to the agent-engine's {@code GET /api/v1/runs/{runId}/status} endpoint
 *       — provides the current LangGraph node and next potential nodes</li>
 * </ol>
 * </p>
 *
 * @param runId        UUID of the SDLC run
 * @param currentStage Current SDLC stage name (e.g. {@code requirements}, {@code dev})
 * @param nextNodes    LangGraph nodes that will execute after the current node completes
 * @param qaIteration  Number of QA retry cycles completed so far (0-based)
 * @param llmUsage     Token usage and cost breakdown from the agent-engine
 *                     (keys: {@code input_tokens}, {@code output_tokens}, {@code cost_usd})
 * @param errors       List of error messages from failed stages or tool calls
 */
public record RunStatusResponse(
        String runId,
        String currentStage,
        List<String> nextNodes,
        int qaIteration,
        Map<String, Object> llmUsage,
        List<String> errors
) {}
