# Atlas Vector Search — Agentic AI Platform

MongoDB Atlas Vector Search backs the semantic memory layer of the platform. Every significant artifact produced or consumed during an SDLC run is embedded and stored so that future runs can recall relevant past context without re-querying external systems.

---

## 1. Purpose

### 1.1 Context Enrichment Before a Run (platform-core)

When `AgentRunService` receives a new run request it pre-fetches context snapshots from Jira, SAP, and Figma. Before forwarding the enriched payload to agent-engine, platform-core embeds the combined snapshot text and queries the `vector_embeddings` collection for the top-3 most similar past runs for the same product. Those summaries are injected into the context payload, giving agent-engine crews an instant view of what was done before — without requiring the crews to call external APIs themselves.

### 1.2 Requirements Crew — Avoiding Duplicate User Stories

The Requirements Crew queries `vector_embeddings` filtered by `stage=requirements` and `productId` to surface user stories from past runs that are semantically close to the ones it is about to generate. Any story scoring above a configurable similarity threshold is flagged so the crew can reference the existing story ID rather than create a duplicate.

### 1.3 Architecture Crew — Reusing Service Patterns

The Architecture Crew filters by `stage=architecture` to find OpenAPI specs and service decomposition documents from prior runs across all products. Proven patterns (e.g., a BFF gateway spec or an event-driven service boundary) can be cited in the new architecture decision rather than re-derived from scratch.

### 1.4 Dev Crew — Reusable Code Artifacts Across Product Lines

The Dev Crew queries `sourceType=sdlc_artifact` and `stage=dev` without restricting `productId`, enabling cross-product code reuse. A React component or a Spring Boot integration module written for one product line can be surfaced and adapted rather than regenerated.

---

## 2. Collection Schema

**Database:** `agent_platform`  
**Collection:** `vector_embeddings`

### 2.1 Field Reference

| Field | Type | Description |
|---|---|---|
| `embeddingId` | String (UUID) | Surrogate key for the embedding document |
| `sourceType` | String (enum) | `context_snapshot`, `sdlc_artifact`, `audit_summary` |
| `sourceId` | String | ID of the originating document (run ID, artifact ID, etc.) |
| `productId` | String | Product line identifier, e.g. `SelfCare-001` |
| `stage` | String (enum) | `requirements`, `architecture`, `dev`, `qa`, `audit`, `pre-run` |
| `textChunk` | String | The raw text that was embedded (kept for debugging and re-embedding) |
| `embedding` | Array[Float] | 1536-dimension vector (OpenAI `text-embedding-3-small` or Anthropic compatible) |
| `model` | String | Embedding model identifier, e.g. `text-embedding-3-small` |
| `createdAt` | Date (ISODate) | Insertion timestamp |

### 2.2 Example Document

```json
{
  "_id": { "$oid": "665f1a2b3c4d5e6f7a8b9c0d" },
  "embeddingId": "emb-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "sourceType": "context_snapshot",
  "sourceId": "run-20250401-SelfCare-001-uuid",
  "productId": "SelfCare-001",
  "stage": "pre-run",
  "textChunk": "Jira epic SC-400: Unified login flow. Open defects: SC-422 (OTP timeout), SC-431 (biometric fallback). SAP CRM customer segments: retail, SME. Figma design v3.2: updated onboarding screens with passkey support.",
  "embedding": [0.0021, -0.0183, 0.0074, "... 1533 more floats ..."],
  "model": "text-embedding-3-small",
  "createdAt": { "$date": "2025-04-01T08:30:00Z" }
}
```

### 2.3 Indexes (Non-Vector)

In addition to the Atlas Vector Search index, create these standard MongoDB indexes to support filter-only queries and document retrieval:

```javascript
// Composite index for filter-only lookups (no vector component)
db.vector_embeddings.createIndex({ productId: 1, sourceType: 1, stage: 1 })

// TTL index — expire audit_summary embeddings after 365 days (optional)
db.vector_embeddings.createIndex(
  { createdAt: 1 },
  { expireAfterSeconds: 31536000, partialFilterExpression: { sourceType: "audit_summary" } }
)
```

---

## 3. Index Setup

The index definition lives at `05-data/vector-search-index.json`. It registers the `embedding` field as a 1536-dimension cosine vector and the `productId`, `sourceType`, and `stage` fields as filter paths so they can be used in `$vectorSearch` pre-filters without a full collection scan.

### 3.1 Atlas CLI

```bash
atlas clusters search indexes create \
  --clusterName <your-cluster-name> \
  --db agent_platform \
  --collection vector_embeddings \
  --file 05-data/vector-search-index.json
```

