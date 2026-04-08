package com.codepil.platform.api;

import com.codepil.platform.api.dto.ApprovalDecisionRequest;
import com.codepil.platform.domain.ApprovalRequest;
import com.codepil.platform.repository.AgentRunRepository;
import com.codepil.platform.repository.ApprovalRequestRepository;
import com.codepil.platform.repository.AuditEventRepository;
import com.codepil.platform.service.ApprovalService;
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

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Unit tests for {@link ApprovalController}.
 *
 * <p>Uses {@code @WebMvcTest} — only the web layer is loaded.
 * {@link ApprovalService} is mocked with Mockito.
 * JWT authentication is simulated via {@code SecurityMockMvcRequestPostProcessors.jwt()}.
 * Authorities are set directly via {@code .authorities()} because the test JWT post processor
 * does not invoke the application's custom {@link JwtAuthenticationConverter} (which maps
 * Okta's {@code scp} claim). Using {@code .authorities()} bypasses that gap.</p>
 */
@WebMvcTest(ApprovalController.class)
@Import(SecurityConfig.class)
@ActiveProfiles("test")
@TestPropertySource(properties = {
    "spring.security.oauth2.resourceserver.jwt.jwk-set-uri=https://test.okta.example.com/oauth2/default/v1/keys",
    "OKTA_ISSUER_URI=https://test.okta.example.com/oauth2/default"
})
class ApprovalControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private ApprovalService approvalService;

    // Required because @EnableMongoRepositories on PlatformApplication is scanned
    // even in @WebMvcTest — mock them to satisfy the ApplicationContext
    @MockBean
    private AgentRunRepository agentRunRepository;
    @MockBean
    private ApprovalRequestRepository approvalRequestRepository;
    @MockBean
    private AuditEventRepository auditEventRepository;

    // -------------------------------------------------------------------------
    // GET /api/v1/approvals
    // -------------------------------------------------------------------------

    @Test
    void getPendingApprovals_withReadScope_returns200WithList() throws Exception {
        ApprovalRequest pending = new ApprovalRequest();
        pending.setRunId("run-001");
        pending.setApprovalStage("requirements");
        pending.setStatus("pending");
        pending.setArtifactSummary("12 user stories generated");

        when(approvalService.getPendingApprovals()).thenReturn(List.of(pending));

        mockMvc.perform(get("/api/v1/approvals")
                .with(jwt().jwt(jwt -> jwt.subject("okta-user-123"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:read"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].runId").value("run-001"))
                .andExpect(jsonPath("$[0].approvalStage").value("requirements"))
                .andExpect(jsonPath("$[0].status").value("pending"));
    }

    @Test
    void getPendingApprovals_withoutAuthentication_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/approvals"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getPendingApprovals_withoutReadScope_returns403() throws Exception {
        mockMvc.perform(get("/api/v1/approvals")
                .with(jwt().jwt(jwt -> jwt.subject("okta-user-123"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:run"))))   // no read scope
                .andExpect(status().isForbidden());
    }

    // -------------------------------------------------------------------------
    // POST /api/v1/approvals/{approvalId}/decide
    // -------------------------------------------------------------------------

    @Test
    void decide_withApproveScope_returns200() throws Exception {
        ApprovalDecisionRequest decision = new ApprovalDecisionRequest("approved", "Looks good");

        doNothing().when(approvalService)
                   .processDecision(eq("appr-001"), any(ApprovalDecisionRequest.class), anyString());

        mockMvc.perform(post("/api/v1/approvals/appr-001/decide")
                .with(jwt().jwt(jwt -> jwt.subject("approver-okta-id"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:approve")))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isOk());

        verify(approvalService).processDecision(
                eq("appr-001"),
                any(ApprovalDecisionRequest.class),
                eq("approver-okta-id"));
    }

    @Test
    void decide_withRejection_returns200() throws Exception {
        ApprovalDecisionRequest decision = new ApprovalDecisionRequest(
                "rejected", "Missing SAP inventory sync story");

        doNothing().when(approvalService)
                   .processDecision(anyString(), any(), anyString());

        mockMvc.perform(post("/api/v1/approvals/appr-002/decide")
                .with(jwt().jwt(jwt -> jwt.subject("approver-okta-id"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:approve")))
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isOk());
    }

    @Test
    void decide_withoutApproveScope_returns403() throws Exception {
        ApprovalDecisionRequest decision = new ApprovalDecisionRequest("approved", null);

        mockMvc.perform(post("/api/v1/approvals/appr-001/decide")
                .with(jwt().jwt(jwt -> jwt.subject("viewer-okta-id"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:read")))   // only read, not approve
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(decision)))
                .andExpect(status().isForbidden());
    }

    @Test
    void decide_withInvalidDecisionValue_returns400() throws Exception {
        String invalidJson = """
                {
                  "decision": "maybe",
                  "feedback": "not sure"
                }
                """;

        mockMvc.perform(post("/api/v1/approvals/appr-001/decide")
                .with(jwt().jwt(jwt -> jwt.subject("approver-okta-id"))
                    .authorities(new SimpleGrantedAuthority("SCOPE_agents:approve")))
                .contentType(MediaType.APPLICATION_JSON)
                .content(invalidJson))
                .andExpect(status().isBadRequest());
    }
}
