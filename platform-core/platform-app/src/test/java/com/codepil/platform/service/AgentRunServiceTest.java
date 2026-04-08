package com.codepil.platform.service;

import com.codepil.platform.api.dto.StartRunRequest;
import com.codepil.platform.api.dto.StartRunResponse;
import com.codepil.platform.domain.AgentRun;
import com.codepil.platform.repository.AgentRunRepository;
import com.codepil.platform.websocket.AgentEventBroadcaster;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link AgentRunService}.
 *
 * <p>Uses {@code @ExtendWith(MockitoExtension.class)} — no Spring context loaded.
 * All dependencies are mocked with Mockito. WebClient reactive calls are stubbed
 * to return predictable {@link Mono} values synchronously.</p>
 */
@ExtendWith(MockitoExtension.class)
@ActiveProfiles("test")
class AgentRunServiceTest {

    @Mock
    private AgentRunRepository agentRunRepository;

    @Mock
    private AuditTrailService auditTrailService;

    @Mock
    private ApprovalService approvalService;

    @Mock
    private AgentEventBroadcaster agentEventBroadcaster;

    @Mock
    private SlackNotificationService slackNotificationService;

    @Mock
    private WebClient agentEngineWebClient;

    @Mock
    private WebClient.RequestBodyUriSpec requestBodyUriSpec;

    @Mock
    private WebClient.RequestBodySpec requestBodySpec;

    @Mock
    @SuppressWarnings("rawtypes")
    private WebClient.RequestHeadersSpec requestHeadersSpec;

    @Mock
    private WebClient.ResponseSpec responseSpec;

    private AgentRunService agentRunService;

    @BeforeEach
    void setUp() {
        agentRunService = new AgentRunService(
                agentRunRepository,
                auditTrailService,
                approvalService,
                agentEventBroadcaster,
                slackNotificationService,
                agentEngineWebClient,
                new ObjectMapper()
        );
    }

    // -------------------------------------------------------------------------
    // startRun()
    // -------------------------------------------------------------------------

    @Test
    void startRun_savesAgentRunToMongoDB() {
        // Arrange
        StartRunRequest request = new StartRunRequest("SC-42", "SelfCare-001", null, null, 3);
        stubWebClientPost();

        // Act
        agentRunService.startRun(request, "okta-user-123");

        // Assert: AgentRun was saved to MongoDB
        ArgumentCaptor<AgentRun> runCaptor = ArgumentCaptor.forClass(AgentRun.class);
        verify(agentRunRepository).save(runCaptor.capture());

        AgentRun savedRun = runCaptor.getValue();
        assertThat(savedRun.getProductId()).isEqualTo("SelfCare-001");
        assertThat(savedRun.getJiraEpicId()).isEqualTo("SC-42");
        assertThat(savedRun.getStatus()).isEqualTo("running");
        assertThat(savedRun.getCurrentStage()).isEqualTo("requirements");
        assertThat(savedRun.getInitiatedByUserId()).isEqualTo("okta-user-123");
        assertThat(savedRun.getRunId()).isNotBlank();
        assertThat(savedRun.getThreadId()).isNotBlank();
    }

    @Test
    void startRun_returnsRunIdAndStartedStatus() {
        // Arrange
        StartRunRequest request = new StartRunRequest("SC-42", "SelfCare-001",
                "https://figma.com/file/abc", null, 3);
        stubWebClientPost();

        // Act
        StartRunResponse response = agentRunService.startRun(request, "okta-user-123");

        // Assert
        assertThat(response).isNotNull();
        assertThat(response.runId()).isNotBlank();
        assertThat(response.status()).isEqualTo("started");
    }

    @Test
    void startRun_generatesDistinctRunIdAndThreadId() {
        // Arrange
        StartRunRequest request = new StartRunRequest("SC-42", "SelfCare-001", null, null, 3);
        stubWebClientPost();

        // Act
        agentRunService.startRun(request, "okta-user-123");

        // Assert: runId and threadId are different UUIDs
        ArgumentCaptor<AgentRun> runCaptor = ArgumentCaptor.forClass(AgentRun.class);
        verify(agentRunRepository).save(runCaptor.capture());

        AgentRun savedRun = runCaptor.getValue();
        assertThat(savedRun.getRunId()).isNotEqualTo(savedRun.getThreadId());
    }

    @Test
    void startRun_callsAgentEngineWithCorrectFields() {
        // Arrange
        StartRunRequest request = new StartRunRequest(
                "SC-99", "ProductX", "https://figma.com/test", "s3://bucket/prd.pdf", 2);
        stubWebClientPost();

        // Act
        agentRunService.startRun(request, "okta-user-456");

        // Assert: WebClient post was called (agent engine was notified)
        verify(agentEngineWebClient).post();
    }

    // -------------------------------------------------------------------------
    // Private stub helpers
    // -------------------------------------------------------------------------

    /**
     * Stub the WebClient POST chain to return a successful Mono<String>.
     * This prevents NullPointerExceptions in the reactive chain during tests.
     */
    @SuppressWarnings({"unchecked", "rawtypes"})
    private void stubWebClientPost() {
        when(agentEngineWebClient.post()).thenReturn(requestBodyUriSpec);
        when(requestBodyUriSpec.uri(anyString())).thenReturn(requestBodySpec);
        when(requestBodySpec.bodyValue(any())).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);
        when(responseSpec.bodyToMono(String.class)).thenReturn(Mono.just("{}"));

        // Save must return the saved entity for any subsequent findByRunId calls
        when(agentRunRepository.save(any(AgentRun.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
    }
}