Verify the index is READY before running queries:

```bash
atlas clusters search indexes list \
  --clusterName <your-cluster-name> \
  --db agent_platform \
  --collection vector_embeddings
```

### 3.2 Atlas UI Steps

1. Open your Atlas project and navigate to **Database > Collections**.
2. Select the `agent_platform` database and the `vector_embeddings` collection.
3. Click the **Search Indexes** tab, then **Create Search Index**.
4. Choose **Atlas Vector Search**, select **JSON Editor**, and paste the contents of `vector-search-index.json`.
5. Set the index name to `vector_embedding_index` and click **Next > Create Search Index**.
6. Wait for the status indicator to show **READY** (typically under two minutes on a warm cluster).

### 3.3 Index Definition Reference

See `05-data/vector-search-index.json` for the exact payload. Key parameters:

```json
{
  "name": "vector_embedding_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1536,
        "similarity": "cosine"
      },
      { "type": "filter", "path": "productId" },
      { "type": "filter", "path": "sourceType" },
      { "type": "filter", "path": "stage" }
    ]
  }
}
```

`cosine` similarity is preferred over `euclidean` here because normalized embedding models (OpenAI `text-embedding-3-small`, Anthropic) encode semantic direction rather than magnitude, and cosine distance is invariant to vector scale.

---

## 4. Embedding Generation

### 4.1 Java — platform-core (`AgentRunService.java`)

After assembling the context snapshot from Jira, SAP, and Figma, `AgentRunService` calls an embedding endpoint and persists the result before forwarding the enriched context to agent-engine.

```java
// Simplified excerpt from AgentRunService.java
// Full implementation in: 02-platform-core/src/main/java/com/agentplatform/service/AgentRunService.java

private void embedAndStoreContextSnapshot(AgentRun run, String snapshotText) {
    // 1. Call embedding endpoint (OpenAI-compatible interface)
    EmbeddingResponse response = embeddingClient.embed(
        EmbeddingRequest.builder()
            .model("text-embedding-3-small")
            .input(snapshotText)
            .build()
    );

    List<Double> vector = response.getData().get(0).getEmbedding();

    // 2. Build the vector_embeddings document
    VectorEmbeddingDocument doc = VectorEmbeddingDocument.builder()
        .embeddingId(UUID.randomUUID().toString())
        .sourceType("context_snapshot")
        .sourceId(run.getRunId())
        .productId(run.getProductId())
        .stage("pre-run")
        .textChunk(snapshotText)
        .embedding(vector)
        .model("text-embedding-3-small")
        .createdAt(new Date())
        .build();

    // 3. Persist to MongoDB
    mongoTemplate.insert(doc, "vector_embeddings");
}
```

The `EmbeddingClient` is a thin wrapper around `RestTemplate` / `WebClient` that targets `EMBEDDING_API_URL` from environment config. Switching between OpenAI and Anthropic requires only changing the URL and auth header — the 1536-dimension contract is maintained on both.

### 4.2 Python — agent-engine (CrewAI crews)

Crews use PyMongo directly to both query for similar artifacts and (optionally) store new embeddings for artifacts they generate.

```python
# Simplified excerpt — agent-engine/app/vector/embedding_service.py

import openai
from pymongo import MongoClient
from app.config import settings

client = MongoClient(settings.MONGODB_URI)
collection = client["agent_platform"]["vector_embeddings"]


def generate_embedding(text: str) -> list[float]:
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def store_artifact_embedding(
    source_id: str,
    product_id: str,
    stage: str,
    text_chunk: str,
    embedding: list[float],
) -> str:
    import uuid
    from datetime import datetime, timezone

    doc = {
        "embeddingId": str(uuid.uuid4()),
        "sourceType": "sdlc_artifact",
        "sourceId": source_id,
        "productId": product_id,
        "stage": stage,
        "textChunk": text_chunk,
        "embedding": embedding,
        "model": "text-embedding-3-small",
        "createdAt": datetime.now(timezone.utc),
    }
    result = collection.insert_one(doc)
    return str(result.inserted_id)
```

---

## 5. Query Patterns

All three patterns use the `$vectorSearch` aggregation stage with a `filter` to restrict the candidate set before the ANN search runs. This is more efficient than post-filtering and is natively supported by the Atlas Vector Search index because `productId`, `sourceType`, and `stage` are registered as filter fields.

### 5.1 Find Top-5 Similar Context Snapshots for a Product

**Use case:** platform-core context enrichment — find the 5 most semantically similar past pre-run snapshots for `SelfCare-001` before starting a new run.

