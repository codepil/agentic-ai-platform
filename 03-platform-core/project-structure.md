# Platform-Core — Project Structure & Standards

> **Scope:** Java Spring Boot control plane, coding standards for agent-generated code, shared Java libraries.

---

## Section A — Control Plane (`platform-app`)

### What It Is

`platform-app` is the Java Spring Boot 3.2 application that forms the **control plane** of the agentic AI platform. It is the single entry point for:

- **Operators and administrators** who trigger SDLC runs, monitor progress, and approve human gates.
- **The ReactJS MFE shell and micro-frontends** (`mfe-agent-dashboard`, `mfe-approval-portal`, `mfe-audit-logs`) that render real-time agent activity and approval UIs.

The app has three core responsibilities:

1. **Orchestrate SDLC runs** — accept run requests, forward them to the Python agent-engine (FastAPI) via Spring WebClient, and subscribe to the SSE event stream.
2. **Stream events to the browser** — consume the SSE stream from Python and re-broadcast each event to ReactJS over STOMP WebSocket.
3. **Manage human approval gates** — pause a run at a gate, notify approvers via Slack, and resume the run when a decision is made.

---

### Maven Multi-Module Project Structure

```
platform-core/                              ← parent POM
├── pom.xml
│
├── platform-app/                           ← runnable Spring Boot app
│   ├── pom.xml
│   └── src/
│       ├── main/
│       │   ├── java/com/codepil/platform/
│       │   │   ├── PlatformApplication.java
│       │   │   ├── config/
│       │   │   │   ├── SecurityConfig.java
│       │   │   │   ├── WebSocketConfig.java
│       │   │   │   └── WebClientConfig.java
│       │   │   ├── api/
│       │   │   │   ├── RunController.java
│       │   │   │   ├── ApprovalController.java
│       │   │   │   └── dto/
│       │   │   │       ├── StartRunRequest.java
│       │   │   │       ├── StartRunResponse.java
│       │   │   │       ├── ApprovalDecisionRequest.java
│       │   │   │       └── RunStatusResponse.java
│       │   │   ├── service/
│       │   │   │   ├── AgentRunService.java
│       │   │   │   ├── ApprovalService.java
│       │   │   │   ├── AuditTrailService.java
│       │   │   │   └── SlackNotificationService.java
│       │   │   ├── domain/
│       │   │   │   ├── AgentRun.java
│       │   │   │   ├── AuditEvent.java
│       │   │   │   └── ApprovalRequest.java
│       │   │   ├── repository/
│       │   │   │   ├── AgentRunRepository.java
│       │   │   │   ├── AuditEventRepository.java
│       │   │   │   └── ApprovalRequestRepository.java
│       │   │   └── websocket/
│       │   │       └── AgentEventBroadcaster.java
│       │   └── resources/
│       │       └── application.yml
│       └── test/
│           └── java/com/codepil/platform/
│               ├── api/
│               │   ├── RunControllerTest.java
│               │   └── ApprovalControllerTest.java
│               └── service/
│                   └── AgentRunServiceTest.java
│
└── shared-java-libs/
    ├── lib-auth/
    │   ├── pom.xml
    │   └── src/main/java/com/codepil/platform/auth/
    │       ├── OktaJwtValidator.java
    │       ├── PlatformSecurityContext.java
    │       └── RequiresScope.java
    ├── lib-mongodb/
    │   ├── pom.xml
    │   └── src/main/java/com/codepil/platform/mongodb/
    │       ├── MongoConfig.java
    │       └── BaseDocument.java
    ├── lib-logging/
    │   ├── pom.xml
    │   └── src/main/java/com/codepil/platform/logging/
    │       ├── MdcFilter.java
    │       └── PlatformLogger.java
    └── lib-sap/
        ├── pom.xml
        └── src/main/java/com/codepil/platform/sap/
            ├── SapODataClient.java
            ├── SapBapiClient.java
            └── SapClientProperties.java
```

---

### Package Layout Conventions

| Package | Layer | Role |
|---------|-------|------|
| `com.codepil.platform` | Root | `PlatformApplication` only — entry point |
| `com.codepil.platform.config` | Config | Spring `@Configuration` beans — security, WebSocket, WebClient |
| `com.codepil.platform.api` | Controller | Thin REST controllers, `@RestController`, `@RequestMapping` |
| `com.codepil.platform.api.dto` | DTO | Java 21 `record` classes — request/response shapes, no domain leakage |
| `com.codepil.platform.service` | Service | Business logic, `@Service`, `@Transactional` where needed |
| `com.codepil.platform.domain` | Domain | MongoDB `@Document` entities — mutable, getters/setters, extends `BaseDocument` |
| `com.codepil.platform.repository` | Repository | `MongoRepository<T, String>` interfaces with custom `@Query` methods |
| `com.codepil.platform.websocket` | WebSocket | STOMP broadcast helpers |

**Convention rule:** Generated product services follow the same layering under their own root package: `com.codepil.{product}.{layer}`. For example, `com.codepil.catalog.api`, `com.codepil.catalog.service`, `com.codepil.catalog.domain`.

---

### Key Classes

#### `PlatformApplication.java`
- `@SpringBootApplication` + `@EnableMongoRepositories`
- Entry point — no logic, just bootstraps Spring context.

#### `config/SecurityConfig.java`
- `@Configuration @EnableWebSecurity @EnableMethodSecurity`
- Defines the `SecurityFilterChain` bean:
  - Permits `/actuator/health` and `/ws/**` without auth.
  - Requires valid Okta JWT for all other paths.
