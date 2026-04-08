# ADR-003: FastAPI REST + SSE over gRPC for Java-Python Bridge

**Status:** Accepted  
**Date:** 2026-04-07  
**Deciders:** Platform Architecture Team

---

## Context

The platform has two runtime processes that must communicate:

- **Java `platform-app`** (port 8080) — control plane, REST API, WebSocket to ReactJS
- **Python `agent-engine`** (port 8000) — LangGraph SDLC orchestration, CrewAI crews

Java must be able to:
1. **Start** an SDLC run in the agent-engine
2. **Receive live updates** as each agent crew completes (to relay to the ReactJS dashboard)
3. **Send human approval decisions** to resume a paused LangGraph graph

The question was: what transport protocol to use for this internal Java-Python bridge?

---

## Decision

Use **FastAPI (Python) + Spring WebClient (Java)** over **HTTP/1.1 REST** with **Server-Sent Events (SSE)** for streaming agent events.

The initial design used gRPC. It was replaced with REST + SSE.

---

## Reasons

### 1. ReactJS frontend requires HTTP/1.1

The ReactJS dashboard consumes agent events in real time. gRPC uses HTTP/2 with binary framing — browsers cannot consume gRPC streams directly without a gRPC-Web proxy (Envoy or grpc-gateway). Adding a proxy layer solely for browser compatibility adds infrastructure complexity with no other benefit.

SSE is native HTTP/1.1, natively supported by every browser, and trivially consumed by `EventSource` in ReactJS. Spring WebClient subscribes to the SSE stream from the agent-engine and forwards events over WebSocket (STOMP) to the browser — all using standard HTTP/1.1 throughout the stack.

### 2. Simpler operational model

gRPC requires:
- `.proto` schema files shared between Java and Python
- Code generation step (`protoc`) for both languages in CI
- Separate gRPC server configuration in Python
- gRPC Java stubs in `platform-app`

REST + SSE requires none of these. The contract is the JSON shape of 5 endpoints, documented in `agent-engine/README.md`. Any HTTP client can call it — `curl`, Postman, integration tests, the Java `WebClient` — without generated code.

### 3. FastAPI + SSE is purpose-built for this use case

FastAPI's `StreamingResponse` with `text/event-stream` media type is idiomatic for SSE. Per-run `asyncio.Queue` objects act as event buffers — the LangGraph background task pushes events into the queue, and the SSE generator yields them to the Java subscriber. This pattern is simple, readable, and requires no additional message broker.

### 4. Spring WebClient handles SSE natively

Spring WebFlux's `WebClient` has first-class support for consuming SSE streams:

```java
webClient.get()
    .uri("/api/v1/runs/{runId}/events", runId)
    .accept(MediaType.TEXT_EVENT_STREAM)
    .retrieve()
    .bodyToFlux(String.class)
    .subscribe(event -> broadcaster.broadcast(runId, event));
```

No additional libraries or configuration are needed. The reactive pipeline handles backpressure and reconnection automatically.

### 5. Alignment with the platform's HTTP/1.1 infrastructure

The entire platform stack (AWS ALB, GitHub Actions health checks, Okta OIDC discovery, MongoDB Atlas REST API) is HTTP/1.1. Introducing HTTP/2 binary framing for a single internal bridge would be the only non-HTTP/1.1 component in the system — an inconsistency with no benefit given the browser compatibility constraint in point 1.

---

## Bridge contract (5 endpoints)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/runs` | Java starts a new SDLC run |
| `GET` | `/api/v1/runs/{id}/events` | Java subscribes to SSE stream of agent events |
| `GET` | `/api/v1/runs/{id}/status` | Java polls current run state |
| `POST` | `/api/v1/runs/{id}/resume` | Java sends human approval decision |
| `DELETE` | `/api/v1/runs/{id}` | Java cancels a run |

---

## Consequences

### Positive
- No `.proto` files, no code generation, no gRPC-Web proxy
- SSE works natively in browsers and in Spring WebClient
- `curl` and Postman can test all endpoints directly during development
- Consistent HTTP/1.1 throughout the entire platform stack
- FastAPI Swagger UI (`/docs`) auto-documents the bridge contract

### Negative
- SSE is unidirectional (server to client) — the Java side cannot push events back to Python over the same connection (only the 5 REST endpoints allow Java -> Python communication)
- HTTP/1.1 lacks built-in multiplexing — each SSE stream holds one connection open per active run

### Mitigated by
- Java -> Python communication is inherently request/response (start run, send decision) — bidirectional streaming is not needed
- Connection-per-run is acceptable at the expected scale (tens of concurrent runs, not thousands)
- AWS ALB idle timeout is configurable to support long-lived SSE connections

---

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| gRPC (HTTP/2 binary) | Requires gRPC-Web proxy for browser consumption; `.proto` code generation in two languages; inconsistent with rest of HTTP/1.1 stack |
| Kafka / SQS (async messaging) | Adds a broker dependency for an internal process-to-process call; overkill for the volume and latency requirements of this bridge |
| WebSocket (bidirectional) | More complex than SSE for a unidirectional event stream; SSE has automatic reconnection built into the browser `EventSource` API |
| Shared MongoDB queue | Polling adds latency; MongoDB is not a message queue; creates tight coupling through the data tier |

---

## Related decisions

- [ADR-001](ADR-001-java-platform-core-over-python.md) — Java Spring Boot for platform control plane
- [ADR-002](ADR-002-python-langgraph-crewai-for-agent-orchestration.md) — Python + LangGraph + CrewAI for agent orchestration
- [ADR-004](ADR-004-three-tier-architecture-with-context-enrichment.md) — 3-tier architecture with platform-core context enrichment
