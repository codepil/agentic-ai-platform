package com.codepil.platform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.mongodb.repository.config.EnableMongoRepositories;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * Entry point for the Platform Core Spring Boot application.
 *
 * <p>This application is the Java control plane for the agentic AI platform.
 * It exposes REST endpoints and WebSocket (STOMP) for the ReactJS MFE shell,
 * communicates with the Python agent-engine via REST + SSE, and persists
 * run state, audit events, and approval requests to MongoDB Atlas.</p>
 *
 * <p>Required environment variables:
 * <ul>
 *   <li>{@code OKTA_ISSUER_URI} — Okta authorization server issuer URI (mandatory)</li>
 *   <li>{@code MONGO_URI} — MongoDB connection string (default: localhost)</li>
 *   <li>{@code AGENT_ENGINE_BASE_URL} — Python FastAPI base URL (default: localhost:8000)</li>
 *   <li>{@code SLACK_WEBHOOK_URL} — Slack Incoming Webhook URL (optional)</li>
 * </ul>
 * </p>
 */
@SpringBootApplication
@EnableMongoRepositories(basePackages = "com.codepil.platform.repository")
@EnableAsync
public class PlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(PlatformApplication.class, args);
    }
}