- Configures `oauth2ResourceServer(jwt → issuerUri)` using `OKTA_ISSUER_URI` env var.
- `JwtAuthenticationConverter` extracts scopes from the `scp` claim and prefixes them `SCOPE_` so Spring Security's `hasAuthority('SCOPE_agents:run')` works.
- **Depends on:** `lib-auth` (OktaJwtValidator), Spring Security OAuth2 Resource Server.

#### `config/WebSocketConfig.java`
- `@EnableWebSocketMessageBroker`
- Message broker: `/topic` prefix for server→client pushes.
- Application destination prefix: `/app` for client→server sends.
- STOMP endpoint: `/ws` with SockJS fallback.
- **Consumed by:** ReactJS MFEs via `@stomp/stompjs`.

#### `config/WebClientConfig.java`
- Produces a named `WebClient` bean (`agentEngineWebClient`).
- Base URL: `${AGENT_ENGINE_BASE_URL}` (default `http://localhost:8000`).
- 30-second response timeout, JSON `Content-Type` header pre-set.
- **Used by:** `AgentRunService`, `ApprovalService`.

#### `api/RunController.java`
- Thin controller — validates auth scope, calls `AgentRunService`, returns HTTP status.
- All heavy lifting delegated to service layer.
- **Depends on:** `AgentRunService`.

#### `api/ApprovalController.java`
- Thin controller for approval lifecycle.
- **Depends on:** `ApprovalService`.

#### `service/AgentRunService.java`
- Core orchestration service:
  1. Creates `AgentRun` in MongoDB.
  2. POSTs to Python agent-engine `/api/v1/runs`.
  3. Subscribes to SSE stream — parsing events, broadcasting to WebSocket, recording to audit trail.
  4. Handles `approval_requested` events by delegating to `ApprovalService`.
  5. On SSE error: updates run status to `failed`, calls `SlackNotificationService.alertOncall`.
- **Depends on:** `AgentRunRepository`, `AuditTrailService`, `ApprovalService`, `AgentEventBroadcaster`, `SlackNotificationService`, `WebClient` (agentEngineWebClient).

#### `service/ApprovalService.java`
- Creates `ApprovalRequest` documents when agent raises a gate.
- Sends Slack notification to approver channel.
- Processes decisions: updates MongoDB, POSTs `resume` to agent-engine, re-subscribes to SSE.
- **Depends on:** `ApprovalRequestRepository`, `AgentRunService`, `SlackNotificationService`.

#### `service/AuditTrailService.java`
- Records every SSE event to `audit_trail` collection asynchronously (`@Async`).
- Query method returns all events for a run ordered by timestamp.
- **Depends on:** `AuditEventRepository`.

#### `service/SlackNotificationService.java`
- POSTs to Slack Incoming Webhook URL.
- Two channels: approver notification channel and on-call alert channel.
- **Depends on:** `WebClient` (or `RestTemplate` — simpler since no streaming needed), Slack webhook URL from `application.yml`.

#### `websocket/AgentEventBroadcaster.java`
- Wraps `SimpMessagingTemplate`.
- `broadcast(runId, eventJson)` sends to `/topic/runs/{runId}`.
- ReactJS subscribes to this topic and renders live agent events.

---

### REST API Surface

#### `RunController` — `/api/v1/runs`

| Method | Path | Scope Required | Description | Request Body | Response |
|--------|------|----------------|-------------|--------------|----------|
| `POST` | `/api/v1/runs` | `agents:run` | Start a new SDLC run | `StartRunRequest` | `202 Accepted` + `StartRunResponse` |
| `GET` | `/api/v1/runs/{runId}` | `agents:read` | Get live run status | — | `200 OK` + `RunStatusResponse` |
| `GET` | `/api/v1/runs/{runId}/artifacts` | `agents:read` | List artifacts produced by run | — | `200 OK` + list of artifact metadata |

**`StartRunRequest`** (Java 21 record):
```json
{
  "jiraEpicId":       "SC-42",
  "productId":        "SelfCare-001",
  "figmaUrl":         "https://figma.com/file/...",
  "prdS3Url":         "s3://bucket/prd.pdf",
  "maxQaIterations":  3
}
```

**`StartRunResponse`** (Java 21 record):
```json
{
  "runId":  "550e8400-e29b-41d4-a716-446655440000",
  "status": "started"
}
```

**`RunStatusResponse`** (Java 21 record):
```json
{
  "runId":        "550e8400-...",
  "currentStage": "dev",
  "nextNodes":    ["qa_crew"],
  "qaIteration":  1,
  "llmUsage":     { "input_tokens": 12000, "output_tokens": 4500, "cost_usd": 0.18 },
  "errors":       []
}
```

#### `ApprovalController` — `/api/v1/approvals`

| Method | Path | Scope Required | Description | Request Body | Response |
|--------|------|----------------|-------------|--------------|----------|
| `GET` | `/api/v1/approvals` | `agents:read` | List all pending approvals | — | `200 OK` + list of `ApprovalRequest` |
| `POST` | `/api/v1/approvals/{approvalId}/decide` | `agents:approve` | Submit approval decision | `ApprovalDecisionRequest` | `200 OK` |

**`ApprovalDecisionRequest`**:
```json
{
  "decision": "approved",
  "feedback": "Looks good — proceed to dev stage"
}
```

---

### WebSocket (STOMP) — Event Flow

