package com.codepil.platform.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;

/**
 * Service for sending Slack notifications at human gate checkpoints and on agent failures.
 *
 * <p>Uses Slack Incoming Webhooks for simplicity — no Slack SDK dependency required.
 * Notifications are fire-and-forget (non-blocking): failures are logged but do not
 * propagate as exceptions because Slack is a notification channel, not a critical path.</p>
 *
 * <h3>When notifications are sent</h3>
 * <ul>
 *   <li>{@code notifyApprover} — called when an {@code approval_requested} SSE event arrives.
 *       Message goes to the approver channel with run details and artifact summary.</li>
 *   <li>{@code alertOncall} — called when the SSE stream disconnects or the agent-engine
 *       rejects a run. Message goes to the on-call channel.</li>
 * </ul>
 *
 * <p>If {@code SLACK_WEBHOOK_URL} is empty (default in local dev), all notifications
 * are silently skipped and logged at DEBUG level.</p>
 */
@Service
public class SlackNotificationService {

    private static final Logger log = LoggerFactory.getLogger(SlackNotificationService.class);

    private final String webhookUrl;
    private final String oncallChannel;
    private final WebClient slackWebClient;

    public SlackNotificationService(
            @Value("${slack.webhook-url:}") String webhookUrl,
            @Value("${slack.oncall-channel:#platform-oncall}") String oncallChannel) {
        this.webhookUrl = webhookUrl;
        this.oncallChannel = oncallChannel;
        this.slackWebClient = WebClient.builder().build();
    }

    /**
     * Notify the approver channel that a human gate is waiting for a decision.
     *
     * <p>The message includes the run ID, approval stage, and an artifact summary
     * so the approver can make an informed decision without needing to log into
     * the platform UI.</p>
     *
     * @param runId           the UUID of the SDLC run
     * @param stage           the approval gate stage ({@code requirements} or {@code staging})
     * @param artifactSummary human-readable summary of what needs review
     */
    public void notifyApprover(String runId, String stage, String artifactSummary) {
        if (webhookUrl == null || webhookUrl.isBlank()) {
            log.debug("Slack webhook not configured — skipping approver notification runId={}", runId);
            return;
        }

        String text = String.format(
            ":robot_face: *SDLC Approval Required*\n" +
            "*Run:* `%s`\n" +
            "*Gate:* `%s`\n" +
            "*Summary:* %s\n\n" +
            "Review and approve at the platform approval portal.",
            runId, stage, artifactSummary
        );

        sendSlackMessage(text);
        log.info("Slack approver notification sent runId={} stage={}", runId, stage);
    }

    /**
     * Alert the on-call channel when an agent run fails unexpectedly.
     *
     * @param runId        the UUID of the SDLC run
     * @param errorMessage description of the failure
     */
    public void alertOncall(String runId, String errorMessage) {
        if (webhookUrl == null || webhookUrl.isBlank()) {
            log.debug("Slack webhook not configured — skipping oncall alert runId={}", runId);
            return;
        }

        String text = String.format(
            ":rotating_light: *Agent Run Failed*\n" +
            "*Run:* `%s`\n" +
            "*Channel:* %s\n" +
            "*Error:* %s",
            runId, oncallChannel, errorMessage
        );

        sendSlackMessage(text);
        log.warn("Slack oncall alert sent runId={}", runId);
    }

    /**
     * Send a message to the configured Slack Incoming Webhook URL.
     *
     * <p>Fire-and-forget — errors are logged but not propagated.</p>
     *
     * @param text the Slack message text (supports Slack mrkdwn formatting)
     */
    private void sendSlackMessage(String text) {
        Map<String, String> payload = Map.of("text", text);

        slackWebClient.post()
                .uri(webhookUrl)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(payload)
                .retrieve()
                .bodyToMono(String.class)
                .subscribe(
                    response -> log.debug("Slack message sent successfully"),
                    error -> log.error("Failed to send Slack message", error)
                );
    }
}
