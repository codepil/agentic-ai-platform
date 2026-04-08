# ADR-001: Java Spring Boot for Platform Control Plane

**Status:** Accepted  
**Date:** 2026-04-07  
**Deciders:** Platform Architecture Team

---

## Context

The agentic AI platform has two distinct runtime components:

1. **Agent Engine** — Python service running LangGraph + CrewAI for AI/LLM orchestration
2. **Platform Control Plane** — serves the user-facing REST API, enforces Okta JWT auth, manages MongoDB state, and relays agent events to the ReactJS frontend over WebSocket

The question was: should the control plane be written in **Python** (same as the agent engine) or **Java Spring Boot**?

---

## Decision

Use **Java 25 + Spring Boot 3.4** for the platform control plane (`platform-core`).

Python remains the exclusive language for the agent engine (`agent-engine`). The boundary between the two is a clean REST + SSE interface (FastAPI on the Python side, Spring WebClient on the Java side).

---

## Reasons

### 1. SAP integration requires Java

The client's self-care products integrate with SAP via RFC/BAPI calls. The official **SAP Java Connector (JCo)** is the only production-grade SAP connector available. There is no equivalent Python library for enterprise SAP integration at scale. The `lib-sap` shared library (`SapBapiClient`, `SapODataClient`) was written in Java for this reason.

### 2. Matches the client's existing technology stack

The client's product services are Java/Spring Boot. Using Java for the platform control plane means:
- Same deployment pipeline (Docker, ECS/EKS, GitHub Actions)
- Same observability stack (Spring Actuator + Micrometer -> CloudWatch)
- Same developer skillset — Java engineers can contribute to both platform and product services without context switching
- Shared libraries (`lib-auth`, `lib-mongodb`, `lib-sap`) can be reused across all services in the ecosystem

### 3. Separation of concerns with a clean contract

Python handles what it does best: AI orchestration, LLM calls, LangGraph state machines, CrewAI crews.  
Java handles what it does best: enterprise REST APIs, OAuth2/JWT security, reactive WebClient, WebSocket (STOMP).

If both were Python, the agent-engine FastAPI server would be responsible for both SDLC orchestration (CPU/memory intensive) and user-facing API serving (I/O bound) — two very different scaling profiles in a single process with no clean boundary to test or replace either side independently.

### 4. Spring Security + Okta is production-grade

The platform enforces Okta JWT OAuth2 with scope-based access control (`agents:run`, `agents:read`, `agents:approve`, `admin:manage`). Spring Security's OAuth2 Resource Server support, `BearerTokenAuthenticationEntryPoint`, and `authorizeHttpRequests()` DSL provide enterprise-grade security with minimal boilerplate. The Python equivalent (fastapi-security, python-jose) is thinner and less battle-tested in enterprise Okta deployments.

### 5. Spring WebFlux handles concurrent SSE + WebSocket cleanly

The platform-app must:
- Serve many ReactJS users simultaneously via REST and WebSocket
- Subscribe to multiple long-lived SSE streams from the agent-engine (one per active SDLC run)
- Write audit events asynchronously without blocking request threads

Spring WebFlux + Spring WebClient handles all of this non-blockingly on the Netty event loop. Mixing synchronous MongoDB writes with async SSE streaming in a single Python FastAPI process is more error-prone under production load.

### 6. Java platform-core provides authentic few-shot examples for Dev Crew

The Dev Crew's Java Developer agent uses `_PLATFORM_CORE_SNIPPETS` — actual controller, service, repository, and DTO code from `platform-core` — as few-shot examples injected into its backstory. This ensures the AI-generated product service code follows the same conventions as the handwritten platform code.

If platform-core were Python, the Dev Crew would have Python patterns available for few-shot injection but would be asked to generate Java for the self-care product services — a mismatch. Java platform-core gives the agent **authentic few-shot examples in the target language**.

---

## Consequences

### Positive
- Enterprise-grade SAP integration via JCo from day one
- Full Spring Security OAuth2 resource server with Okta JWT
- Reactive WebClient + WebSocket on proven Netty infrastructure
- Shared Java libs (`lib-auth`, `lib-mongodb`, `lib-logging`, `lib-sap`) reusable across all product services
- Java Developer agent in Dev Crew has authentic same-language coding standards to follow
- Independent scaling: agent-engine (GPU/compute heavy) and platform-app (I/O heavy) scale separately

### Negative
- Two languages to maintain (Python + Java)
- Two build systems (pip/pytest + Maven/JUnit)
- Engineers need familiarity with both ecosystems

### Mitigated by
- The REST + SSE boundary between the two components is narrow and well-defined (5 endpoints)
- The agent-engine is self-contained and can be deployed, tested, and scaled independently
- Java is already the client's standard for product services, so no new language is being introduced to the organisation

---

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Python (FastAPI) for control plane | No production SAP JCo connector; thinner OAuth2/Okta support; no clean separation of AI orchestration vs API serving |
| Node.js for control plane | No SAP JCo; not aligned with client's Java skillset; weaker MongoDB + security ecosystem |
| Single Python monolith (agent engine + control plane) | Single process handles both LLM calls and user API — different scaling profiles; no clean boundary for independent testing or replacement |

---

## Related decisions

- ADR-002 (planned): Python + LangGraph + CrewAI for agent orchestration
- ADR-003 (planned): FastAPI REST + SSE over gRPC for agent-engine bridge