```
Python agent-engine (FastAPI)
         │
         │  SSE stream: GET /api/v1/runs/{runId}/events
         │  Content-Type: text/event-stream
         ▼
AgentRunService.subscribeToEventStream()
         │  WebClient .bodyToFlux(String.class)
         │  per event:
         │    → AuditTrailService.record()        (async, MongoDB)
         │    → AgentEventBroadcaster.broadcast() (WebSocket)
         │    → if approval_requested: ApprovalService.createApprovalRequest()
         │    → if run_complete: update AgentRun.status = completed
         ▼
AgentEventBroadcaster
         │  SimpMessagingTemplate.convertAndSend("/topic/runs/{runId}", eventJson)
         ▼
ReactJS MFE (mfe-agent-dashboard)
         │  STOMP subscription to /topic/runs/{runId}
         │  Renders live event in Pipeline Viewer
```

**SSE event format** (from Python engine):
```json
{
  "run_id":     "550e8400-...",
  "agent":      "JavaServiceBuilder",
  "event_type": "tool_call",
  "payload":    "{ ... }",
  "ts":         1712345678
}
```

`event_type` values that drive Java behaviour:
| `event_type` | Java action |
|---|---|
| `thinking`, `tool_call`, `state_update` | Broadcast to WebSocket, record to audit trail |
| `approval_requested` | Create `ApprovalRequest`, Slack notify, pause listening |
| `stage_complete` | Update `AgentRun.currentStage`, broadcast |
| `run_complete` | Set `AgentRun.status = completed`, broadcast final event |
| `error` | Record to audit trail, broadcast, if fatal set `status = failed`, Slack alert |

---

### Security — Okta JWT Validation and Scope-Based Access

**JWT flow:**
1. ReactJS obtains a JWT from Okta via PKCE flow.
2. JWT is sent in the `Authorization: Bearer <token>` header on every API call.
3. `SecurityConfig` configures Spring's `oauth2ResourceServer` to validate the token against Okta's JWKS endpoint (fetched from `{OKTA_ISSUER_URI}/.well-known/openid-configuration`).
4. `JwtAuthenticationConverter` maps the `scp` claim array to Spring Security `GrantedAuthority` objects prefixed `SCOPE_`.
5. Each controller method uses `@PreAuthorize("hasAuthority('SCOPE_{scope}')")` — Spring evaluates this before the method body runs.

**Scope per endpoint:**

| Scope | Endpoints |
|-------|-----------|
| `agents:run` | `POST /api/v1/runs` |
| `agents:read` | `GET /api/v1/runs/*`, `GET /api/v1/approvals` |
| `agents:approve` | `POST /api/v1/approvals/*/decide` |
| `admin:manage` | Future — platform configuration |

**Okta groups → scopes:**

| Okta Group | Scopes granted |
|------------|----------------|
| `platform-admin` | `agents:run`, `agents:read`, `agents:approve`, `admin:manage` |
| `agent-operator` | `agents:run`, `agents:read` |
| `approver` | `agents:approve`, `agents:read` |
| `viewer` | `agents:read` |

---

### MongoDB Collections Written By `platform-app`

#### `agent_runs`
| Field | Type | Description |
|-------|------|-------------|
| `_id` | `String` (UUID) | Auto-generated by `BaseDocument` |
| `runId` | `String` | UUID generated by Java at run start |
| `threadId` | `String` | UUID for LangGraph thread correlation |
| `productId` | `String` | Product being built (e.g. `SelfCare-001`) |
| `jiraEpicId` | `String` | Jira epic key (e.g. `SC-42`) |
| `status` | `String` | `running` \| `waiting_approval` \| `completed` \| `failed` \| `escalated` |
| `currentStage` | `String` | Active SDLC stage name |
| `approvalStage` | `String` | Which gate is open: `null` \| `requirements` \| `staging` |
| `qaIteration` | `int` | How many QA retry cycles have occurred |
| `llmUsage` | `Map<String,Object>` | Token counts and cost in USD |
| `errors` | `List<String>` | Error messages from failed stages |
| `createdAt` | `Instant` | Set by `@CreatedDate` (lib-mongodb) |
| `updatedAt` | `Instant` | Set by `@LastModifiedDate` (lib-mongodb) |

#### `audit_trail`
| Field | Type | Description |
|-------|------|-------------|
| `_id` | `String` | Auto-generated |
| `runId` | `String` | FK to `agent_runs.runId` |
| `agentName` | `String` | Which CrewAI agent produced this event |
| `eventType` | `String` | `state_update` \| `error` \| `run_complete` \| `approval_requested` |
| `stage` | `String` | SDLC stage at time of event |
| `rawPayload` | `String` | Full SSE JSON payload (for replay/debugging) |
| `timestampMs` | `long` | Epoch milliseconds from SSE event |

#### `approval_requests`
| Field | Type | Description |
|-------|------|-------------|
| `_id` | `String` | Auto-generated |
| `runId` | `String` | FK to `agent_runs.runId` |
| `approvalStage` | `String` | `requirements` \| `staging` |
| `status` | `String` | `pending` \| `approved` \| `rejected` |
| `artifactSummary` | `String` | Human-readable summary of what to review |
| `decision` | `String` | Copied from `ApprovalDecisionRequest.decision` |
| `feedback` | `String` | Optional text from approver |
| `approvedBy` | `String` | Okta user ID of the approver |
| `decidedAt` | `Instant` | When the decision was submitted |

---

### `application.yml` Key Properties