#### MongoDB Aggregation Pipeline (JSON)

```json
[
  {
    "$vectorSearch": {
      "index": "vector_embedding_index",
      "path": "embedding",
      "queryVector": "<1536-float array>",
      "numCandidates": 100,
      "limit": 5,
      "filter": {
        "productId": { "$eq": "SelfCare-001" },
        "sourceType": { "$eq": "context_snapshot" }
      }
    }
  },
  {
    "$project": {
      "_id": 0,
      "sourceId": 1,
      "textChunk": 1,
      "stage": 1,
      "createdAt": 1,
      "score": { "$meta": "vectorSearchScore" }
    }
  }
]
```

#### Python (PyMongo)

```python
# agent-engine/app/vector/similarity_service.py

def find_similar_context_snapshots(
    query_embedding: list[float],
    product_id: str,
    top_k: int = 5,
) -> list[dict]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_embedding_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": top_k * 20,
                "limit": top_k,
                "filter": {
                    "productId": {"$eq": product_id},
                    "sourceType": {"$eq": "context_snapshot"},
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "sourceId": 1,
                "textChunk": 1,
                "stage": 1,
                "createdAt": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(collection.aggregate(pipeline))
```

#### Java (MongoTemplate)

```java
// platform-core/src/main/java/com/agentplatform/service/VectorSearchService.java

public List<VectorSearchResult> findSimilarContextSnapshots(
        List<Double> queryVector, String productId, int topK) {

    Document vectorSearchStage = new Document("$vectorSearch", new Document()
        .append("index", "vector_embedding_index")
        .append("path", "embedding")
        .append("queryVector", queryVector)
        .append("numCandidates", topK * 20)
        .append("limit", topK)
        .append("filter", new Document()
            .append("productId", new Document("$eq", productId))
            .append("sourceType", new Document("$eq", "context_snapshot"))
        )
    );

    Document projectStage = new Document("$project", new Document()
        .append("_id", 0)
        .append("sourceId", 1)
        .append("textChunk", 1)
        .append("stage", 1)
        .append("createdAt", 1)
        .append("score", new Document("$meta", "vectorSearchScore"))
    );

    List<Document> pipeline = List.of(vectorSearchStage, projectStage);

    return mongoTemplate
        .getCollection("vector_embeddings")
        .aggregate(pipeline, Document.class)
        .into(new ArrayList<>())
        .stream()
        .map(VectorSearchResult::fromDocument)
        .collect(Collectors.toList());
}
```

---

### 5.2 Find Similar User Stories from Past Runs

**Use case:** Requirements Crew deduplication — surface user stories from past requirements stages that are semantically close to the story being drafted.

#### MongoDB Aggregation Pipeline (JSON)

```json
[
  {
    "$vectorSearch": {
      "index": "vector_embedding_index",
      "path": "embedding",
      "queryVector": "<1536-float array of the draft user story text>",
      "numCandidates": 150,
      "limit": 10,
      "filter": {
        "stage": { "$eq": "requirements" },
        "sourceType": { "$eq": "sdlc_artifact" }
      }
    }
  },
  {
    "$project": {
      "_id": 0,
      "sourceId": 1,
      "productId": 1,
      "textChunk": 1,
      "createdAt": 1,
      "score": { "$meta": "vectorSearchScore" }
    }
  }
]
```

#### Python (PyMongo)

```python
def find_similar_user_stories(
    query_embedding: list[float],
    top_k: int = 10,
    similarity_threshold: float = 0.88,
) -> list[dict]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_embedding_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": top_k * 15,
                "limit": top_k,
                "filter": {
                    "stage": {"$eq": "requirements"},
                    "sourceType": {"$eq": "sdlc_artifact"},
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "sourceId": 1,
                "productId": 1,
                "textChunk": 1,
                "createdAt": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    results = list(collection.aggregate(pipeline))
    # Post-filter by threshold — only flag likely duplicates
    return [r for r in results if r["score"] >= similarity_threshold]
```

---

### 5.3 Find Reusable React Components from Past Dev Runs

**Use case:** Dev Crew code reuse — locate frontend artifacts generated in prior dev stages across all products.

#### MongoDB Aggregation Pipeline (JSON)

```json
[
  {
    "$vectorSearch": {
      "index": "vector_embedding_index",
      "path": "embedding",
      "queryVector": "<1536-float array of the component description or requirements text>",
      "numCandidates": 200,
      "limit": 5,
      "filter": {
        "sourceType": { "$eq": "sdlc_artifact" },
        "stage": { "$eq": "dev" }
      }
    }
  },
  {
    "$project": {
      "_id": 0,
      "sourceId": 1,
      "productId": 1,
      "textChunk": 1,
      "createdAt": 1,
      "score": { "$meta": "vectorSearchScore" }
    }
  }
]
```

