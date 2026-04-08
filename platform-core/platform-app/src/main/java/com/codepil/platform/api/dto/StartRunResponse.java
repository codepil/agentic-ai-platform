package com.codepil.platform.api.dto;

/**
 * Response body for {@code POST /api/v1/runs} — returned with HTTP 202 Accepted.
 *
 * <p>Callers should use the {@code runId} to:
 * <ul>
 *   <li>Subscribe to the STOMP topic {@code /topic/runs/{runId}} for live events</li>
 *   <li>Poll {@code GET /api/v1/runs/{runId}} for current status</li>
 * </ul>
 * </p>
 *
 * @param runId  UUID assigned to this SDLC run by the Java control plane
 * @param status Initial status — always {@code "started"} on successful creation
 */
public record StartRunResponse(String runId, String status) {}