```yaml
server:
  port: 8080

spring:
  data:
    mongodb:
      uri: ${MONGO_URI:mongodb://localhost:27017/agent_platform}
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: ${OKTA_ISSUER_URI}           # Required — no default

agent:
  engine:
    base-url: ${AGENT_ENGINE_BASE_URL:http://localhost:8000}

slack:
  webhook-url: ${SLACK_WEBHOOK_URL:}               # Empty string = Slack disabled
  oncall-channel: ${SLACK_ONCALL_CHANNEL:#platform-oncall}

logging:
  pattern:
    console: "%d{ISO8601} [%thread] %-5level [%X{runId}] [%X{productId}] %logger{36} - %msg%n"
```

---

---

## Section B — Coding Standards (Used as Dev Crew Prompts)

### Why This Matters

The **Dev Crew agents** do not generate code in a vacuum. Their system prompts are dynamically assembled from three sources:

1. **The OpenAPI spec** produced by the Architecture Crew's `APIContractWriter` agent.
2. **The MongoDB schema** produced by the Architecture Crew's `SchemaDesigner` agent.
3. **Platform-core code snippets** — actual Java source files from this repository — showing exactly what a "correct" controller, service, repository, DTO, and exception looks like.

This technique is called **few-shot code generation**. By including real, passing, production code as examples, the LLM (Claude Sonnet) learns the exact conventions to replicate, rather than inventing its own style.

---

### How the Dev Crew System Prompt Is Built

The `DevCrew` class in `agent-engine/src/platform/crews/dev_crew.py` constructs the `JavaServiceBuilder` agent's backstory at runtime:

```python
# Inside DevCrew.kickoff() — real mode branch
java_dev = Agent(
    role="Senior Java Developer",
    goal="Implement production-ready Spring Boot 3 REST controllers, services, "
         "and SAP JCo integration with proper exception handling and test coverage",
    backstory=(
        "You are a Senior Java Developer specialising in Spring Boot 3, Spring Security, "
        "and SAP JCo integration. You write production-ready code with proper exception "
        "handling, logging, and Testcontainers-based integration tests. Your code follows "
        "hexagonal architecture and is fully covered by unit tests."
        "\n\nCODING STANDARDS TO FOLLOW:\n"
        + DevCrew._PLATFORM_CORE_SNIPPETS     # <── injected here
    ),
    ...
)
```

The `_PLATFORM_CORE_SNIPPETS` class constant contains representative excerpts from the actual `platform-core` source files. Four patterns are shown:

1. **Controller pattern** — thin `@RestController`, `@PreAuthorize`, delegates to service.
2. **Service pattern** — `@Service`, `@Transactional`, SLF4J logging with MDC.
3. **Repository pattern** — `MongoRepository` with `@Query`.
4. **DTO record pattern** — Java 21 `record` with static factory method.

The `java_task` task description additionally injects the OpenAPI spec and MongoDB schema:

```python
java_task = Task(
    description=(
        f"OpenAPI spec from Architecture Crew:\n{inputs.get('openapi_spec', '')}\n\n"
        f"MongoDB schema from Architecture Crew:\n{inputs.get('mongo_schema', '')}\n\n"
        f"Implement the Spring Boot service. Follow the coding standards in your backstory exactly.\n"
        f"1. Create the @RestController following the Controller Pattern example.\n"
        f"2. Create the @Service following the Service Pattern example.\n"
        f"3. Create the MongoRepository following the Repository Pattern example.\n"
        f"4. Create record DTOs following the DTO Record Pattern example.\n"
        f"Commit all files using Commit File to GitHub."
    ),
    ...
)
```

---

### Coding Standards Reference

These standards are enforced by the Tech Lead agent's review task and are injected as few-shot examples for the Java Developer agent.

#### Package Naming

```
com.codepil.{product}.{layer}
```

| Layer | Example |
|-------|---------|
| `api` | `com.codepil.catalog.api` |
| `api.dto` | `com.codepil.catalog.api.dto` |
| `service` | `com.codepil.catalog.service` |
| `domain` | `com.codepil.catalog.domain` |
| `repository` | `com.codepil.catalog.repository` |

#### Controller Standard

```java
@RestController
@RequestMapping("/api/v1/products")
public class ProductController {

    private final ProductService productService;

    // Constructor injection — no @Autowired, no Lombok
    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('SCOPE_products:read')")
    public ResponseEntity<Page<ProductResponse>> listProducts(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(productService.listProducts(page, size));
    }

    @PostMapping
    @PreAuthorize("hasAuthority('SCOPE_products:write')")
    public ResponseEntity<ProductResponse> createProduct(
            @RequestBody @Validated CreateProductRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                             .body(productService.createProduct(request));
    }
}
```

Rules:
- `@RestController` + `@RequestMapping` at class level, HTTP method annotations at method level.
- `@PreAuthorize` on every endpoint — no endpoint is unauthenticated except health checks.
- No business logic in the controller — it validates and delegates.
- Returns `ResponseEntity<T>` with explicit status codes.

#### Service Standard

```java
@Service
public class ProductService {

    private static final Logger log = LoggerFactory.getLogger(ProductService.class);

    private final ProductRepository productRepository;
    private final SapODataClient sapODataClient;

    public ProductService(ProductRepository productRepository, SapODataClient sapODataClient) {
        this.productRepository = productRepository;
        this.sapODataClient = sapODataClient;
    }

    @Transactional(readOnly = true)
    public Page<ProductResponse> listProducts(int page, int size) {
        log.info("Listing products page={} size={}", page, size);
        return productRepository.findAll(PageRequest.of(page, size))
                                .map(ProductResponse::from);
    }

    @Transactional
    public ProductResponse createProduct(CreateProductRequest request) {
        log.info("Creating product sku={}", request.sku());
        // ... business logic
    }
}
```