#### Python (PyMongo)

```python
def find_reusable_dev_artifacts(
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_embedding_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": top_k * 40,
                "limit": top_k,
                "filter": {
                    "sourceType": {"$eq": "sdlc_artifact"},
                    "stage": {"$eq": "dev"},
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "sourceId": 1,
                "productId": 1,
                "textChunk": 1,
                "createdAt": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(collection.aggregate(pipeline))
```

#### Java (MongoTemplate)

```java
public List<VectorSearchResult> findReusableDevArtifacts(
        List<Double> queryVector, int topK) {

    Document vectorSearchStage = new Document("$vectorSearch", new Document()
        .append("index", "vector_embedding_index")
        .append("path", "embedding")
        .append("queryVector", queryVector)
        .append("numCandidates", topK * 40)
        .append("limit", topK)
        .append("filter", new Document()
            .append("sourceType", new Document("$eq", "sdlc_artifact"))
            .append("stage", new Document("$eq", "dev"))
        )
    );

    Document projectStage = new Document("$project", new Document()
        .append("_id", 0)
        .append("sourceId", 1)
        .append("productId", 1)
        .append("textChunk", 1)
        .append("createdAt", 1)
        .append("score", new Document("$meta", "vectorSearchScore"))
    );

    return mongoTemplate
        .getCollection("vector_embeddings")
        .aggregate(List.of(vectorSearchStage, projectStage), Document.class)
        .into(new ArrayList<>())
        .stream()
        .map(VectorSearchResult::fromDocument)
        .collect(Collectors.toList());
}
```

> **numCandidates guidance:** Set `numCandidates` to at least `10 × limit` for high-recall queries. For cross-product searches with no `productId` filter, increase to `40 × limit` because the candidate pool spans more documents. ANN recall degrades if `numCandidates` is too small relative to `limit`.

---

## 6. Integration with Platform-Core Context Enrichment (ADR-004)

ADR-004 mandates that every agent run receive an **enriched context payload** — the raw Jira/SAP/Figma data plus a `similarPastRuns` array so crews do not need to call external APIs mid-run. The vector search layer is what makes the `similarPastRuns` section possible without unbounded latency.

### 6.1 End-to-End Flow

```
Client (UI / API)
    │
    ▼
platform-core: AgentRunService.startRun(runRequest)
    │
    ├─ 1. Fetch context snapshot
    │       ├─ Jira: open epics + defects for productId
    │       ├─ SAP CRM: customer segments + account data
    │       └─ Figma: latest design version metadata
    │
    ├─ 2. Serialize snapshot to text (snapshotText)
    │
    ├─ 3. Call EmbeddingClient.embed(snapshotText)
    │       └─ POST https://api.openai.com/v1/embeddings
    │           body: { model: "text-embedding-3-small", input: snapshotText }
    │           → returns float[1536]
    │
    ├─ 4. Store in vector_embeddings
    │       sourceType=context_snapshot, stage=pre-run, productId=...
    │
    ├─ 5. Query vector_embeddings for top-3 similar past runs
    │       $vectorSearch filter: productId + sourceType=context_snapshot
    │       → returns [ { sourceId, textChunk, score }, ... ]
    │
    ├─ 6. Fetch full run summaries for matched sourceIds
    │       from agent_runs collection (audit_summaries subdoc)
    │
    └─ 7. Assemble enriched context payload
            {
              "runId": "...",
              "productId": "SelfCare-001",
              "contextSnapshot": { jira: {...}, sap: {...}, figma: {...} },
              "similarPastRuns": [
                { "runId": "run-20250301-...", "summary": "...", "similarity": 0.94 },
                { "runId": "run-20250215-...", "summary": "...", "similarity": 0.91 },
                { "runId": "run-20250110-...", "summary": "...", "similarity": 0.87 }
              ]
            }
            │
            └─ POST to agent-engine /runs  (forwarded to CrewAI orchestrator)
```

### 6.2 Java Implementation Sketch

