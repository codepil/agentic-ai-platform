# MongoDB Atlas Schema Design — Agentic AI Platform

**Database:** `agent_platform`
**Cluster:** MongoDB Atlas M30+ (multi-region)
**Last Updated:** 2026-04-07

---

## Table of Contents

1. [Overview](#1-overview)
2. [Collection Inventory](#2-collection-inventory)
3. [Data Flow Diagram](#3-data-flow-diagram)
4. [Collection Schemas](#4-collection-schemas)
   - 4.1 [agent_runs](#41-agent_runs)
   - 4.2 [approval_requests](#42-approval_requests)
   - 4.3 [audit_trail](#43-audit_trail)
   - 4.4 [langgraph_checkpoints](#44-langgraph_checkpoints)
   - 4.5 [langgraph_writes](#45-langgraph_writes)
   - 4.6 [sdlc_artifacts](#46-sdlc_artifacts)
   - 4.7 [context_snapshots](#47-context_snapshots)
   - 4.8 [vector_embeddings](#48-vector_embeddings)
5. [Index Strategy](#5-index-strategy)
6. [Retention and TTL Policy](#6-retention-and-ttl-policy)
7. [Atlas Cluster Sizing](#7-atlas-cluster-sizing)
8. [Setup Scripts](#8-setup-scripts)
9. [Cross-References](#9-cross-references)

---

## 1. Overview

This document describes the MongoDB Atlas schema for the Agentic AI Platform — a system that orchestrates autonomous software development lifecycle (SDLC) workflows using LangGraph state machines, CrewAI multi-agent crews, and Claude AI models.

The platform spans three backend services that share a single Atlas database (`agent_platform`):

| Service | Runtime | Role |
|---|---|---|
| **platform-core** | Java 21 + Spring Boot 3 | REST API gateway, approval orchestration, audit recording, WebSocket relay |
| **agent-engine** | Python 3.12 + FastAPI | LangGraph SDLC graph execution, CrewAI crew dispatch, SSE event streaming |
| **mfe (ReactJS)** | Node.js (browser) | Real-time dashboard, approval portal, audit log viewer |

The ReactJS frontend never writes to MongoDB directly; it receives data via Spring Boot WebSocket (STOMP) and REST API calls.

---

## 2. Collection Inventory

| Collection | Owner Service | Purpose | Write Pattern | Estimated Size |
|---|---|---|---|---|
| `agent_runs` | platform-core (Spring Boot) | One document per SDLC run. Tracks lifecycle status, stage progression, LLM token usage, and error accumulation. | Create once, update ~20x per run | ~5 KB/doc · 10K docs/year = ~50 MB/year |
| `approval_requests` | platform-core (Spring Boot) | Human-in-the-loop approval gate records (requirements review, staging sign-off). | Create once, update once on decision | ~3 KB/doc · 20K docs/year = ~60 MB/year |
| `audit_trail` | platform-core (Spring Boot) | Append-only log of every SSE event from the agent-engine. Compliance, replay, debugging. | Append-only, ~200 events/run | ~2 KB/doc · 2M docs/year = ~4 GB/year |
| `langgraph_checkpoints` | agent-engine (Python) | Full serialized `SDLCState` after every LangGraph node execution. Supports interrupt/resume and crash recovery. | Upsert after each node (~12 nodes/run) | ~50 KB/doc · 120K docs/year = ~6 GB/year |
| `langgraph_writes` | agent-engine (Python) | Pending channel writes not yet committed to a checkpoint. Transient buffer between graph steps. | Insert/delete within seconds | ~5 KB/doc · small volume (cleaned up) |
| `sdlc_artifacts` | agent-engine (Python) | Generated SDLC artifacts: user stories, OpenAPI specs, Java service code, React components, test suites, ADRs, Terraform configs. | Create once per artifact | ~200 KB/doc · 100K docs/year = ~20 GB/year |
| `context_snapshots` | platform-core (Spring Boot) | Snapshot of enterprise system data (Jira, SAP, Figma, GitHub) fetched at run start for traceability and RAG embedding input. | Create once per run | ~100 KB/doc · 10K docs/year = ~1 GB/year |
| `vector_embeddings` | agent-engine (Python) | 1536-dimension text embeddings for Atlas Vector Search. Powers RAG retrieval for Claude context injection. | Create once, never update | ~8 KB/doc · 50K docs/year = ~400 MB/year |

**Total estimated growth:** ~32 GB/year at 10K runs/year. M30 tier comfortably handles this within a 3-year horizon.

---

## 3. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SDLC Run Lifecycle                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

  ReactJS MFE                platform-core (Spring Boot)         agent-engine (Python FastAPI)
  ──────────                 ──────────────────────────          ─────────────────────────────
  POST /api/v1/runs   ──►   AgentRunService.startRun()
                             │  WRITE agent_runs {status:running}
                             │  POST /api/v1/runs ──────────────► LangGraph graph.astart()
                             │                                     │  UPSERT langgraph_checkpoints
                             │                                     │  INSERT langgraph_writes
                             │  GET /api/v1/runs/{id}/events ◄─── │  SSE stream per node
                             │  (long-lived SSE subscription)      │
                             │                                     ▼
                             │  handleSseEvent()                   [intake node]
                             │  ├─ BROADCAST WebSocket/STOMP       │  READ context_snapshots
                             │  ├─ INSERT audit_trail              │  READ vector_embeddings (RAG)
                             │  ├─ UPDATE agent_runs               │
                             │  └─ on approval_requested:          [requirements node]
                             │     INSERT approval_requests         │  WRITE sdlc_artifacts (user_stories)
                             │     SEND Slack notification          │  WRITE vector_embeddings
                             │                                     │
                             ◄── SSE: approval_requested ─────────[requirements_approval node]
                             │   UPDATE agent_runs                  │  INTERRUPT (graph paused here)
                             │   {status: waiting_approval}         │  UPSERT langgraph_checkpoints
                             │                                     │
  POST /api/v1/runs/         │                                     │
  {id}/approve        ──►   ApprovalService.processDecision()     │
                             │  UPDATE approval_requests           │
                             │  POST /api/v1/runs/{id}/resume ──► graph.resume(Command)
                             │                                     │  READ langgraph_checkpoints
                             │                                     │
                             │                                    [architecture → dev → qa → devops]
                             │                                     │  WRITE sdlc_artifacts
                             │                                     │  WRITE vector_embeddings
                             │                                     │  UPSERT langgraph_checkpoints
                             │                                     │
                             ◄── SSE: run_complete ───────────────[deploy_prod node → END]
                             │   UPDATE agent_runs {status: completed}
                             │
  GET /audit ──────── ──►   READ audit_trail (by runId + time)
  GET /artifacts ──── ──►   READ sdlc_artifacts (by runId)
  GET /status ─────── ──►   READ agent_runs (by runId)
```

### Collection Access Summary

| Collection | platform-core | agent-engine | ReactJS |
|---|---|---|---|
| `agent_runs` | R/W (primary owner) | R (status poll) | R via REST |
| `approval_requests` | R/W (primary owner) | — | R via REST |
| `audit_trail` | W (append-only) | — | R via REST |
| `langgraph_checkpoints` | — | R/W (primary owner) | — |
| `langgraph_writes` | — | R/W (primary owner) | — |
| `sdlc_artifacts` | R (listing) | W (primary owner) | R via REST |
| `context_snapshots` | W (at run start) | R (at intake) | — |
| `vector_embeddings` | — | R/W (primary owner) | — |

---

## 4. Collection Schemas

### 4.1 `agent_runs`

**Owner:** platform-core (`com.codepil.platform.domain.AgentRun` extends `BaseDocument`)

**Purpose:** Single source of truth for a SDLC run's lifecycle status. Created when `POST /api/v1/runs` is called and updated throughout the run as SSE events arrive. ReactJS reads this for the dashboard run list and run detail views.

**Status lifecycle:**
```
running → waiting_approval → running → completed
                           → rejected → failed  (if max rejections exceeded)
        → failed
        → escalated  (stuck > 30 min, triggers on-call alert)
```

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "AgentRun",
    "required": ["_id", "runId", "threadId", "productId", "jiraEpicId", "status",
                 "currentStage", "qaIteration", "initiatedByUserId", "createdAt", "updatedAt"],
    "additionalProperties": true,
    "properties": {
      "_id": {
        "bsonType": "string",
        "description": "UUID string — set by BaseDocument constructor before first save"
      },
      "runId": {
        "bsonType": "string",
        "description": "Stable external UUID. Unique index. Used in all cross-collection FK references."
      },
      "threadId": {
        "bsonType": "string",
        "description": "UUID passed to LangGraph as configurable.thread_id. Correlates agent_runs to langgraph_checkpoints."
      },
      "productId": {
        "bsonType": "string",
        "description": "Platform product identifier (e.g. SelfCare-001). Indexed for product-scoped queries."
      },
      "jiraEpicId": {
        "bsonType": "string",
        "description": "Jira epic key that initiated this run (e.g. SC-42)."
      },
      "status": {
        "bsonType": "string",
        "enum": ["running", "waiting_approval", "completed", "failed", "escalated"],
        "description": "Current lifecycle status. Indexed for dashboard status-filter queries."
      },
      "currentStage": {
        "bsonType": "string",
        "description": "Active SDLC stage name (intake / requirements / architecture / dev / qa / devops / deployed_staging / deployed_production / error)."
      },
      "approvalStage": {
        "bsonType": ["string", "null"],
        "enum": ["requirements", "staging", null],
        "description": "Which human gate is currently open. Null when no gate is active."
      },
      "qaIteration": {
        "bsonType": "int",
        "description": "Number of QA retry cycles completed. Incremented by qa_failed_handler_node."
      },
      "llmUsage": {
        "bsonType": "object",
        "description": "Accumulated LLM token usage and cost from the agent-engine.",
        "properties": {
          "input_tokens":  { "bsonType": "int" },
          "output_tokens": { "bsonType": "int" },
          "cost_usd":      { "bsonType": "double" }
        }
      },
      "errors": {
        "bsonType": "array",
        "description": "Ordered list of error messages from failed stages or tool calls.",
        "items": { "bsonType": "string" }
      },
      "initiatedByUserId": {
        "bsonType": "string",
        "description": "Okta subject claim (user ID) of the operator who started this run."
      },
      "createdAt": {
        "bsonType": "date",
        "description": "Populated by Spring Data MongoDB @CreatedDate on first save."
      },
      "updatedAt": {
        "bsonType": "date",
        "description": "Updated by Spring Data MongoDB @LastModifiedDate on every save."
      }
    }
  }
}
```

#### Example Document

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "threadId": "f0e1d2c3-b4a5-6789-0123-456789abcdef",
  "productId": "SelfCare-001",
  "jiraEpicId": "SC-42",
  "status": "waiting_approval",
  "currentStage": "requirements",
  "approvalStage": "requirements",
  "qaIteration": 0,
  "llmUsage": {
    "input_tokens": 24500,
    "output_tokens": 8200,
    "cost_usd": 0.87
  },
  "errors": [],
  "initiatedByUserId": "okta|user_01J8XXXXXXXX",
  "createdAt": { "$date": "2026-04-07T10:00:00.000Z" },
  "updatedAt": { "$date": "2026-04-07T10:08:33.000Z" }
}
```

---

### 4.2 `approval_requests`

**Owner:** platform-core (`com.codepil.platform.domain.ApprovalRequest` extends `BaseDocument`)

**Purpose:** Records human approval gate requests created when the LangGraph graph emits an `approval_requested` SSE event. The approval portal MFE queries pending documents; approvers submit decisions via `POST /api/v1/runs/{runId}/approve`. The decision is written back here before the agent-engine is resumed.

**Approval gates:**
- `requirements` — after the requirements crew produces user stories and acceptance criteria
- `staging` — after the devops crew deploys to staging and runs smoke tests

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "ApprovalRequest",
    "required": ["_id", "runId", "approvalStage", "status", "artifactSummary", "createdAt", "updatedAt"],
    "additionalProperties": true,
    "properties": {
      "_id": {
        "bsonType": "string",
        "description": "UUID string from BaseDocument."
      },
      "runId": {
        "bsonType": "string",
        "description": "FK to agent_runs.runId. Indexed for run-scoped lookups."
      },
      "approvalStage": {
        "bsonType": "string",
        "enum": ["requirements", "staging"],
        "description": "Which SDLC gate checkpoint this approval covers."
      },
      "status": {
        "bsonType": "string",
        "enum": ["pending", "approved", "rejected"],
        "description": "Current approval status. Indexed for pending-approvals dashboard queries."
      },
      "artifactSummary": {
        "bsonType": "string",
        "description": "Human-readable markdown summary generated by the crew. Shown in the approval portal."
      },
      "decision": {
        "bsonType": ["string", "null"],
        "enum": ["approved", "rejected", null],
        "description": "The decision submitted by the approver. Null until decided."
      },
      "feedback": {
        "bsonType": ["string", "null"],
        "description": "Optional free-text feedback from the approver. Required when rejecting."
      },
      "approvedBy": {
        "bsonType": ["string", "null"],
        "description": "Okta user ID of the approver who recorded the decision."
      },
      "decidedAt": {
        "bsonType": ["date", "null"],
        "description": "Wall-clock timestamp when the decision was recorded."
      },
      "createdAt": {
        "bsonType": "date"
      },
      "updatedAt": {
        "bsonType": "date"
      }
    }
  }
}
```

#### Example Document (pending)

```json
{
  "_id": "660e8400-e29b-41d4-a716-446655440001",
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "approvalStage": "requirements",
  "status": "pending",
  "artifactSummary": "## Requirements Summary\n\n**Product:** SelfCare-001\n**Epic:** SC-42\n\n### User Stories Generated\n- US-001: As a customer, I can view my bill online...\n- US-002: As a customer, I can pay my bill using a saved card...\n\n### SAP Dependencies\n- BAPI_BILLING_GETLIST (FI-AR)\n- ZSD_SELFCARE_PAYMENT (custom)\n\n### Open Ambiguities\n- Maximum retry count for failed payments not specified in PRD.",
  "decision": null,
  "feedback": null,
  "approvedBy": null,
  "decidedAt": null,
  "createdAt": { "$date": "2026-04-07T10:08:35.000Z" },
  "updatedAt": { "$date": "2026-04-07T10:08:35.000Z" }
}
```

#### Example Document (approved)

```json
{
  "_id": "660e8400-e29b-41d4-a716-446655440001",
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "approvalStage": "requirements",
  "status": "approved",
  "artifactSummary": "## Requirements Summary\n\n...",
  "decision": "approved",
  "feedback": "Looks good. Please clarify payment retry logic in the next sprint.",
  "approvedBy": "okta|user_01J8YYYYYYYY",
  "decidedAt": { "$date": "2026-04-07T10:25:00.000Z" },
  "createdAt": { "$date": "2026-04-07T10:08:35.000Z" },
  "updatedAt": { "$date": "2026-04-07T10:25:00.000Z" }
}
```

---

### 4.3 `audit_trail`

**Owner:** platform-core (`com.codepil.platform.domain.AuditEvent` extends `BaseDocument`)

**Purpose:** Append-only log of every SSE event received from the agent-engine. Each SSE event (thinking step, tool call, state update, stage completion, approval request, run completion, error) produces exactly one document. Provides full replay capability for compliance audits and debugging. The mfe-audit-logs MFE queries this collection paginated by `(runId, timestampMs)`.

**Write guarantee:** Documents are never updated or deleted. `audit_trail` is the authoritative record of what the AI agents did and when.

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "AuditEvent",
    "required": ["_id", "runId", "eventType", "stage", "rawPayload", "timestampMs", "createdAt"],
    "additionalProperties": true,
    "properties": {
      "_id": {
        "bsonType": "string",
        "description": "UUID string from BaseDocument."
      },
      "runId": {
        "bsonType": "string",
        "description": "FK to agent_runs.runId. Part of the compound index (runId, timestampMs)."
      },
      "agentName": {
        "bsonType": ["string", "null"],
        "description": "Name of the CrewAI agent that produced this event (e.g. RequirementsParser, ArchitectureDesigner). Null for graph-level events."
      },
      "eventType": {
        "bsonType": "string",
        "enum": ["thinking", "tool_call", "state_update", "stage_complete",
                 "approval_requested", "run_complete", "error"],
        "description": "Classifies the event. Used to filter the audit log view."
      },
      "stage": {
        "bsonType": "string",
        "description": "SDLC stage active at the time of the event."
      },
      "rawPayload": {
        "bsonType": "string",
        "description": "Full raw JSON string from the SSE event data field. Preserved verbatim for replay."
      },
      "timestampMs": {
        "bsonType": "long",
        "description": "Epoch milliseconds from the SSE event timestamp field. Part of the compound index."
      },
      "createdAt": {
        "bsonType": "date",
        "description": "Wall-clock insert time set by Spring Data MongoDB @CreatedDate."
      },
      "updatedAt": {
        "bsonType": "date"
      }
    }
  }
}
```

#### Example Documents

```json
{
  "_id": "770e8400-e29b-41d4-a716-000000000001",
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "agentName": "RequirementsParser",
  "eventType": "thinking",
  "stage": "requirements",
  "rawPayload": "{\"run_id\":\"a1b2c3d4\",\"agent\":\"requirements\",\"event_type\":\"thinking\",\"stage\":\"requirements\",\"ts\":1744020500000,\"payload\":\"Analyzing Jira epic SC-42 for user story extraction...\"}",
  "timestampMs": 1744020500000,
  "createdAt": { "$date": "2026-04-07T10:01:40.000Z" },
  "updatedAt": { "$date": "2026-04-07T10:01:40.000Z" }
}
```

```json
{
  "_id": "770e8400-e29b-41d4-a716-000000000042",
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "agentName": null,
  "eventType": "stage_complete",
  "stage": "requirements",
  "rawPayload": "{\"run_id\":\"a1b2c3d4\",\"agent\":\"requirements\",\"event_type\":\"stage_complete\",\"stage\":\"requirements\",\"ts\":1744020800000,\"payload\":\"requirements\"}",
  "timestampMs": 1744020800000,
  "createdAt": { "$date": "2026-04-07T10:06:40.000Z" },
  "updatedAt": { "$date": "2026-04-07T10:06:40.000Z" }
}
```

---

### 4.4 `langgraph_checkpoints`

**Owner:** agent-engine (Python `MongoCheckpointer`)

**Purpose:** Stores the full serialized `SDLCState` TypedDict after every LangGraph node execution. This enables:
1. **Interrupt/resume** — the graph pauses at `requirements_approval` and `staging_approval` nodes, persists state here, and resumes from this checkpoint when the human decision arrives.
2. **Crash recovery** — if the agent-engine process restarts, the graph re-reads the latest checkpoint and continues from the last committed node.
3. **State inspection** — `GET /api/v1/runs/{run_id}/status` calls `graph.get_state()` which reads the latest checkpoint for a `thread_id`.

The `checkpoint` and `metadata` fields are JSON strings (serialized by `MongoCheckpointer._serialize()`). The `state` sub-document description below reflects the deserialized SDLCState structure for documentation purposes.

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "LangGraphCheckpoint",
    "required": ["thread_id", "checkpoint_id", "checkpoint", "metadata", "saved_at"],
    "additionalProperties": true,
    "properties": {
      "_id": {
        "bsonType": "objectId",
        "description": "MongoDB auto-generated ObjectId (not a UUID — this collection is Python-owned)."
      },
      "thread_id": {
        "bsonType": "string",
        "description": "LangGraph thread identifier. Correlates to agent_runs.threadId. Part of unique compound index."
      },
      "checkpoint_id": {
        "bsonType": "string",
        "description": "Unique checkpoint identifier within the thread. LangGraph generates this as a UUID. Part of unique compound index."
      },
      "parent_checkpoint_id": {
        "bsonType": ["string", "null"],
        "description": "checkpoint_id of the preceding checkpoint in this thread. Null for the first checkpoint."
      },
      "checkpoint": {
        "bsonType": "string",
        "description": "JSON-serialized LangGraph Checkpoint object containing the full SDLCState. See state structure below."
      },
      "metadata": {
        "bsonType": "string",
        "description": "JSON-serialized CheckpointMetadata (step number, source node name, writes)."
      },
      "new_versions": {
        "bsonType": "string",
        "description": "JSON-serialized channel version map from LangGraph for this checkpoint step."
      },
      "saved_at": {
        "bsonType": "date",
        "description": "UTC timestamp when this checkpoint was written by MongoCheckpointer.put()."
      }
    }
  }
}
```

#### SDLCState Structure (inside `checkpoint` JSON string)

The `checkpoint` field serializes the full LangGraph `Checkpoint` object. The `values` key within it holds the `SDLCState` TypedDict:

```json
{
  "thread_id": "f0e1d2c3-b4a5-6789-0123-456789abcdef",
  "checkpoint_id": "1ef8b4a0-1234-5678-9abc-def012345678",
  "parent_checkpoint_id": "1ef8b4a0-0000-0000-0000-000000000001",
  "checkpoint": "{\"id\": \"1ef8b4a0-1234-5678-9abc-def012345678\", \"v\": 1, \"ts\": \"2026-04-07T10:08:00Z\", \"channel_values\": {\"run_id\": \"a1b2c3d4-e5f6-7890-abcd-ef1234567890\", \"product_id\": \"SelfCare-001\", \"thread_id\": \"f0e1d2c3-b4a5-6789-0123-456789abcdef\", \"jira_epic_id\": \"SC-42\", \"figma_url\": \"https://figma.com/file/XXXXXX\", \"prd_s3_url\": \"s3://platform-docs/SC-42/prd.pdf\", \"requirements\": {\"user_stories\": [{\"id\": \"US-001\", \"title\": \"View bill online\", \"description\": \"As a customer...\", \"acceptance_criteria\": [\"Given I am logged in...\"], \"story_points\": 5}], \"acceptance_criteria\": [{\"story_id\": \"US-001\", \"criteria\": [\"Bill displays within 2 seconds\"]}], \"sap_dependencies\": [\"BAPI_BILLING_GETLIST\", \"ZSD_SELFCARE_PAYMENT\"], \"ambiguities\": [\"Maximum payment retry count not specified\"], \"jira_subtask_ids\": [\"SC-43\", \"SC-44\"]}, \"architecture\": null, \"code_artifacts\": [], \"qa_results\": null, \"deployment\": null, \"current_stage\": \"requirements\", \"qa_iteration\": 0, \"max_qa_iterations\": 3, \"approval_status\": null, \"human_feedback\": null, \"requirements_rejection_count\": 0, \"messages\": [], \"llm_usage\": {\"input_tokens\": 24500, \"output_tokens\": 8200, \"cost_usd\": 0.87}, \"errors\": [], \"stage_timings\": {\"intake\": 12.4, \"requirements\": 485.2}}}",
  "metadata": "{\"step\": 2, \"source\": \"loop\", \"writes\": {\"requirements\": {\"requirements\": {...}}}}",
  "new_versions": "{\"run_id\": 1, \"product_id\": 1, \"requirements\": 3}",
  "saved_at": { "$date": "2026-04-07T10:08:00.000Z" }
}
```

**SDLCState field reference (deserialized from `checkpoint.channel_values`):**

| Field | Python Type | Description |
|---|---|---|
| `run_id` | `str` | FK to `agent_runs.runId` |
| `product_id` | `str` | Platform product ID |
| `thread_id` | `str` | LangGraph thread ID |
| `jira_epic_id` | `str` | Jira epic key |
| `figma_url` | `Optional[str]` | Figma design file URL |
| `prd_s3_url` | `Optional[str]` | S3 path to the PRD PDF |
| `requirements` | `Optional[RequirementsOutput]` | User stories, acceptance criteria, SAP deps, ambiguities, Jira subtask IDs |
| `architecture` | `Optional[ArchitectureOutput]` | OpenAPI specs, MongoDB schemas, ADR IDs, SAP integration plan, service dependency graph |
| `code_artifacts` | `List[CodeArtifact]` | Each: artifact_id, type, repo, file_path, git_branch, git_commit_sha, content_hash |
| `qa_results` | `Optional[QAResults]` | passed, unit_test_results, integration_test_results, security_scan_results, code_review_findings, e2e_test_results, failure_summary |
| `deployment` | `Optional[DeploymentResult]` | environment, service_urls, git_pr_url, pipeline_run_url, deployed_at |
| `current_stage` | `str` | Active graph node name |
| `qa_iteration` | `int` | QA retry count |
| `max_qa_iterations` | `int` | Escalation threshold (default: 3) |
| `approval_status` | `Optional[str]` | `approved` / `rejected` / `None` |
| `human_feedback` | `Optional[str]` | Approver free-text feedback |
| `requirements_rejection_count` | `int` | Consecutive requirements rejections |
| `messages` | `List[BaseMessage]` | LangChain message history (add_messages reducer) |
| `llm_usage` | `LLMUsage` | input_tokens, output_tokens, cost_usd |
| `errors` | `List[str]` | Error messages accumulated during the run |
| `stage_timings` | `Dict[str, float]` | stage_name → elapsed seconds |

---

### 4.5 `langgraph_writes`

**Owner:** agent-engine (Python `MongoCheckpointer`)

**Purpose:** Transient buffer for pending channel writes that have been submitted by a task but not yet folded into a committed checkpoint. LangGraph uses this for internal consistency during parallel node execution. Documents are short-lived: written by `put_writes()` and superseded once the next checkpoint commits.

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "LangGraphWrite",
    "required": ["thread_id", "checkpoint_id", "task_id", "channel", "value", "saved_at"],
    "properties": {
      "_id": { "bsonType": "objectId" },
      "thread_id": {
        "bsonType": "string",
        "description": "LangGraph thread ID. Part of compound index (thread_id, task_id)."
      },
      "checkpoint_id": {
        "bsonType": ["string", "null"],
        "description": "The checkpoint this write is associated with."
      },
      "task_id": {
        "bsonType": "string",
        "description": "LangGraph task identifier. Part of compound index (thread_id, task_id)."
      },
      "channel": {
        "bsonType": "string",
        "description": "SDLCState channel key being written (e.g. requirements, code_artifacts)."
      },
      "value": {
        "bsonType": "string",
        "description": "JSON-serialized value for this channel write."
      },
      "saved_at": {
        "bsonType": "date",
        "description": "UTC timestamp of the write."
      }
    }
  }
}
```

#### Example Document

```json
{
  "_id": { "$oid": "6615a2b3c4d5e6f7a8b9c0d1" },
  "thread_id": "f0e1d2c3-b4a5-6789-0123-456789abcdef",
  "checkpoint_id": "1ef8b4a0-1234-5678-9abc-def012345678",
  "task_id": "task-req-node-0001",
  "channel": "requirements",
  "value": "{\"user_stories\": [...], \"acceptance_criteria\": [...]}",
  "saved_at": { "$date": "2026-04-07T10:07:55.000Z" }
}
```

---

### 4.6 `sdlc_artifacts`

**Owner:** agent-engine (Python)

**Purpose:** Persistent store for all SDLC artifacts generated during a run. Each artifact (a user story set, an OpenAPI spec, a Java service file, a React component, a test suite, an ADR, a Terraform config, a pipeline YAML) is stored as a separate document with the full content text and Git metadata. Platform-core reads this collection to list artifacts for a run; the ReactJS artifact viewer fetches them via the platform-core REST API.

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "SdlcArtifact",
    "required": ["artifactId", "runId", "productId", "type", "stage", "content",
                 "contentHash", "sizeBytes", "createdAt"],
    "additionalProperties": true,
    "properties": {
      "_id": { "bsonType": "objectId" },
      "artifactId": {
        "bsonType": "string",
        "description": "UUID. Unique index. Matches CodeArtifact.artifact_id in SDLCState."
      },
      "runId": {
        "bsonType": "string",
        "description": "FK to agent_runs.runId. Indexed for run-scoped artifact listing."
      },
      "productId": {
        "bsonType": "string",
        "description": "FK to product identifier. Indexed for product history queries."
      },
      "type": {
        "bsonType": "string",
        "enum": ["user_stories", "openapi_spec", "java_service", "react_component",
                 "test_suite", "adr", "terraform", "pipeline_yaml"],
        "description": "Artifact type classifying what this document contains."
      },
      "stage": {
        "bsonType": "string",
        "description": "SDLC stage that produced this artifact (requirements / architecture / dev / qa / devops)."
      },
      "content": {
        "bsonType": "string",
        "description": "Full text content of the artifact. May be YAML, JSON, Java, TypeScript, Markdown, etc."
      },
      "contentHash": {
        "bsonType": "string",
        "description": "SHA-256 hash of content for deduplication and integrity verification."
      },
      "repo": {
        "bsonType": ["string", "null"],
        "description": "GitHub repository name where this artifact was committed (e.g. codepil/selfcare-service)."
      },
      "filePath": {
        "bsonType": ["string", "null"],
        "description": "File path within the repo (e.g. src/main/java/com/codepil/SelfCareService.java)."
      },
      "gitBranch": {
        "bsonType": ["string", "null"],
        "description": "Git branch name (e.g. feature/SC-42-selfcare-service)."
      },
      "gitCommitSha": {
        "bsonType": ["string", "null"],
        "description": "Full 40-character Git commit SHA for exact version pinning."
      },
      "sizeBytes": {
        "bsonType": "int",
        "description": "Content size in bytes. Used for storage accounting and pagination hints."
      },
      "createdAt": {
        "bsonType": "date",
        "description": "UTC timestamp when the artifact was written."
      }
    }
  }
}
```

#### Example Documents

```json
{
  "_id": { "$oid": "6615a2b3c4d5e6f7a8b9c0d2" },
  "artifactId": "art-001-a1b2c3d4",
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "productId": "SelfCare-001",
  "type": "user_stories",
  "stage": "requirements",
  "content": "# User Stories — SelfCare-001 / SC-42\n\n## US-001: View Bill Online\n**As a** customer,\n**I want to** view my current bill online,\n**So that** I can understand my charges without calling support.\n\n### Acceptance Criteria\n- [ ] Bill loads within 2 seconds for 95th percentile\n- [ ] Itemised charges are displayed per service line\n- [ ] SAP BAPI_BILLING_GETLIST called with customer BP number\n...",
  "contentHash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "repo": null,
  "filePath": null,
  "gitBranch": null,
  "gitCommitSha": null,
  "sizeBytes": 4820,
  "createdAt": { "$date": "2026-04-07T10:06:00.000Z" }
}
```

```json
{
  "_id": { "$oid": "6615a2b3c4d5e6f7a8b9c0d3" },
  "artifactId": "art-007-a1b2c3d4",
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "productId": "SelfCare-001",
  "type": "java_service",
  "stage": "dev",
  "content": "package com.codepil.selfcare;\n\nimport org.springframework.web.bind.annotation.*;\n// ...\n@RestController\n@RequestMapping(\"/api/v1/billing\")\npublic class BillingController {\n    // generated by DevCrew\n}",
  "contentHash": "sha256:abc123def456...",
  "repo": "codepil/selfcare-service",
  "filePath": "src/main/java/com/codepil/selfcare/BillingController.java",
  "gitBranch": "feature/SC-42-selfcare-service",
  "gitCommitSha": "4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b",
  "sizeBytes": 3240,
  "createdAt": { "$date": "2026-04-07T11:42:00.000Z" }
}
```

---

### 4.7 `context_snapshots`

**Owner:** platform-core (Spring Boot — fetches at run start; agent-engine reads at intake node)

**Purpose:** Before starting a LangGraph run, platform-core fetches data from enterprise systems (Jira, SAP, Figma, GitHub) and stores a complete snapshot here. This serves two purposes:
1. **Traceability** — preserves exactly what context the AI agents were given, enabling retrospective analysis of AI decisions.
2. **RAG pipeline input** — the snapshot content is chunked and embedded into `vector_embeddings` for Claude context injection during requirements and architecture stages.

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "ContextSnapshot",
    "required": ["runId", "fetchedAt"],
    "additionalProperties": true,
    "properties": {
      "_id": { "bsonType": "objectId" },
      "runId": {
        "bsonType": "string",
        "description": "FK to agent_runs.runId. Indexed — one snapshot per run."
      },
      "jiraEpic": {
        "bsonType": "object",
        "description": "Full Jira epic JSON as returned by the Jira REST API v3. Includes fields, description, subtasks, sprints, story points, and linked issues."
      },
      "sapSnapshot": {
        "bsonType": "object",
        "description": "Relevant SAP product catalog slice fetched via OData/BAPI. Includes material master records, pricing conditions, and integration point metadata relevant to the product being built."
      },
      "figmaSpec": {
        "bsonType": ["array", "null"],
        "description": "List of Figma component definitions extracted from the design file. Each entry includes component name, props, design tokens, and screen layout context.",
        "items": { "bsonType": "object" }
      },
      "existingApis": {
        "bsonType": ["array", "null"],
        "description": "List of existing OpenAPI spec objects from GitHub for the target product's repositories. Used to avoid generating duplicate endpoints.",
        "items": { "bsonType": "object" }
      },
      "fetchedAt": {
        "bsonType": "date",
        "description": "UTC timestamp when the enterprise data was fetched. Useful for cache invalidation and audit."
      },
      "embeddingId": {
        "bsonType": ["string", "null"],
        "description": "FK to vector_embeddings.embeddingId — points to the embedding generated from this snapshot's content."
      }
    }
  }
}
```

#### Example Document

```json
{
  "_id": { "$oid": "6615a2b3c4d5e6f7a8b9c0d4" },
  "runId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "jiraEpic": {
    "id": "10042",
    "key": "SC-42",
    "fields": {
      "summary": "SelfCare Portal — Online Billing & Payment",
      "description": "Enable customers to view bills and pay online...",
      "status": { "name": "In Progress" },
      "priority": { "name": "High" },
      "storyPoints": 34,
      "subtasks": [{ "key": "SC-43", "summary": "Bill view API" }]
    }
  },
  "sapSnapshot": {
    "materialGroup": "TEL-SELFCARE",
    "pricingConditions": ["ZPRC", "ZDIS"],
    "bapiEndpoints": ["BAPI_BILLING_GETLIST", "ZSD_SELFCARE_PAYMENT"],
    "integrationProfile": "S4HANA-2023"
  },
  "figmaSpec": [
    {
      "componentName": "BillSummaryCard",
      "props": ["billDate", "totalAmount", "currency"],
      "designTokens": { "primaryColor": "#0050A0", "fontFamily": "Inter" }
    }
  ],
  "existingApis": [
    {
      "repo": "codepil/customer-api",
      "path": "openapi.yaml",
      "info": { "title": "Customer API", "version": "2.1.0" }
    }
  ],
  "fetchedAt": { "$date": "2026-04-07T09:58:00.000Z" },
  "embeddingId": "emb-ctx-a1b2c3d4"
}
```

---

### 4.8 `vector_embeddings`

**Owner:** agent-engine (Python)

**Purpose:** Stores text embeddings generated from context snapshots and SDLC artifacts for Atlas Vector Search. The RAG pipeline uses this to retrieve relevant context chunks before invoking Claude — for example, retrieving similar past requirements when generating new user stories, or retrieving relevant API specs when generating architecture designs.

**Embedding model:** `text-embedding-3-small` (OpenAI) or `voyage-3` (Anthropic/Voyage) — 1536 dimensions. The `model` field records which model was used.

**Atlas Vector Search index** must be created on the `embedding` field (see Section 5).

#### JSON Schema

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "title": "VectorEmbedding",
    "required": ["embeddingId", "sourceType", "sourceId", "productId", "textChunk",
                 "embedding", "model", "createdAt"],
    "additionalProperties": true,
    "properties": {
      "_id": { "bsonType": "objectId" },
      "embeddingId": {
        "bsonType": "string",
        "description": "UUID. Unique index. Referenced by context_snapshots.embeddingId and sdlc_artifacts (future FK)."
      },
      "sourceType": {
        "bsonType": "string",
        "enum": ["context_snapshot", "sdlc_artifact", "audit_summary"],
        "description": "Classifies what content was embedded."
      },
      "sourceId": {
        "bsonType": "string",
        "description": "FK to the source document: runId (for context_snapshot), artifactId (for sdlc_artifact)."
      },
      "productId": {
        "bsonType": "string",
        "description": "Product identifier. Indexed to enable product-scoped vector search (pre-filter)."
      },
      "stage": {
        "bsonType": ["string", "null"],
        "description": "SDLC stage that produced the source content. Used as pre-filter for stage-scoped similarity search."
      },
      "textChunk": {
        "bsonType": "string",
        "description": "The text chunk that was embedded. Returned in search results for display and citation."
      },
      "embedding": {
        "bsonType": "array",
        "description": "1536-dimension float vector. Atlas Vector Search index targets this field.",
        "items": { "bsonType": "double" }
      },
      "model": {
        "bsonType": "string",
        "description": "Embedding model identifier (e.g. text-embedding-3-small, voyage-3)."
      },
      "createdAt": {
        "bsonType": "date"
      }
    }
  }
}
```

#### Example Document

```json
{
  "_id": { "$oid": "6615a2b3c4d5e6f7a8b9c0d5" },
  "embeddingId": "emb-ctx-a1b2c3d4",
  "sourceType": "context_snapshot",
  "sourceId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "productId": "SelfCare-001",
  "stage": "requirements",
  "textChunk": "Jira Epic SC-42: SelfCare Portal — Online Billing & Payment. Enable customers to view bills and pay online. SAP dependencies: BAPI_BILLING_GETLIST, ZSD_SELFCARE_PAYMENT. Figma components: BillSummaryCard, PaymentForm. Priority: High. Story points: 34.",
  "embedding": [0.0023, -0.0187, 0.0341, "... 1533 more floats ..."],
  "model": "text-embedding-3-small",
  "createdAt": { "$date": "2026-04-07T09:59:00.000Z" }
}
```

---

## 5. Index Strategy

### 5.1 `agent_runs`

| Field(s) | Index Type | Reason |
|---|---|---|
| `runId` | Unique ascending | Primary external lookup key used in all REST API paths and cross-collection FK joins |
| `status` | Ascending | Dashboard status-filter queries: `findByStatus("running")`, `findByStatus("waiting_approval")` |
| `productId` | Ascending | Product history view: `findByProductId("SelfCare-001")` |
| `createdAt` | Descending | Default sort for run list pagination (newest first) |
| `initiatedByUserId` | Ascending | User's run history: `findByInitiatedByUserId(oktaId)` |

### 5.2 `approval_requests`

| Field(s) | Index Type | Reason |
|---|---|---|
| `runId` | Ascending | Load approvals for a given run |
| `status` | Ascending | Pending approvals dashboard: `findByStatus("pending")` |
| `approvalStage` | Ascending | Filter by gate type (requirements vs. staging) |
| `(runId, approvalStage)` | Compound ascending | Find the current open approval gate for a run |

### 5.3 `audit_trail`

| Field(s) | Index Type | Reason |
|---|---|---|
| `(runId, timestampMs)` | Compound ascending | Primary query: all events for run X in chronological order. Defined as `@CompoundIndex` on `AuditEvent.java`. |
| `runId` | Ascending (covered by compound) | Supports `countByRunIdAndEventType` queries |
| `(runId, eventType)` | Compound ascending | Filter audit log by event type (error events, approval events) |
| `timestampMs` | Descending + TTL | TTL index for 2-year retention. See Section 6. |

### 5.4 `langgraph_checkpoints`

| Field(s) | Index Type | Reason |
|---|---|---|
| `(thread_id, checkpoint_id)` | Unique compound (desc on checkpoint_id) | Primary lookup: latest checkpoint for a thread. Defined in `MongoCheckpointer._ensure_indexes()`. |
| `thread_id` | Ascending (covered) | List all checkpoints for a thread (history replay) |
| `saved_at` | Ascending + TTL | TTL index for 90-day retention. See Section 6. |

### 5.5 `langgraph_writes`

| Field(s) | Index Type | Reason |
|---|---|---|
| `(thread_id, task_id)` | Compound ascending | Lookup pending writes for a specific task. Defined in `MongoCheckpointer._ensure_indexes()`. |
| `saved_at` | Ascending + TTL | TTL index for 7-day cleanup (writes should be cleared within seconds; 7-day safety net). |

### 5.6 `sdlc_artifacts`

| Field(s) | Index Type | Reason |
|---|---|---|
| `artifactId` | Unique ascending | External ID used in API responses and vector_embeddings.sourceId references |
| `runId` | Ascending | List all artifacts for a run |
| `productId` | Ascending | Product artifact history queries |
| `(productId, type)` | Compound ascending | Filter by artifact type within a product |
| `contentHash` | Ascending | Deduplication check before writing a new artifact |

### 5.7 `context_snapshots`

| Field(s) | Index Type | Reason |
|---|---|---|
| `runId` | Unique ascending | One snapshot per run; used for FK joins and run-scoped queries |
| `fetchedAt` | Descending | Latest snapshots for cache staleness checks |

### 5.8 `vector_embeddings`

| Field(s) | Index Type | Reason |
|---|---|---|
| `embeddingId` | Unique ascending | External FK target from context_snapshots.embeddingId |
| `productId` | Ascending | Pre-filter for product-scoped vector search queries |
| `sourceType` | Ascending | Pre-filter by source type |
| `embedding` | **Atlas Vector Search** (cosine, 1536 dims) | KNN similarity search for RAG retrieval |
| `createdAt` | Ascending + TTL | TTL index for 1-year retention |

#### Atlas Vector Search Index Definition

```json
{
  "name": "vector_embeddings_knn_idx",
  "type": "vectorSearch",
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "productId"
    },
    {
      "type": "filter",
      "path": "sourceType"
    },
    {
      "type": "filter",
      "path": "stage"
    }
  ]
}
```

**Usage pattern** (Atlas `$vectorSearch` aggregation):

```json
{
  "$vectorSearch": {
    "index": "vector_embeddings_knn_idx",
    "path": "embedding",
    "queryVector": ["<1536-float-array>"],
    "numCandidates": 150,
    "limit": 10,
    "filter": {
      "productId": { "$eq": "SelfCare-001" },
      "sourceType": { "$in": ["context_snapshot", "sdlc_artifact"] }
    }
  }
}
```

---

## 6. Retention and TTL Policy

MongoDB TTL indexes are used to automatically expire documents. TTL indexes delete documents when `expireAfterSeconds` elapses past the indexed date field.

| Collection | Retention Period | TTL Field | Expiry Setting | Rationale |
|---|---|---|---|---|
| `audit_trail` | **2 years** | `createdAt` | `expireAfterSeconds: 63072000` (730 days) | Regulatory compliance requires 2-year audit log retention. Older events are archived to S3 Glacier via Atlas Online Archive before TTL deletion. |
| `langgraph_checkpoints` | **90 days** | `saved_at` | `expireAfterSeconds: 7776000` (90 days) | Checkpoints are only needed for active runs and recent replay. After 90 days, runs are either complete or failed. State can be reconstructed from `audit_trail` if needed. |
| `langgraph_writes` | **7 days** | `saved_at` | `expireAfterSeconds: 604800` (7 days) | Writes are consumed within seconds during normal operation. 7-day TTL is a safety net for orphaned write documents from crashed agent-engine processes. |
| `vector_embeddings` | **1 year** | `createdAt` | `expireAfterSeconds: 31536000` (365 days) | Embeddings are regenerated on each new run. Older embeddings from superseded product versions are no longer queried. |
| `agent_runs` | **Indefinite** | — | No TTL | Run records are the business record of work performed. Kept permanently; moved to Atlas Online Archive after 1 year. |
| `approval_requests` | **Indefinite** | — | No TTL | Approval decisions are compliance records. Kept permanently; archived after 1 year. |
| `sdlc_artifacts` | **Indefinite** | — | No TTL | Generated artifacts are the deliverables of the platform. Kept for product history and reuse. |
| `context_snapshots` | **1 year** | `fetchedAt` | `expireAfterSeconds: 31536000` (365 days) | Snapshots older than 1 year are stale (enterprise data has changed). Kept for 1 year for retrospective analysis. |

### Atlas Online Archive Configuration

Collections with no TTL (`agent_runs`, `approval_requests`, `sdlc_artifacts`) should be configured for **Atlas Online Archive** to move documents older than 365 days to Atlas-managed S3-compatible cold storage. This keeps the working set in M30 RAM while preserving history at low cost.

```
Archive Rule:
  Collection: agent_runs
  Date field: createdAt
  Archive documents older than: 365 days
  Partition fields: productId, status
```

---

## 7. Atlas Cluster Sizing Recommendation

### Recommended Tier: M30 (Primary) with M10 Analytics Node

| Attribute | Specification |
|---|---|
| **Cluster tier** | M30 (dedicated) |
| **vCPUs** | 2 per node |
| **RAM** | 8 GB per node |
| **Storage** | 40 GB NVMe SSD (auto-scaling enabled, up to 1 TB) |
| **Replica set** | 3-node replica set (1 primary + 2 secondaries) |
| **Multi-region** | Primary: us-east-1 (AWS). Secondary: eu-west-1 (AWS). Read preference: `nearest` for analytics queries. |
| **Analytics node** | M10 in us-east-1 for BI Connector / aggregation queries without impacting the primary |

### Justification

**Storage:** The working set at year 1 is approximately 32 GB (see Section 2). M30 with auto-scaling covers this with headroom. The `sdlc_artifacts` collection (largest at ~20 GB/year) should have documents over 16 MB (MongoDB document limit) chunked — in practice, large Java services rarely exceed 500 KB.

**RAM:** The hot working set consists of active run checkpoints and recent audit events. With 10K runs/year and ~200 audit events/run, the past 7 days of audit events is ~200K documents × 2 KB = 400 MB. This fits comfortably in M30's 8 GB working set alongside the index footprint (~2 GB estimated for all indexes combined).

**Write throughput:** Peak write load occurs when multiple runs are active simultaneously. Each run generates approximately 12 checkpoint upserts + 200 audit inserts. At 20 concurrent runs, peak write rate is ~240 ops/sec — well within M30's IOPS capacity.

**Transactions:** `MongoConfig.java` enables `MongoTransactionManager`. Multi-document transactions require a replica set. M30 with a 3-node replica set satisfies this requirement.

**Vector Search:** Atlas Vector Search is available on M10+ dedicated clusters. The `vector_embeddings` collection at 50K documents × 1536 floats × 8 bytes ≈ 600 MB — fits in memory on M30 for hot vector search.

### Scaling Triggers

| Metric | Threshold | Action |
|---|---|---|
| Working set exceeds 60% of RAM | > 4.8 GB | Upgrade to M40 (16 GB RAM) |
| Storage exceeds 70% | > 28 GB | Auto-scaling triggers; review Online Archive configuration |
| Write latency (p99) > 20 ms | — | Add a shard or upgrade tier |
| Concurrent active runs > 50 | — | Evaluate M50 or horizontal sharding on `runId` |

### Sharding Strategy (future, > 50K runs/year)

If the platform scales beyond M50 capacity:

| Collection | Shard Key | Pattern |
|---|---|---|
| `audit_trail` | `{ runId: 1, timestampMs: 1 }` | Hashed on runId for even distribution |
| `langgraph_checkpoints` | `{ thread_id: "hashed" }` | Hashed for even write distribution |
| `sdlc_artifacts` | `{ productId: 1, runId: 1 }` | Range sharding to co-locate product artifacts |

---

## 8. Setup Scripts

The MongoDB initialization script for this schema is maintained in:

```
/Users/pavan.kumar.bijjala/Pavan-resume/Agentic-AI-platform/05-data/init-mongo.js
```

The script performs the following operations against the `agent_platform` database:

1. Creates all 8 collections with `$jsonSchema` validators
2. Creates all indexes defined in Section 5, including the TTL indexes from Section 6
3. Creates the Atlas Vector Search index definition for `vector_embeddings` (note: the vector search index must be applied via the Atlas UI or Atlas CLI after the collection is created — it cannot be created via `mongosh`)
4. Inserts reference data (e.g. product catalog seed records) if applicable

### Running the Init Script

```bash
# Against Atlas (replace with your connection string)
mongosh "mongodb+srv://<username>:<password>@<cluster>.mongodb.net/agent_platform" \
  --file /path/to/05-data/init-mongo.js

# Against local replica set for development
mongosh "mongodb://localhost:27017/agent_platform?replicaSet=rs0" \
  --file /path/to/05-data/init-mongo.js
```

### Atlas Vector Search Index (Atlas CLI)

The vector search index must be created separately after collection creation:

```bash
# Using Atlas CLI
atlas clusters search indexes create \
  --clusterName agent-platform-prod \
  --file /path/to/05-data/vector-search-index.json

# Or via Atlas UI:
# Data Services → Collections → vector_embeddings → Search Indexes → Create Search Index
# → Atlas Vector Search → JSON Editor → paste the index definition from Section 5.8
```

### Environment Variables

Both platform-core and agent-engine read the MongoDB connection string from environment variables:

**agent-engine (Python)** — from `src/platform/config.py`:
```bash
MONGO_URI="mongodb+srv://<user>:<pass>@<cluster>.mongodb.net"
MONGO_DB_NAME="agent_platform"
```

**platform-core (Java Spring Boot)** — from `application.yml`:
```yaml
spring:
  data:
    mongodb:
      uri: ${MONGO_URI}
      database: ${MONGO_DB_NAME:agent_platform}
```

---

## 9. Cross-References

### Java Domain Classes

| Collection | Java Class | File Path |
|---|---|---|
| `agent_runs` | `AgentRun extends BaseDocument` | `platform-core/platform-app/src/main/java/com/codepil/platform/domain/AgentRun.java` |
| `approval_requests` | `ApprovalRequest extends BaseDocument` | `platform-core/platform-app/src/main/java/com/codepil/platform/domain/ApprovalRequest.java` |
| `audit_trail` | `AuditEvent extends BaseDocument` | `platform-core/platform-app/src/main/java/com/codepil/platform/domain/AuditEvent.java` |
| *(base)* | `BaseDocument` | `platform-core/shared-java-libs/lib-mongodb/src/main/java/com/codepil/platform/mongodb/BaseDocument.java` |

**`BaseDocument` field mapping:**

| Java field | MongoDB field | Type | Spring Data annotation |
|---|---|---|---|
| `id` | `_id` | `String` (UUID) | `@Id` — auto-generated as `UUID.randomUUID().toString()` |
| `createdAt` | `createdAt` | `Date` | `@CreatedDate` — set on first save by `@EnableMongoAuditing` in `MongoConfig` |
| `updatedAt` | `updatedAt` | `Date` | `@LastModifiedDate` — updated on every save |

**Spring Data repository interfaces:**

| Repository | Relevant query methods |
|---|---|
| `AgentRunRepository` | `findByRunId`, `findByStatus`, `findByProductId`, `findByInitiatedByUserId` |
| `ApprovalRequestRepository` | `findByRunId`, `findByStatus` |
| `AuditEventRepository` | `findByRunIdOrderByTimestampMsAsc`, `findByRunIdAndEventTypeOrderByTimestampMsAsc`, `countByRunIdAndEventType` |

### Python SDLCState TypedDict

| Collection | Python Class | File Path |
|---|---|---|
| `langgraph_checkpoints` | `MongoCheckpointer` | `agent-engine/src/platform/checkpointing/mongo_checkpointer.py` |
| `langgraph_writes` | `MongoCheckpointer` | `agent-engine/src/platform/checkpointing/mongo_checkpointer.py` |
| *(state schema)* | `SDLCState(TypedDict)` | `agent-engine/src/platform/state/sdlc_state.py` |

**SDLCState sub-TypedDict hierarchy:**

```
SDLCState
├── LLMUsage              — input_tokens, output_tokens, cost_usd
├── RequirementsOutput    — user_stories, acceptance_criteria, sap_dependencies, ambiguities, jira_subtask_ids
├── ArchitectureOutput    — openapi_specs, mongodb_schemas, adr_ids, sap_integration_plan, service_dependency_graph
├── List[CodeArtifact]    — artifact_id, type, repo, file_path, git_branch, git_commit_sha, content_hash
├── QAResults             — passed, unit/integration/security/e2e test results, code_review_findings, failure_summary
└── DeploymentResult      — environment, service_urls, git_pr_url, pipeline_run_url, deployed_at
```

**LangGraph graph topology** (from `agent-engine/src/platform/graphs/sdlc_graph.py`):

```
intake → requirements → requirements_approval* → architecture → dev → qa → devops → staging_approval* → deploy_prod → END
                     ↳ (rejected) → requirements                    ↳ (retry) → qa_failed_handler → dev
                     ↳ (escalate) → error_handler → END              ↳ (escalate) → error_handler → END
                                                                                    ↳ (rejected) → dev
```

`*` = `interrupt_before` nodes — graph pauses here, persists full SDLCState to `langgraph_checkpoints`, and waits for `POST /api/v1/runs/{run_id}/resume` with the human decision.

### Key FK Relationships

```
agent_runs.runId
  ├──► approval_requests.runId     (1 run : N approval requests)
  ├──► audit_trail.runId           (1 run : N audit events, append-only)
  ├──► sdlc_artifacts.runId        (1 run : N artifacts)
  └──► context_snapshots.runId     (1 run : 1 snapshot)

agent_runs.threadId
  └──► langgraph_checkpoints.thread_id   (1 run : N checkpoints, one per node)

context_snapshots.embeddingId
  └──► vector_embeddings.embeddingId     (1 snapshot : 1+ embeddings, chunked)

sdlc_artifacts.artifactId
  └──► vector_embeddings.sourceId        (1 artifact : 1 embedding)
```

---

*Document maintained by the Platform Engineering team. For schema changes, open a PR against this file and the companion `init-mongo.js` script. Breaking index changes require a coordinated deployment with both platform-core and agent-engine.*