Rules:
- `@Service` annotation.
- `@Transactional(readOnly = true)` on read methods; `@Transactional` on write methods.
- SLF4J logger — `LoggerFactory.getLogger(ClassName.class)` — always `static final`.
- No `System.out.println` — ever.
- MDC keys `runId` and `productId` are injected by `MdcFilter` — log statements automatically include them.

#### Repository Standard

```java
@Repository
public interface ProductRepository extends MongoRepository<Product, String> {

    Page<Product> findByCategoryAndPriceLessThanEqual(
            String category, BigDecimal maxPrice, Pageable pageable);

    @Query("{ 'sapMaterialId': ?0 }")
    Optional<Product> findBySapMaterialId(String sapMaterialId);

    @Query("{ 'status': ?0, 'category': ?1 }")
    List<Product> findByStatusAndCategory(String status, String category);
}
```

Rules:
- Interface only — no implementation class.
- Extends `MongoRepository<T, String>` where `String` is the `_id` type.
- Use derived query method names where possible (Spring Data auto-implements them).
- Use `@Query` with MongoDB query JSON only when derived names become unreadable.

#### DTO Standard — Java 21 Records

```java
// Request record — immutable, no Lombok
public record CreateProductRequest(
        @NotBlank String sku,
        @NotBlank String name,
        @DecimalMin("0.01") BigDecimal price,
        @NotBlank String category,
        @NotBlank String sapMaterialId
) {}

// Response record with static factory
public record ProductResponse(
        String id,
        String sku,
        String name,
        BigDecimal price,
        String category,
        int stockQuantity
) {
    public static ProductResponse from(Product product) {
        return new ProductResponse(
                product.getId(), product.getSku(), product.getName(),
                product.getPrice(), product.getCategory(), product.getStockQuantity()
        );
    }
}
```

Rules:
- All DTOs are `record` classes (Java 21) — compact, immutable, no boilerplate.
- NO Lombok on any class.
- Bean validation annotations (`@NotBlank`, `@DecimalMin`) go on record components.
- Response records have a `static ProductResponse from(Domain domain)` factory method.

#### Exception Handling Standard

```java
// Custom exception extending PlatformException from lib-common
public class AgentRunNotFoundException extends PlatformException {
    public AgentRunNotFoundException(String runId) {
        super("Agent run not found: " + runId, "RUN_NOT_FOUND");
    }
}

// Global handler in the controller layer
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(AgentRunNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(AgentRunNotFoundException ex) {
        log.warn("Run not found: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                             .body(new ErrorResponse(ex.getErrorCode(), ex.getMessage()));
    }
}
```

Rules:
- Custom exceptions extend `PlatformException` (from `lib-common`, see Section C).
- `@RestControllerAdvice` catches exceptions globally — no try/catch in controllers.
- Error response shape: `{ "code": "RUN_NOT_FOUND", "message": "..." }`.

#### Logging Standard

```java
// In every class:
private static final Logger log = LoggerFactory.getLogger(AgentRunService.class);

// In service methods — structured log entries:
log.info("Starting SDLC run runId={} productId={} jiraEpicId={}",
         runId, productId, jiraEpicId);
log.warn("Approval timeout runId={} stage={}", runId, stage);
log.error("Agent engine unreachable runId={}", runId, exception);
```

Rules:
- `private static final Logger log = LoggerFactory.getLogger(ClassName.class)` — always.
- MDC context (`runId`, `productId`) is injected by `MdcFilter` — do not set manually in service methods.
- Log parameters as structured key=value pairs: `log.info("key={} key2={}", val, val2)`.
- Never log sensitive data (JWT tokens, SAP passwords, PII).

#### Test Standard

```java
// Unit test — no Spring context
@ExtendWith(MockitoExtension.class)
class AgentRunServiceTest {
    @Mock AgentRunRepository agentRunRepository;
    @Mock WebClient webClient;
    @InjectMocks AgentRunService agentRunService;

    @Test
    void startRun_savesToMongoDB_andCallsAgentEngine() {
        // Arrange
        var request = new StartRunRequest("SC-42", "SelfCare-001", null, null, 3);
        // Act
        var response = agentRunService.startRun(request, "okta-user-123");
        // Assert
        verify(agentRunRepository).save(any(AgentRun.class));
        assertThat(response.status()).isEqualTo("started");
    }
}

// Integration test — real MongoDB via Testcontainers
@SpringBootTest
@Testcontainers
class AgentRunRepositoryIT {
    @Container
    static MongoDBContainer mongo = new MongoDBContainer("mongo:7.0");
    // ...
}
```

Rules:
- Unit tests: `@ExtendWith(MockitoExtension.class)`, no Spring context loaded.
- Integration tests: `@SpringBootTest` + Testcontainers `MongoDBContainer` — no mocks for persistence.
- Controller tests: `@WebMvcTest` — loads only the web layer, all services mocked.
- Test method naming: `methodUnderTest_scenario_expectedOutcome`.
- Minimum 80% line coverage — enforced by QA Crew's `CodeReviewer` agent.

---

### Before/After Example — Architecture Spec to Generated Java File

#### Input: Architecture Crew output (simplified)