```java
// AgentRunService.java — enrichContext() method (simplified)

public EnrichedContext enrichContext(AgentRunRequest request) {
    // Steps 1–2: fetch and serialize
    ContextSnapshot snapshot = contextFetchService.fetch(request.getProductId());
    String snapshotText = snapshotSerializer.toText(snapshot);

    // Step 3: embed
    List<Double> embedding = embeddingClient.embed(snapshotText);

    // Step 4: persist
    embedAndStoreContextSnapshot(currentRun, snapshotText, embedding);

    // Steps 5–6: query and resolve summaries
    List<VectorSearchResult> similar = vectorSearchService
        .findSimilarContextSnapshots(embedding, request.getProductId(), 3);

    List<PastRunSummary> pastRunSummaries = similar.stream()
        .map(r -> agentRunRepository.findSummaryByRunId(r.getSourceId())
            .map(s -> new PastRunSummary(r.getSourceId(), s, r.getScore()))
            .orElse(null))
        .filter(Objects::nonNull)
        .collect(Collectors.toList());

    // Step 7: build payload
    return EnrichedContext.builder()
        .runId(currentRun.getRunId())
        .productId(request.getProductId())
        .contextSnapshot(snapshot)
        .similarPastRuns(pastRunSummaries)
        .build();
}
```

### 6.3 Why This Pattern Satisfies ADR-004

- **Single external call budget per run**: Jira, SAP, Figma, and the embedding API are called exactly once in platform-core, not once per crew. Crews receive everything they need in the initial payload.
- **Temporal relevance**: Cosine similarity over `context_snapshot` embeddings naturally surfaces runs with similar product state (same open epics, similar design version). Pure metadata filtering (date range, product ID) would miss semantically equivalent runs that happened under a different sprint cycle.
- **Graceful degradation**: If the embedding API is unavailable, platform-core continues the run with `similarPastRuns: []`. The crews lose enrichment but the run does not fail.

---

## 7. Cost and Performance Notes

### 7.1 Atlas Cluster Sizing

| Tier | Approximate $vectorSearch latency (p50) | Recommended for |
|---|---|---|
| M10 | 300–600 ms | Development / low traffic |
| M30 | 80–120 ms | Production — tens of concurrent runs |
| M50 | 40–70 ms | Production — hundreds of concurrent runs |

At the expected scale of the platform (tens of concurrent SDLC runs), an **Atlas M30** delivers sub-120 ms vector search queries (p50), which is acceptable given that the embedding + vector search step is done once per run in platform-core, not in the critical path of each crew task.

The `numCandidates` setting directly affects both recall and latency. Higher values improve recall but increase scan time. The values in the query patterns above (`20×`, `15×`, `40× limit`) are starting points — tune based on observed recall metrics in staging.

### 7.2 Embedding API Cost

| Model | Dimensions | Price (per 1M tokens) | Approx. cost per run |
|---|---|---|---|
| `text-embedding-3-small` | 1536 | $0.02 | ~$0.0001 |
| `text-embedding-3-large` | 3072 | $0.13 | ~$0.0007 |
| `text-embedding-ada-002` | 1536 | $0.10 | ~$0.0005 |

`text-embedding-3-small` at 1536 dimensions offers the best cost-to-quality ratio for this use case. A typical context snapshot (Jira epics + SAP summary + Figma metadata) is roughly 500–800 tokens, putting per-run embedding cost at approximately **$0.0001**. At 1,000 runs/month this is $0.10 — effectively negligible.

### 7.3 Storage Estimate

Each `vector_embeddings` document is approximately **12 KB** (1536 floats × 4 bytes + metadata overhead). At 5 embedding documents per run (1 context snapshot + ~4 artifacts) and 1,000 runs/month, monthly growth is approximately **60 MB** — well within Atlas free-tier storage, let alone M30.

### 7.4 Index Build Time

Initial index build on an empty collection completes in seconds. On a collection with 100,000 documents (roughly 20,000 runs worth of history) expect 2–5 minutes on M30. The collection remains queryable via standard `find` during index build; vector search queries against that index will return an error until the index status is `READY`.

### 7.5 Operational Recommendations

- **Re-embedding policy**: If the embedding model changes (e.g., migrating from `ada-002` to `text-embedding-3-small`), existing vectors must be regenerated. Track the `model` field and filter queries to only compare vectors from the same model family.
- **numCandidates in production**: Start at `20 × limit` and increase if recall (measured by human spot-checks or A/B testing) is insufficient. Atlas does not expose ANN recall metrics directly — instrument the application layer.
- **Index warm-up**: After a cluster failover or Atlas maintenance window, the first few vector search queries may be slower (cold ANN graph). No action is needed; the index warms itself within 1–2 minutes of traffic.
- **TTL for old embeddings**: Consider expiring `context_snapshot` embeddings older than 18 months to control storage growth. The TTL index example in section 2.3 can be adapted for this purpose.
