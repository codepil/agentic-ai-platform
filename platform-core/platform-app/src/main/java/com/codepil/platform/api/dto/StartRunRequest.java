package com.codepil.platform.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;

/**
 * Request body for {@code POST /api/v1/runs}.
 *
 * <p>All fields are passed through to the Python agent-engine when starting a new SDLC run.
 * The {@code jiraEpicId} and {@code productId} are mandatory; Figma URL and PRD S3 URL are
 * optional — the Requirements Crew works with whatever inputs are provided.</p>
 *
 * @param jiraEpicId      Jira epic key identifying the feature to build (e.g. {@code SC-42})
 * @param productId       Platform product identifier (e.g. {@code SelfCare-001})
 * @param figmaUrl        Optional Figma design file URL for the React Developer agent
 * @param prdS3Url        Optional S3 URI to the PRD document (e.g. {@code s3://bucket/prd.pdf})
 * @param maxQaIterations Maximum QA retry cycles before escalating to a human (default: 3)
 */
public record StartRunRequest(

        @NotBlank(message = "jiraEpicId is required")
        String jiraEpicId,

        @NotBlank(message = "productId is required")
        String productId,

        String figmaUrl,

        String prdS3Url,

        @Positive(message = "maxQaIterations must be at least 1")
        int maxQaIterations

) {}