```yaml
# openapi_spec excerpt
paths:
  /api/v1/orders:
    post:
      operationId: createOrder
      security:
        - BearerAuth: [orders:write]
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateOrderRequest'
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResponse'

# mongo_schema excerpt
collections:
  orders:
    fields:
      orderId: string (UUID)
      customerId: string
      status: string (pending|confirmed|shipped)
      totalAmountUsd: decimal
      sapSalesOrderId: string
    shared_libs:
      - lib-mongodb   # BaseDocument for auditing
      - lib-sap       # SapODataClient for SAP order sync
```

#### Dev Crew prompt (assembled by `DevCrew.kickoff()`):

```
[System — Java Developer backstory]
You are a Senior Java Developer specialising in Spring Boot 3...

CODING STANDARDS TO FOLLOW:
=== CODING STANDARD: Spring Boot Controller Pattern ===
@RestController
@RequestMapping("/api/v1/products")
public class ProductController {
    ... (full snippet from _PLATFORM_CORE_SNIPPETS)
}

=== CODING STANDARD: Spring Boot Service Pattern ===
...

[Task description]
OpenAPI spec:
  POST /api/v1/orders — scope orders:write — returns 201 OrderResponse
  ...

MongoDB schema:
  orders collection — orderId, customerId, status, totalAmountUsd, sapSalesOrderId
  shared_libs: [lib-mongodb, lib-sap]

Implement the Spring Boot service. Follow the coding standards in your backstory exactly.
1. Create the @RestController following the Controller Pattern example.
2. Create the @Service following the Service Pattern example.
3. Create the MongoRepository following the Repository Pattern example.
4. Create record DTOs following the DTO Record Pattern example.
Commit all files using Commit File to GitHub.
```

#### Generated output (by Java Developer agent):

```java
// com/codepil/order/api/OrderController.java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping
    @PreAuthorize("hasAuthority('SCOPE_orders:write')")
    public ResponseEntity<OrderResponse> createOrder(
            @RequestBody @Validated CreateOrderRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                             .body(orderService.createOrder(request));
    }
}
```

The agent replicated the controller pattern exactly — constructor injection, `@PreAuthorize`, `ResponseEntity` with explicit status, delegation to service.

---

---

## Section C — `shared-java-libs`

### Why Shared Libraries Exist

Both `platform-core` (the control plane) and every **generated product service** (e.g. `selfcare-catalog`, `selfcare-order`) depend on the same cross-cutting concerns:

- JWT validation and scope enforcement
- MongoDB document base class and auditing
- Structured logging with MDC context
- SAP connectivity (OData v4, BAPI/RFC via JCo)

Without shared libraries, each generated service would re-implement these concerns differently, creating drift and security gaps. The Architecture Crew's output always lists which `shared_libs` a service needs — the Dev Crew uses this list to add the right Maven dependencies and import the correct classes.

---

### Library Catalogue

#### `lib-auth`
**Maven artifact:** `com.codepil.platform:lib-auth:1.0.0-SNAPSHOT`

| Class | Purpose |
|-------|---------|
| `OktaJwtValidator` | Validates JWT using Okta's JWKS endpoint. Caches JWKS to avoid repeated HTTP calls. Extracts `scp` claim as a list of scope strings. |
| `PlatformSecurityContext` | Static helpers: `getCurrentUserId()`, `getCurrentScopes()`, `hasScope(String)`. Reads from Spring's `SecurityContextHolder`. |
| `RequiresScope` | `@Target(METHOD) @Retention(RUNTIME)` annotation. Used at service layer as an alternative to controller-level `@PreAuthorize`. An AOP aspect enforces it. |

**Key use case:** Service-layer enforcement — a method marked `@RequiresScope("admin:manage")` will throw `AccessDeniedException` if the current user's token lacks that scope, even if the controller already checked a broader scope.

---

#### `lib-mongodb`
**Maven artifact:** `com.codepil.platform:lib-mongodb:1.0.0-SNAPSHOT`

| Class | Purpose |
|-------|---------|
| `BaseDocument` | Abstract base for all `@Document` entities. Provides `@Id String id` (auto-UUID), `@CreatedDate Instant createdAt`, `@LastModifiedDate Instant updatedAt`. |
| `MongoConfig` | `@Configuration @EnableMongoAuditing`. Enables Spring Data MongoDB auditing so `@CreatedDate` and `@LastModifiedDate` populate automatically on save. |

**Key use case:** Every domain entity extends `BaseDocument`. Adding a new collection only requires:
```java
@Document(collection = "orders")
public class Order extends BaseDocument {
    private String orderId;
    // ...
}
```
`createdAt` and `updatedAt` are managed automatically — no manual timestamp setting.

---

#### `lib-logging`
**Maven artifact:** `com.codepil.platform:lib-logging:1.0.0-SNAPSHOT`

| Class | Purpose |
|-------|---------|
| `MdcFilter` | `OncePerRequestFilter`. Extracts `X-Run-Id` and `X-Product-Id` HTTP headers and places their values in the SLF4J MDC as `runId` and `productId`. Clears MDC after each request. |
| `PlatformLogger` | Wrapper around SLF4J `Logger`. Adds structured key-value context and serialises log events as JSON for ELK/CloudWatch ingestion. |

**Key use case:** When the Java app calls the agent engine and receives SSE events, it sets `runId` in MDC. Every log line emitted during that event's processing automatically includes `[runId=550e8400-...]` — enabling log correlation in CloudWatch Insights or Kibana without any per-call code.

---

#### `lib-sap`
**Maven artifact:** `com.codepil.platform:lib-sap:1.0.0-SNAPSHOT`

