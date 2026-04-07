# Architecture Crew

Parent blueprint: [blueprint.md](../../blueprint.md)

---

## Purpose

The Architecture Crew designs the complete technical solution for a self-care product. It produces OpenAPI 3.1 specifications for all microservices, MongoDB document schemas optimised for query patterns, Architecture Decision Records (ADRs), a SAP integration plan, and a service dependency graph — all as an `ArchitectureOutput` TypedDict.

---

## Process Type

**`Process.sequential`**

Tasks execute in order: Solution Architect → API Designer → Data Architect. Each agent builds on the previous one's output via `context` dependencies.

---

## Agent Roster

### 1. Solution Architect

| Field | Value |
|-------|-------|
| Role | Solution Architect |
| Goal | Design a scalable, cloud-native system architecture with clear ADRs |
| Tools | `Read Jira Epic`, `Add Jira Comment`, `Create GitHub Branch`, `Commit File to GitHub` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Principal Solution Architect specialising in cloud-native microservices on AWS. You have designed event-driven systems processing 10M+ events/day and are an expert in the reactive manifesto, DDD, and hexagonal architecture. You produce ADRs that are clear, opinionated, and easy for junior engineers to follow.

---

### 2. API Designer

| Field | Value |
|-------|-------|
| Role | API Designer |
| Goal | Produce OpenAPI 3.1 specifications for all services following API-first principles |
| Tools | `Commit File to GitHub` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Lead API Designer who follows API-first development. You write OpenAPI 3.1 specifications that are developer-friendly, RESTful, and hypermedia-ready. You have designed APIs for Stripe-quality developer experience and know every OpenAPI extension.

---

### 3. Data Architect

| Field | Value |
|-------|-------|
| Role | Data Architect |
| Goal | Design MongoDB schemas optimised for query patterns with Atlas Search configuration |
| Tools | `Commit File to GitHub` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a MongoDB Certified Data Architect. You design document schemas optimised for query patterns, know when to embed vs reference, and produce Atlas Search and Vector Search configurations as part of your deliverables.

---

## Task Definitions

### `design_task`

| Field | Value |
|-------|-------|
| Agent | Solution Architect |
| Context dependencies | — (first task) |
| Description | Design the full system architecture from requirements. Produce ADRs for key decisions, a service dependency graph (nodes + directed edges), and a SAP integration plan (OData services, auth, retry). Commit ADR documents to GitHub. |
| Expected output | JSON: `{adr_ids, service_dependency_graph, sap_integration_plan}` |

---

### `api_task`

| Field | Value |
|-------|-------|
| Agent | API Designer |
| Context dependencies | `[design_task]` |
| Description | Write OpenAPI 3.1 specs for all identified services. Each spec must include all endpoints with HTTP method, path, summary, query parameters, and request/response schemas. Commit each spec to the architecture branch on GitHub. |
| Expected output | JSON list of OpenAPI spec objects: `{service, version, base_path, endpoints[]}` |

---

### `schema_task`

| Field | Value |
|-------|-------|
| Agent | Data Architect |
| Context dependencies | `[design_task, api_task]` |
| Description | Design MongoDB document schemas for each collection. Include bsonType validation, compound indexes for common query patterns, Atlas Search index config, and embed-vs-reference decisions. Commit schema files to GitHub. |
| Expected output | JSON list: `{collection, indexes[], schema{bsonType validation}}` |

---

## Crew Configuration

| Parameter | Value |
|-----------|-------|
| `process` | `Process.sequential` |
| `verbose` | `True` |
| `memory` | `True` |
| `max_rpm` | `10` |

---

## Output Mapping — `ArchitectureOutput` TypedDict

| Crew output key | TypedDict field | Type |
|-----------------|-----------------|------|
| `openapi_specs` | `architecture.openapi_specs` | `List[Dict]` |
| `mongodb_schemas` | `architecture.mongodb_schemas` | `List[Dict]` |
| `adr_ids` | `architecture.adr_ids` | `List[str]` |
| `sap_integration_plan` | `architecture.sap_integration_plan` | `Dict` |
| `service_dependency_graph` | `architecture.service_dependency_graph` | `Dict` |

Validated by `ArchitectureCrewOutput` Pydantic model in `output_models.py`.

---

## Pydantic Output Models

```python
class OpenAPIEndpoint(BaseModel):
    method: str
    path: str
    summary: str
    query_params: Optional[List[str]] = None
    request_body: Optional[str] = None

class OpenAPISpec(BaseModel):
    service: str
    version: str
    base_path: str
    endpoints: List[OpenAPIEndpoint]

class ArchitectureCrewOutput(BaseModel):
    openapi_specs: List[OpenAPISpec]
    mongodb_schemas: List[Dict[str, Any]]
    adr_ids: List[str]
    sap_integration_plan: Dict[str, Any]
    service_dependency_graph: Dict[str, Any]
```

All models use `model_config = ConfigDict(extra='allow')`.

---

## Mock vs Real Mode

| Mode | Behaviour |
|------|-----------|
| `MOCK_MODE=true` | Returns `_MOCK_OUTPUT` — hardcoded `ArchitectureOutput` with 1 OpenAPI spec (3 endpoints), 1 MongoDB schema (products collection), 2 ADR IDs, SAP OData integration plan, and a 5-node dependency graph. No CrewAI imports occur. |
| `MOCK_MODE=false` | Real CrewAI objects instantiated. LLM obtained from `get_llm("architecture_design")` (Sonnet). GitHub tools used to commit ADRs and specs. LLM output parsed into `ArchitectureOutput` shape. |

---

## File Locations

| File | Path |
|------|------|
| Crew implementation | `agent-engine/src/platform/crews/architecture_crew.py` |
| Output model | `agent-engine/src/platform/crews/output_models.py` |
| CrewAI tools | `agent-engine/src/platform/tools/crewai_tools.py` |
| GitHub client | `agent-engine/src/platform/tools/github_tools.py` |
| Tests | `agent-engine/tests/test_crews.py::TestArchitectureCrew` |
