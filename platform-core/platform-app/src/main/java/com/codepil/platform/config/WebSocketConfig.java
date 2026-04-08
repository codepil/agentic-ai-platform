package com.codepil.platform.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

/**
 * STOMP WebSocket configuration for real-time agent event streaming to the ReactJS MFE.
 *
 * <h3>Architecture</h3>
 * <pre>
 * Python agent-engine (FastAPI SSE)
 *         |
 *         v
 * AgentRunService.subscribeToEventStream()  -- WebClient SSE consumer
 *         |
 *         v
 * AgentEventBroadcaster.broadcast(runId, eventJson)
 *         |
 *         v
 * SimpMessagingTemplate.convertAndSend("/topic/runs/{runId}", payload)
 *         |
 *         v  [STOMP over WebSocket / SockJS]
 * ReactJS MFE (mfe-agent-dashboard)
 *   stompClient.subscribe('/topic/runs/{runId}', handler)
 * </pre>
 *
 * <h3>Destinations</h3>
 * <ul>
 *   <li>{@code /topic/runs/{runId}} — server-to-client broadcast (agent events)</li>
 *   <li>{@code /app/...} — client-to-server messages (not currently used by the MFE)</li>
 * </ul>
 */
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    /**
     * Configures the in-memory STOMP message broker.
     *
     * <ul>
     *   <li>{@code /topic} prefix — server-to-client push subscriptions</li>
     *   <li>{@code /app} prefix — client-to-server message routing (via @MessageMapping)</li>
     * </ul>
     */
    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        registry.enableSimpleBroker("/topic");
        registry.setApplicationDestinationPrefixes("/app");
    }

    /**
     * Registers the STOMP endpoint.
     *
     * <p>ReactJS connects to {@code ws://host:8080/ws} (native WebSocket) or falls
     * back to SockJS HTTP long-polling when WebSocket is unavailable.</p>
     *
     * <p>In production, the CORS origin should be locked down to the MFE shell origin.
     * For now {@code *} is used to simplify local development.</p>
     */
    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws")
                .setAllowedOriginPatterns("*")
                .withSockJS();
    }
}