| Class | Purpose |
|-------|---------|
| `SapODataClient` | Generic OData v4 client using Spring WebClient. Methods: `getEntities(serviceName, entitySet, filters)`, `createEntity(serviceName, entitySet, body)`. Handles OAuth2 client credentials to SAP Gateway. Retries 3 times with exponential backoff. |
| `SapBapiClient` | JCo-based RFC/BAPI caller. Method: `callBapi(bapiName, params)`. Manages JCo connection pool. Note: SAP JCo jar is not in Maven Central — must be installed to the local/private Maven repository manually. |
| `SapClientProperties` | `@ConfigurationProperties(prefix = "sap")`. Binds all SAP connectivity config from `application.yml` into a typed POJO: `gatewayUrl`, `oauthTokenUrl`, `clientId`, `clientSecret`, `jcoHost`, `jcoClient`, `jcoUser`, `jcoPassword`. |

**Key use case:** The `SAPConnectorBuilder` Dev Crew agent generates code that calls `SapODataClient` or `SapBapiClient` from `lib-sap` rather than building raw HTTP connections. This ensures all SAP calls use the platform's retry logic, OAuth2 token caching, and structured error handling.

---

### How Generated Product Services Import Shared Libs

Every generated `pom.xml` includes the shared libraries it needs. The Architecture Crew's output `shared_libs` field drives which dependencies the Dev Crew adds.

```xml
<!-- In a generated product service pom.xml -->
<dependencies>

    <!-- Always included -->
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-auth</artifactId>
        <version>${platform.version}</version>
    </dependency>
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-mongodb</artifactId>
        <version>${platform.version}</version>
    </dependency>
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-logging</artifactId>
        <version>${platform.version}</version>
    </dependency>

    <!-- Only when Architecture Crew lists lib-sap in shared_libs -->
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-sap</artifactId>
        <version>${platform.version}</version>
    </dependency>

</dependencies>
```

Usage in generated service code:
```java
import com.codepil.platform.mongodb.BaseDocument;
import com.codepil.platform.auth.PlatformSecurityContext;
import com.codepil.platform.logging.MdcFilter;
import com.codepil.platform.sap.SapODataClient;

@Document(collection = "orders")
public class Order extends BaseDocument {   // ← lib-mongodb
    // fields...
}

@Service
public class OrderService {
    private final SapODataClient sapODataClient;    // ← lib-sap

    public OrderResponse createOrder(CreateOrderRequest request) {
        String userId = PlatformSecurityContext.getCurrentUserId();  // ← lib-auth
        // ...
    }
}
```

---

### How Dev Crew Knows to Use Shared Libs

The Architecture Crew's `SchemaDesigner` and `SAPIntegrationPlanner` agents produce output that includes a `shared_libs` field:

```json
{
  "service_name": "order-service",
  "collections": ["orders"],
  "shared_libs": ["lib-mongodb", "lib-sap"],
  "sap_calls": [
    { "type": "odata", "service": "API_SALES_ORDER_SRV", "entity": "SalesOrder" }
  ]
}
```

When `DevCrew.kickoff()` receives this architecture output, it injects the API documentation for each listed lib into the Java Developer agent's task description:

```python
lib_docs = ""
for lib in architecture.get("shared_libs", []):
    lib_docs += LIB_API_DOCS[lib]  # pre-loaded API doc strings per lib

java_task = Task(
    description=(
        f"Shared library APIs to use:\n{lib_docs}\n\n"
        f"OpenAPI spec:\n{inputs.get('openapi_spec', '')}\n\n"
        ...
    ),
    ...
)
```

This ensures the agent knows exactly which classes to import and how to call them.

---

---

## Section D — Usage Guide

### 1. Running `platform-core` Locally

**Prerequisites:**
- Java 21 JDK (`JAVA_HOME` pointing to JDK 21)
- Maven 3.9+
- Docker (for MongoDB via Testcontainers in tests)
- A running Python agent-engine (default `http://localhost:8000`)
- Okta developer account with an API server (needed for JWT validation)

**Environment variables:**

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_URI` | No | Defaults to `mongodb://localhost:27017/agent_platform` |
| `OKTA_ISSUER_URI` | **Yes** | E.g. `https://dev-12345.okta.com/oauth2/default` |
| `AGENT_ENGINE_BASE_URL` | No | Defaults to `http://localhost:8000` |
| `SLACK_WEBHOOK_URL` | No | Slack notifications disabled if empty |
| `SLACK_ONCALL_CHANNEL` | No | Defaults to `#platform-oncall` |

**Start the app:**
```bash
# From the platform-core root
cd platform-core

# Build all modules (skip tests for fast start)
mvn clean install -DskipTests

# Run the Spring Boot app
cd platform-app
OKTA_ISSUER_URI=https://dev-12345.okta.com/oauth2/default \
mvn spring-boot:run
```

The app starts on port 8080. Check `GET http://localhost:8080/actuator/health` — should return `{"status":"UP"}`.

---

### 2. Starting an SDLC Run via the API

Get an Okta access token first (PKCE or client credentials depending on setup), then:

```bash
# Start a new SDLC run
curl -X POST http://localhost:8080/api/v1/runs \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "jiraEpicId":       "SC-42",
    "productId":        "SelfCare-001",
    "figmaUrl":         "https://www.figma.com/file/abc123/SelfCare",
    "prdS3Url":         "s3://my-bucket/prds/sc-42.pdf",
    "maxQaIterations":  3
  }'

# Response: 202 Accepted
{
  "runId":  "550e8400-e29b-41d4-a716-446655440000",
  "status": "started"
}
```

