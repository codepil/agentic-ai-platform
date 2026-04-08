// =============================================================================
// init-mongo.js — MongoDB initialization script for Agentic AI Platform
// =============================================================================
// Run with:
//   mongosh "$MONGO_URI" --file 05-data/init-mongo.js
//
// This script is fully idempotent — safe to run multiple times.
// Existing collections are left intact; indexes and validators are upserted.
// =============================================================================

// =============================================================================
// SECTION 0 — Switch to the target database
// =============================================================================
db = db.getSiblingDB("agent_platform");
print("\n=== Agentic AI Platform — MongoDB Init ===");
print("Target database: " + db.getName());
print("Timestamp: " + new Date().toISOString());
print("");

// =============================================================================
// SECTION 1 — Helper utilities
// =============================================================================

/**
 * Create a collection with a $jsonSchema validator.
 * If the collection already exists the validator is updated via collMod.
 * Errors are caught so the script remains idempotent.
 */
function createOrUpdateCollection(name, options) {
  try {
    db.createCollection(name, options);
    print("[CREATE] Collection created: " + name);
  } catch (e) {
    if (e.codeName === "NamespaceExists" || e.code === 48) {
      // Collection exists — apply updated validator if one is supplied
      if (options && options.validator) {
        try {
          db.runCommand(
            Object.assign({ collMod: name }, options)
          );
          print("[UPDATE] Collection already exists, validator refreshed: " + name);
        } catch (modErr) {
          print("[WARN]   Could not update validator for " + name + ": " + modErr.message);
        }
      } else {
        print("[SKIP]   Collection already exists (no validator): " + name);
      }
    } else {
      print("[ERROR]  Could not create collection " + name + ": " + e.message);
    }
  }
}

/**
 * Create an index idempotently.
 * MongoDB ignores duplicate index-creation requests for identical key+options.
 */
function ensureIndex(collectionName, keys, options) {
  try {
    db[collectionName].createIndex(keys, options);
    const label = options && options.name ? options.name : JSON.stringify(keys);
    print("[INDEX]  " + collectionName + " — " + label);
  } catch (e) {
    print("[WARN]   Index on " + collectionName + " skipped: " + e.message);
  }
}

// =============================================================================
// SECTION 2 — Create collections with $jsonSchema validators
// =============================================================================
print("--- Section 2: Creating collections ---\n");

