package com.codepil.platform.api;

import com.codepil.platform.api.dto.StartRunRequest;
import com.codepil.platform.api.dto.StartRunResponse;
import com.codepil.platform.api.dto.RunStatusResponse;
import com.codepil.platform.repository.AgentRunRepository;
import com.codepil.platform.repository.ApprovalRequestRepository;
import com.codepil.platform.repository.AuditEventRepository;
import com.codepil.platform.service.AgentRunService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import com.codepil.platform.config.SecurityConfig;
import org.springframework.context.annotation.Import;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Unit tests for {@link RunController}.
 *
 * <p>Uses {@code @WebMvcTest} which loads only the web layer — Spring Security filter chain,
 * the controller, and message converters. The service layer is fully mocked with Mockito.
 * JWT authentication is simulated using {@code SecurityMockMvcRequestPostProcessors.jwt()}.
 * Authorities are set directly via {@code .authorities()} because the test JWT post processor
 * does not invoke the application's custom {@link JwtAuthenticationConverter} (which maps
 * Okta's {@code scp} claim). Using {@code .authorities()} bypasses that gap.</p>
 */
@WebMvcTest(RunController.class)
@Import(SecurityConfig.class)
@ActiveProfiles("test")
@TestPropertySource(properties = {
    "spring.security.oauth2.resourceserver.jwt.jwk-set-uri=https://test.okta.example.com/oauth2/default/v1/keys",
    "OKTA_ISSUER_URI=https://test.okta.example.com/oauth2/default"
})
class RunControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private AgentRunService agentRunService;

    // Required because @EnableMongoRepositories on PlatformApplication is scanned
    // even in @WebMvcTest — mock them to satisfy the ApplicationContext
    @MockBean
    private AgentRunRepository agentRunRepository;
    @MockBean
    private ApprovalRequestRepository approvalRequestRepository;
    @MockBean
    private AuditEventRepository auditEventRepository;

    // -------------------------------------------------------------------------
    // POST /api/v1/runs
    // -------------------------------------------------------------------------

    @Test
    void startRun_withValidRequestAndCorrectScope_returns202() throws Exception {
        StartRunRequest request = new StartRunRequest("SC-42", "SelfCare-001", null, null, 3);
        StartRunResponse response = new StartRunResponse("test-run-id-001", "started");

        when(agentRunService.startRun(any(StartRunRequest.class), anyString()))
                .thenReturn(response);

        mockMvc.perform(post("/api/v1/runs")
                .with(jwt().jwt(jwt -> jwt.subject("okta-user-123"))
                    .authorities(
                        new SimpleGrantedAuthority("SCOPE_agents:run"),
                        new SimpleGrantedAuthority("SCOPE_agents:read")))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.runId").value("test-run-id-001"))
                .andExpect(jsonPath("$.status").value("started"));
    }

    @Test
    void startRun_withoutAgentsRunScope_returns403() throws Exception {
        StartRunRequest request = new StartRunRequest("SC-42", "SelfCare-001", null, null, 3);

        mockMvc.perform(post("/api/v1/runs")
                .with(jwt().jwt(jwt -> jwt.subject("okta-viewer-user"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:read")))   // no run scope
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isForbidden());
    }

    @Test
    void startRun_withoutAuthentication_returns401() throws Exception {
        StartRunRequest request = new StartRunRequest("SC-42", "SelfCare-001", null, null, 3);

        mockMvc.perform(post("/api/v1/runs")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void startRun_withMissingJiraEpicId_returns400() throws Exception {
        // jiraEpicId is blank — validation should fail with 400
        String badJson = """
                {
                  "jiraEpicId": "",
                  "productId": "SelfCare-001",
                  "maxQaIterations": 3
                }
                """;

        mockMvc.perform(post("/api/v1/runs")
                .with(jwt().jwt(jwt -> jwt.subject("okta-user-123"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:run")))
                .contentType(MediaType.APPLICATION_JSON)
                .content(badJson))
                .andExpect(status().isBadRequest());
    }

    // -------------------------------------------------------------------------
    // GET /api/v1/runs/{runId}
    // -------------------------------------------------------------------------

    @Test
    void getRunStatus_withReadScope_returns200() throws Exception {
        RunStatusResponse statusResponse = new RunStatusResponse(
                "test-run-id-001", "requirements", List.of("architecture_crew"),
                0, Map.of("input_tokens", 1000), List.of()
        );

        when(agentRunService.getRunStatus("test-run-id-001")).thenReturn(statusResponse);

        mockMvc.perform(get("/api/v1/runs/test-run-id-001")
                .with(jwt().jwt(jwt -> jwt.subject("okta-user-123"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:read"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.runId").value("test-run-id-001"))
                .andExpect(jsonPath("$.currentStage").value("requirements"))
                .andExpect(jsonPath("$.nextNodes[0]").value("architecture_crew"));
    }

    @Test
    void getRunStatus_withoutAuthentication_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/runs/any-run-id"))
                .andExpect(status().isUnauthorized());
    }

    // -------------------------------------------------------------------------
    // GET /api/v1/runs/{runId}/artifacts
    // -------------------------------------------------------------------------

    @Test
    void getArtifacts_withReadScope_returns200WithList() throws Exception {
        List<Map<String, Object>> artifacts = List.of(
                Map.of("artifact_id", "art-001", "type", "java_service")
        );

        when(agentRunService.getArtifacts("test-run-id-001")).thenReturn(artifacts);

        mockMvc.perform(get("/api/v1/runs/test-run-id-001/artifacts")
                .with(jwt().jwt(jwt -> jwt.subject("okta-user-123"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:read"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].artifact_id").value("art-001"))
                .andExpect(jsonPath("$[0].type").value("java_service"));
    }
}