**Watch live events via WebSocket (JavaScript example):**
```javascript
import { Client } from '@stomp/stompjs';

const client = new Client({ brokerURL: 'ws://localhost:8080/ws' });

client.onConnect = () => {
  client.subscribe('/topic/runs/550e8400-e29b-41d4-a716-446655440000', (message) => {
    const event = JSON.parse(message.body);
    console.log(`[${event.agent}] ${event.event_type}: ${event.payload}`);
  });
};
client.activate();
```

**Poll run status via REST:**
```bash
curl http://localhost:8080/api/v1/runs/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <access_token>"

# Response
{
  "runId":        "550e8400-...",
  "currentStage": "requirements",
  "nextNodes":    ["architecture_crew"],
  "qaIteration":  0,
  "llmUsage":     { "input_tokens": 3200, "output_tokens": 800, "cost_usd": 0.04 },
  "errors":       []
}
```

---

### 3. Processing a Human Approval

When the agent engine raises a gate, `platform-app` creates an `ApprovalRequest` and sends a Slack notification. The approver uses the web UI or the REST API:

```bash
# List pending approvals
curl http://localhost:8080/api/v1/approvals \
  -H "Authorization: Bearer <access_token_with_agents:read_scope>"

# Response includes the approval ID:
[
  {
    "id": "appr-8800-...",
    "runId": "550e8400-...",
    "approvalStage": "requirements",
    "status": "pending",
    "artifactSummary": "Requirements Crew produced 12 user stories and 45 acceptance criteria..."
  }
]

# Approve
curl -X POST http://localhost:8080/api/v1/approvals/appr-8800-.../decide \
  -H "Authorization: Bearer <access_token_with_agents:approve_scope>" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "feedback": "Stories look complete — proceed to Architecture Crew"
  }'

# Reject (sends back to requirements stage with feedback)
curl -X POST http://localhost:8080/api/v1/approvals/appr-8800-.../decide \
  -H "Authorization: Bearer <access_token_with_agents:approve_scope>" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "rejected",
    "feedback": "Missing acceptance criteria for the SAP inventory sync story — please redo"
  }'
```

After `approved`, `ApprovalService` POSTs to the agent-engine's `/api/v1/runs/{runId}/resume` endpoint and the SSE stream resumes automatically.

---

### 4. How a Generated Product Service Uses Shared Java Libs

In a generated `selfcare-catalog` service:

**`pom.xml` dependency snippet:**
```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-mongodb</artifactId>
    </dependency>

    <!-- Platform shared libs -->
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-auth</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </dependency>
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-mongodb</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </dependency>
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-logging</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </dependency>
    <dependency>
        <groupId>com.codepil.platform</groupId>
        <artifactId>lib-sap</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </dependency>
</dependencies>
```

**Service code importing from shared libs:**
```java
package com.codepil.catalog.domain;

import com.codepil.platform.mongodb.BaseDocument;       // ← lib-mongodb
import org.springframework.data.mongodb.core.mapping.Document;

@Document(collection = "products")
public class Product extends BaseDocument {
    private String sku;
    private String name;
    private java.math.BigDecimal price;
    // getters/setters...
}
```

```java
package com.codepil.catalog.service;

import com.codepil.platform.auth.PlatformSecurityContext;  // ← lib-auth
import com.codepil.platform.sap.SapODataClient;            // ← lib-sap

@Service
public class ProductService {
    private final SapODataClient sapODataClient;

    public ProductResponse getProductFromSap(String materialId) {
        String userId = PlatformSecurityContext.getCurrentUserId();
        log.info("Fetching SAP product materialId={} requestedBy={}", materialId, userId);
        var result = sapODataClient.getEntities(
            "API_PRODUCT_SRV", "A_Product",
            Map.of("$filter", "Product eq '" + materialId + "'")
        );
        // map result to ProductResponse...
    }
}
```

---

### 5. How Dev Crew Uses Platform-Core as a Template

This is the mechanism that ensures every generated service looks like it was written by the same team.

**Injected snippet in Dev Crew prompt (from `_PLATFORM_CORE_SNIPPETS`):**
```
=== CODING STANDARD: Spring Boot Controller Pattern ===
@RestController
@RequestMapping("/api/v1/products")
public class ProductController {
    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    @GetMapping
    @PreAuthorize("hasAuthority('SCOPE_products:read')")
    public ResponseEntity<Page<ProductResponse>> listProducts(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(productService.listProducts(page, size));
    }
}
```

**Generated output by Java Developer agent:**
```java
// Generated for the order-service based on OpenAPI spec
// The agent replicated: constructor injection, @PreAuthorize, ResponseEntity, delegation to service
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping
    @PreAuthorize("hasAuthority('SCOPE_orders:write')")
    public ResponseEntity<OrderResponse> createOrder(
            @RequestBody @Validated CreateOrderRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                             .body(orderService.createOrder(request));
    }

    @GetMapping("/{orderId}")
    @PreAuthorize("hasAuthority('SCOPE_orders:read')")
    public ResponseEntity<OrderResponse> getOrder(@PathVariable String orderId) {
        return ResponseEntity.ok(orderService.getOrder(orderId));
    }
}
```

The agent faithfully reproduced the pattern — not because it was told "use constructor injection" in abstract terms, but because it saw a concrete working example and replicated it. This is why few-shot prompting with real code snippets is more reliable than rule-based instructions alone.