// ---------------- 2.1  agent_runs ----------------
createOrUpdateCollection("agent_runs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["runId", "threadId", "productId", "jiraEpicId", "status", "currentStage"],
      properties: {
        runId:             { bsonType: "string",  description: "Unique run identifier (required)" },
        threadId:          { bsonType: "string",  description: "LangGraph thread ID (required)" },
        productId:         { bsonType: "string",  description: "Product/project identifier (required)" },
        jiraEpicId:        { bsonType: "string",  description: "Jira epic key (required)" },
        status: {
          bsonType: "string",
          enum: ["running", "waiting_approval", "completed", "failed", "escalated"],
          description: "Current lifecycle status (required)"
        },
        currentStage:      { bsonType: "string",  description: "Active SDLC stage name (required)" },
        approvalStage:     { bsonType: ["string", "null"], description: "Stage awaiting approval (nullable)" },
        qaIteration:       { bsonType: ["int", "null"],    description: "QA retry count" },
        llmUsage: {
          bsonType: ["object", "null"],
          properties: {
            input_tokens:  { bsonType: "int" },
            output_tokens: { bsonType: "int" },
            cost_usd:      { bsonType: "double" }
          }
        },
        errors:              { bsonType: ["array", "null"], items: { bsonType: "string" } },
        initiatedByUserId:   { bsonType: ["string", "null"] },
        createdAt:           { bsonType: ["date", "null"] },
        updatedAt:           { bsonType: ["date", "null"] }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// ---------------- 2.2  approval_requests ----------------
createOrUpdateCollection("approval_requests", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["runId", "approvalStage", "status"],
      properties: {
        runId: { bsonType: "string", description: "Parent run ID (required)" },
        approvalStage: {
          bsonType: "string",
          enum: ["requirements", "staging"],
          description: "Stage requiring approval (required)"
        },
        status: {
          bsonType: "string",
          enum: ["pending", "approved", "rejected"],
          description: "Decision status (required)"
        },
        artifactSummary: { bsonType: ["string", "null"] },
        decision:        { bsonType: ["string", "null"] },
        feedback:        { bsonType: ["string", "null"] },
        approvedBy:      { bsonType: ["string", "null"] },
        decidedAt:       { bsonType: ["date", "null"] },
        createdAt:       { bsonType: ["date", "null"] },
        updatedAt:       { bsonType: ["date", "null"] }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// ---------------- 2.3  audit_trail ----------------
createOrUpdateCollection("audit_trail", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["runId", "eventType", "rawPayload", "timestampMs"],
      properties: {
        runId:     { bsonType: "string", description: "Parent run ID (required)" },
        agentName: { bsonType: ["string", "null"] },
        eventType: {
          bsonType: "string",
          enum: [
            "thinking", "tool_call", "state_update", "stage_complete",
            "approval_requested", "run_complete", "error"
          ],
          description: "Event category (required)"
        },
        stage:      { bsonType: ["string", "null"] },
        rawPayload: { bsonType: "string",  description: "JSON-serialised agent payload (required)" },
        timestampMs:{ bsonType: "long",    description: "Unix epoch milliseconds (required)" },
        createdAt:  { bsonType: ["date", "null"] }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// ---------------- 2.4  sdlc_artifacts ----------------
createOrUpdateCollection("sdlc_artifacts", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["artifactId", "runId", "productId", "type", "stage"],
      properties: {
        artifactId: { bsonType: "string", description: "Unique artifact ID (required)" },
        runId:      { bsonType: "string", description: "Parent run ID (required)" },
        productId:  { bsonType: "string", description: "Product identifier (required)" },
        type: {
          bsonType: "string",
          enum: [
            "user_stories", "openapi_spec", "java_service", "react_component",
            "test_suite", "adr", "terraform", "pipeline_yaml"
          ],
          description: "Artifact type (required)"
        },
        stage:       { bsonType: "string",  description: "SDLC stage that produced this artifact (required)" },
        content:     { bsonType: ["string", "null"] },
        contentHash: { bsonType: ["string", "null"] },
        repo:        { bsonType: ["string", "null"] },
        filePath:    { bsonType: ["string", "null"] },
        gitBranch:   { bsonType: ["string", "null"] },
        gitCommitSha:{ bsonType: ["string", "null"] },
        sizeBytes:   { bsonType: ["int", "null"] },
        createdAt:   { bsonType: ["date", "null"] }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// ---------------- 2.5  context_snapshots ----------------
createOrUpdateCollection("context_snapshots", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["runId", "fetchedAt"],
      properties: {
        runId:       { bsonType: "string", description: "Run ID — unique per snapshot (required)" },
        jiraEpic:    { bsonType: ["object", "null"] },
        sapSnapshot: { bsonType: ["object", "null"] },
        figmaSpec:   { bsonType: ["object", "null"] },
        existingApis:{ bsonType: ["array", "null"] },
        fetchedAt:   { bsonType: "date",   description: "When external data was fetched (required)" },
        embeddingId: { bsonType: ["string", "null"] }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// ---------------- 2.6  vector_embeddings ----------------
createOrUpdateCollection("vector_embeddings", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["embeddingId", "sourceId", "productId", "textChunk", "embedding"],
      properties: {
        embeddingId: { bsonType: "string", description: "Unique embedding ID (required)" },
        sourceType: {
          bsonType: ["string", "null"],
          enum: ["context_snapshot", "sdlc_artifact", "audit_summary", null]
        },
        sourceId:   { bsonType: "string", description: "ID of the originating document (required)" },
        productId:  { bsonType: "string", description: "Product identifier (required)" },
        stage:      { bsonType: ["string", "null"] },
        textChunk:  { bsonType: "string", description: "Source text that was embedded (required)" },
        embedding: {
          bsonType: "array",
          description: "1536-dimensional float vector (required)",
          items: { bsonType: "double" }
        },
        model:     { bsonType: ["string", "null"] },
        createdAt: { bsonType: ["date", "null"] }
      }
    }
  },
  validationLevel: "moderate",
  validationAction: "warn"
});

// ---------------- 2.7  langgraph_checkpoints ----------------
// LangGraph manages its own document format; no strict validator applied.
createOrUpdateCollection("langgraph_checkpoints", {
  comment: "Managed by LangGraph-MongoDB checkpoint saver. No application-level validator — LangGraph owns the schema."
});

// ---------------- 2.8  langgraph_writes ----------------
createOrUpdateCollection("langgraph_writes", {
  comment: "Managed by LangGraph-MongoDB checkpoint saver (pending writes). No application-level validator."
});

// =============================================================================
// SECTION 3 — Regular indexes
// =============================================================================
print("\n--- Section 3: Creating regular indexes ---\n");

// ---- agent_runs ----
ensureIndex("agent_runs", { runId: 1 },                      { unique: true,  name: "runId_unique" });
ensureIndex("agent_runs", { productId: 1 },                  { name: "productId_1" });
ensureIndex("agent_runs", { status: 1 },                     { name: "status_1" });
ensureIndex("agent_runs", { initiatedByUserId: 1 },          { name: "initiatedByUserId_1" });
ensureIndex("agent_runs", { status: 1, createdAt: -1 },      { name: "status_createdAt_compound" });

// ---- approval_requests ----
ensureIndex("approval_requests", { runId: 1 },                          { name: "runId_1" });
ensureIndex("approval_requests", { status: 1 },                         { name: "status_1" });
ensureIndex("approval_requests", { runId: 1, approvalStage: 1 },        { name: "runId_approvalStage_compound" });
ensureIndex("approval_requests", { approvedBy: 1 },                     { name: "approvedBy_1" });

// ---- audit_trail ----
ensureIndex("audit_trail", { runId: 1 },                   { name: "runId_1" });
ensureIndex("audit_trail", { runId: 1, timestampMs: 1 },   { name: "runId_timestampMs_compound" }); // PRIMARY query pattern
ensureIndex("audit_trail", { eventType: 1 },               { name: "eventType_1" });

// ---- sdlc_artifacts ----
ensureIndex("sdlc_artifacts", { artifactId: 1 },                        { unique: true, name: "artifactId_unique" });
ensureIndex("sdlc_artifacts", { runId: 1 },                             { name: "runId_1" });
ensureIndex("sdlc_artifacts", { productId: 1 },                         { name: "productId_1" });
ensureIndex("sdlc_artifacts", { productId: 1, type: 1, stage: 1 },     { name: "productId_type_stage_compound" });

// ---- context_snapshots ----
ensureIndex("context_snapshots", { runId: 1 },       { unique: true, name: "runId_unique" });
ensureIndex("context_snapshots", { fetchedAt: -1 },  { name: "fetchedAt_desc" });

// ---- vector_embeddings ----
ensureIndex("vector_embeddings", { embeddingId: 1 },               { unique: true, name: "embeddingId_unique" });
ensureIndex("vector_embeddings", { sourceId: 1 },                  { name: "sourceId_1" });
ensureIndex("vector_embeddings", { productId: 1 },                 { name: "productId_1" });
ensureIndex("vector_embeddings", { sourceType: 1, productId: 1 },  { name: "sourceType_productId_compound" });

// ---- langgraph_checkpoints ----
ensureIndex("langgraph_checkpoints", { thread_id: 1 },                    { name: "thread_id_1" });
ensureIndex("langgraph_checkpoints", { thread_id: 1, checkpoint_id: 1 },  { name: "thread_id_checkpoint_id_compound" });

// ---- langgraph_writes ----
ensureIndex("langgraph_writes", { thread_id: 1 }, { name: "thread_id_1" });
ensureIndex("langgraph_writes", { task_id: 1 },   { name: "task_id_1" });

// =============================================================================
// SECTION 4 — TTL indexes
// =============================================================================
print("\n--- Section 4: Creating TTL indexes ---\n");

// audit_trail — 2 years (63,072,000 s)
ensureIndex("audit_trail", { createdAt: 1 }, {
  expireAfterSeconds: 63072000,
  name: "createdAt_ttl_2yr"
});

// langgraph_checkpoints — 90 days (7,776,000 s)
ensureIndex("langgraph_checkpoints", { ts: 1 }, {
  expireAfterSeconds: 7776000,
  name: "ts_ttl_90d"
});

// langgraph_writes — 7 days (604,800 s)
ensureIndex("langgraph_writes", { ts: 1 }, {
  expireAfterSeconds: 604800,
  name: "ts_ttl_7d"
});

// vector_embeddings — 1 year (31,536,000 s)
ensureIndex("vector_embeddings", { createdAt: 1 }, {
  expireAfterSeconds: 31536000,
  name: "createdAt_ttl_1yr"
});

// context_snapshots — 1 year (31,536,000 s)
ensureIndex("context_snapshots", { fetchedAt: 1 }, {
  expireAfterSeconds: 31536000,
  name: "fetchedAt_ttl_1yr"
});

// =============================================================================
// SECTION 5 — Atlas Vector Search index instructions
// =============================================================================
// NOTE: Atlas Vector Search indexes CANNOT be created via mongosh.
// Use the Atlas CLI or Atlas UI after this script completes.
//
// Atlas CLI command:
//   atlas clusters search indexes create \
//     --clusterName <cluster> \
//     --db agent_platform \
//     --collection vector_embeddings \
//     --file 05-data/vector-search-index.json
//
// Example 05-data/vector-search-index.json:
// {
//   "name": "vector_index",
//   "type": "vectorSearch",
//   "definition": {
//     "fields": [
//       {
//         "type": "vector",
//         "path": "embedding",
//         "numDimensions": 1536,
//         "similarity": "cosine"
//       },
//       {
//         "type": "filter",
//         "path": "productId"
//       },
//       {
//         "type": "filter",
//         "path": "sourceType"
//       },
//       {
//         "type": "filter",
//         "path": "stage"
//       }
//     ]
//   }
// }
//
// Atlas UI path:
//   Cluster → Search Indexes → Create Search Index → JSON Editor
//   Select database: agent_platform, collection: vector_embeddings
// =============================================================================
print("\n--- Section 5: Atlas Vector Search ---");
print("[INFO]  Vector Search index must be created via Atlas CLI or Atlas UI.");
print("[INFO]  See comments in this script (Section 5) for the CLI command and JSON definition.");

// =============================================================================
// SECTION 6 — Seed test documents
// =============================================================================
// All test documents carry _testData: true for easy bulk-delete:
//   db.agent_runs.deleteMany({ _testData: true })
// =============================================================================
print("\n--- Section 6: Seeding test documents ---\n");

const TEST_RUN_ID       = "TEST-RUN-000";
const TEST_THREAD_ID    = "TEST-THREAD-000";
const TEST_PRODUCT_ID   = "TEST-PRODUCT-001";
const TEST_ARTIFACT_ID  = "TEST-ARTIFACT-000";
const TEST_EMBEDDING_ID = "TEST-EMBEDDING-000";
const NOW               = new Date();

function seedDocument(collectionName, doc) {
  try {
    // Use replaceOne with upsert so repeated runs don't duplicate seed rows
    const filter = doc._seedKey ? doc._seedKey : { _testData: true, runId: doc.runId };
    delete doc._seedKey;
    const result = db[collectionName].replaceOne(filter, doc, { upsert: true });
    const action = result.upsertedCount > 0 ? "INSERTED" : "REPLACED";
    print("[SEED " + action + "] " + collectionName);
  } catch (e) {
    print("[WARN]   Seed failed for " + collectionName + ": " + e.message);
  }
}

// agent_runs
seedDocument("agent_runs", {
  _testData: true,
  _seedKey: { _testData: true, runId: TEST_RUN_ID },
  runId:            TEST_RUN_ID,
  threadId:         TEST_THREAD_ID,
  productId:        TEST_PRODUCT_ID,
  jiraEpicId:       "JIRA-TEST-001",
  status:           "completed",
  currentStage:     "pipeline",
  approvalStage:    null,
  qaIteration:      NumberInt(1),
  llmUsage:         { input_tokens: NumberInt(1200), output_tokens: NumberInt(800), cost_usd: 0.0045 },
  errors:           [],
  initiatedByUserId:"test-user-001",
  createdAt:        NOW,
  updatedAt:        NOW
});

// approval_requests
seedDocument("approval_requests", {
  _testData: true,
  _seedKey: { _testData: true, runId: TEST_RUN_ID, approvalStage: "requirements" },
  runId:          TEST_RUN_ID,
  approvalStage:  "requirements",
  status:         "approved",
  artifactSummary:"User stories for TEST-PRODUCT-001 generated by requirements agent.",
  decision:       "approved",
  feedback:       "Looks good — proceed to design.",
  approvedBy:     "test-user-001",
  decidedAt:      NOW,
  createdAt:      NOW,
  updatedAt:      NOW
});

// audit_trail
seedDocument("audit_trail", {
  _testData: true,
  _seedKey: { _testData: true, runId: TEST_RUN_ID, eventType: "run_complete" },
  runId:       TEST_RUN_ID,
  agentName:   "orchestrator",
  eventType:   "run_complete",
  stage:       "pipeline",
  rawPayload:  JSON.stringify({ message: "Test run completed successfully.", runId: TEST_RUN_ID }),
  timestampMs: NumberLong(NOW.getTime()),
  createdAt:   NOW
});

// sdlc_artifacts
seedDocument("sdlc_artifacts", {
  _testData: true,
  _seedKey: { _testData: true, artifactId: TEST_ARTIFACT_ID },
  artifactId:   TEST_ARTIFACT_ID,
  runId:        TEST_RUN_ID,
  productId:    TEST_PRODUCT_ID,
  type:         "user_stories",
  stage:        "requirements",
  content:      "# User Stories\n\nAs a developer, I want to verify the init script works correctly.",
  contentHash:  "sha256:abc123test",
  repo:         "github.com/org/test-repo",
  filePath:     "docs/user-stories.md",
  gitBranch:    "feature/test-init",
  gitCommitSha: "abc123def456",
  sizeBytes:    NumberInt(512),
  createdAt:    NOW
});

// context_snapshots
seedDocument("context_snapshots", {
  _testData: true,
  _seedKey: { _testData: true, runId: TEST_RUN_ID },
  runId:       TEST_RUN_ID,
  jiraEpic:    { key: "JIRA-TEST-001", summary: "Test epic for init verification", status: "In Progress" },
  sapSnapshot: { module: "SD", version: "S/4HANA 2023", relevantEntities: ["SalesOrder", "Customer"] },
  figmaSpec:   { fileId: "test-figma-file", pages: ["Home", "Dashboard"] },
  existingApis:[ { name: "order-service", version: "v2", baseUrl: "https://api.internal/orders" } ],
  fetchedAt:   NOW,
  embeddingId: TEST_EMBEDDING_ID
});

// vector_embeddings — use a dummy 1536-dim zero vector for test purposes
const ZERO_VECTOR = Array.from({ length: 1536 }, () => 0.0);
seedDocument("vector_embeddings", {
  _testData: true,
  _seedKey: { _testData: true, embeddingId: TEST_EMBEDDING_ID },
  embeddingId: TEST_EMBEDDING_ID,
  sourceType:  "context_snapshot",
  sourceId:    TEST_RUN_ID,
  productId:   TEST_PRODUCT_ID,
  stage:       "requirements",
  textChunk:   "Test epic for init verification — JIRA-TEST-001 (seed document, safe to delete).",
  embedding:   ZERO_VECTOR,
  model:       "text-embedding-3-small",
  createdAt:   NOW
});

// langgraph_checkpoints — freeform document (LangGraph format approximation)
seedDocument("langgraph_checkpoints", {
  _testData: true,
  _seedKey: { _testData: true, thread_id: TEST_THREAD_ID },
  thread_id:     TEST_THREAD_ID,
  checkpoint_id: "TEST-CHECKPOINT-000",
  parent_id:     null,
  type:          "checkpoint",
  checkpoint:    { v: 1, ts: NOW.toISOString(), channel_values: { messages: [] }, channel_versions: {}, versions_seen: {} },
  metadata:      { source: "init-script-seed", step: 0 },
  ts:            NOW
});

// langgraph_writes — freeform document
seedDocument("langgraph_writes", {
  _testData: true,
  _seedKey: { _testData: true, thread_id: TEST_THREAD_ID },
  thread_id:     TEST_THREAD_ID,
  checkpoint_id: "TEST-CHECKPOINT-000",
  task_id:       "TEST-TASK-000",
  idx:           NumberInt(0),
  channel:       "__root__",
  type:          "write",
  value:         { message: "Seed write — safe to delete." },
  ts:            NOW
});

print("\n[INFO]  To remove ALL seed documents after verification:");
print('        db.agent_runs.deleteMany({ _testData: true })');
print('        db.approval_requests.deleteMany({ _testData: true })');
print('        db.audit_trail.deleteMany({ _testData: true })');
print('        db.sdlc_artifacts.deleteMany({ _testData: true })');
print('        db.context_snapshots.deleteMany({ _testData: true })');
print('        db.vector_embeddings.deleteMany({ _testData: true })');
print('        db.langgraph_checkpoints.deleteMany({ _testData: true })');
print('        db.langgraph_writes.deleteMany({ _testData: true })');

// =============================================================================
// SECTION 7 — Summary
// =============================================================================
print("\n--- Section 7: Summary ---\n");

const collections = [
  "agent_runs",
  "approval_requests",
  "audit_trail",
  "sdlc_artifacts",
  "context_snapshots",
  "vector_embeddings",
  "langgraph_checkpoints",
  "langgraph_writes"
];

print("Collection                  | Documents");
print("----------------------------+----------");

let totalDocs = 0;
collections.forEach(function(name) {
  try {
    const count = db[name].countDocuments();
    totalDocs += count;
    const padded = (name + "                            ").substring(0, 28);
    print(padded + "| " + count);
  } catch (e) {
    print(name + " | ERROR: " + e.message);
  }
});

print("----------------------------+----------");
print("TOTAL                       | " + totalDocs);
print("\n=== Init complete. Database: agent_platform ===\n");
