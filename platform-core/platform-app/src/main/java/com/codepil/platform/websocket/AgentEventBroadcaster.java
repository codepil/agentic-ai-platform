package com.codepil.platform.websocket;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;

/**
 * Broadcasts agent SSE events to ReactJS MFE clients via STOMP WebSocket.
 *
 * <p>This component is the bridge between the reactive SSE consumption pipeline
 * (in {@link com.codepil.platform.service.AgentRunService}) and the STOMP broker
 * configured in {@link com.codepil.platform.config.WebSocketConfig}.</p>
 *
 * <h3>WebSocket topic convention</h3>
 * <pre>
 * /topic/runs/{runId}
 * </pre>
 *
 * <p>The ReactJS {@code mfe-agent-dashboard} subscribes to this topic using:</p>
 * <pre>
 * stompClient.subscribe('/topic/runs/' + runId, (message) => {
 *   const event = JSON.parse(message.body);
 *   // render event in the pipeline viewer
 * });
 * </pre>
 *
 * <h3>Event format</h3>
 * <p>Events are forwarded as-is from the Python agent-engine SSE stream — a JSON string
 * with fields: {@code run_id}, {@code agent}, {@code event_type}, {@code payload}, {@code ts}.</p>
 */
@Component
public class AgentEventBroadcaster {

    private static final Logger log = LoggerFactory.getLogger(AgentEventBroadcaster.class);

    private static final String TOPIC_PREFIX = "/topic/runs/";

    private final SimpMessagingTemplate messagingTemplate;

    public AgentEventBroadcaster(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    /**
     * Broadcast a single agent event to all WebSocket subscribers for a run.
     *
     * <p>Sends the raw JSON event string to the STOMP topic {@code /topic/runs/{runId}}.
     * All connected ReactJS clients subscribed to this topic receive the message
     * immediately via the in-memory STOMP broker.</p>
     *
     * @param runId     the UUID of the SDLC run — determines the WebSocket topic
     * @param eventJson the raw JSON string from the SSE event stream
     */
    public void broadcast(String runId, String eventJson) {
        String destination = TOPIC_PREFIX + runId;
        try {
            messagingTemplate.convertAndSend(destination, eventJson);
            log.debug("Broadcast agent event runId={} destination={}", runId, destination);
        } catch (Exception e) {
            // Log but do not fail — if no clients are subscribed, this is expected
            log.warn("Failed to broadcast event runId={} destination={}", runId, destination, e);
        }
    }
}
