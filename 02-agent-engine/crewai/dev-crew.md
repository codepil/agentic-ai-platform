# Dev Crew

Parent blueprint: [blueprint.md](../../blueprint.md)

---

## Purpose

The Dev Crew implements all code artefacts for the current sprint — Spring Boot 3 microservices, React 18 TypeScript components, and test suites. It produces a list of `CodeArtifact` objects each carrying a git branch, commit SHA, and content hash, which flows into the LangGraph SDLC state.

---

## Process Type

**`Process.hierarchical`**

The Tech Lead is the **manager agent** who delegates to the Java Developer and React Developer, then reviews all output before accepting it. This mirrors a real engineering team where a staff engineer oversees implementation.

---

## Agent Roster

### 1. Tech Lead (Manager Agent)

| Field | Value |
|-------|-------|
| Role | Tech Lead |
| Goal | Ensure code quality, architecture adherence, SOLID principles, and security best practices. Delegate tasks and review all output. |
| Tools | `Create GitHub Branch`, `Create GitHub PR` |
| Memory | `True` |
| `allow_delegation` | `True` |

**Backstory (full prompt text)**

> You are a Staff Engineer and Tech Lead with 12 years in Spring Boot microservices and React frontends. You enforce clean architecture, SOLID principles, and security best practices in every PR. You are the manager agent who delegates implementation tasks and reviews all output.

---

### 2. Java Developer

| Field | Value |
|-------|-------|
| Role | Senior Java Developer |
| Goal | Implement production-ready Spring Boot 3 REST controllers, services, and SAP JCo integration with proper exception handling and test coverage |
| Tools | `Commit File to GitHub` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Senior Java Developer specialising in Spring Boot 3, Spring Security, and SAP JCo integration. You write production-ready code with proper exception handling, logging, and Testcontainers-based integration tests. Your code follows hexagonal architecture and is fully covered by unit tests.

---

### 3. React Developer

| Field | Value |
|-------|-------|
| Role | Senior React Developer |
| Goal | Build accessible WCAG 2.1 AA React 18 TypeScript components from Figma designs with comprehensive Jest and Playwright tests |
| Tools | `Read Figma File`, `List Figma Components`, `Commit File to GitHub` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Senior Frontend Engineer specialising in React 18, TypeScript, and Webpack Module Federation. You build accessible (WCAG 2.1 AA) components from Figma designs and write comprehensive Jest and Playwright tests.

---

## Task Definitions

### `java_task`

| Field | Value |
|-------|-------|
| Agent | Senior Java Developer |
| Context dependencies | `[]` (runs independently) |
| Description | Create a feature branch. Implement `ProductController.java` (REST controller), `ProductService.java` (business logic with SAP JCo), `ProductRepository.java` (MongoDB). Commit all files to GitHub. |
| Expected output | JSON list of committed Java source file objects with `artifact_id`, `type="java_service"`, `repo`, `file_path`, `git_branch`, `git_commit_sha`, `content_hash` |

---

### `react_task`

| Field | Value |
|-------|-------|
| Agent | Senior React Developer |
| Context dependencies | `[]` (runs independently) |
| Description | Use `List Figma Components` to discover design components. Implement `ProductCard.tsx`, `FilterSidebar.tsx`, `ProductCard.test.tsx`, and `ProductCard.spec.ts`. Commit all files to GitHub. |
| Expected output | JSON list of committed React/TypeScript file objects with `artifact_id`, `type="react_component"`, `repo`, `file_path`, `git_branch`, `git_commit_sha`, `content_hash` |

---

### `review_task`

| Field | Value |
|-------|-------|
| Agent | Tech Lead |
| Context dependencies | `[java_task, react_task]` |
| Description | Review all produced code for: OWASP Top 10 security, N+1 query patterns, SOLID principles, naming conventions, minimum 80% test coverage. Create a GitHub PR for each feature branch. |
| Expected output | JSON code review report with pass/fail per file and list of PR URLs created |

---

## Crew Configuration

| Parameter | Value |
|-----------|-------|
| `process` | `Process.hierarchical` |
| `manager_agent` | Tech Lead |
| `verbose` | `True` |
| `memory` | `True` |
| `max_rpm` | `10` |

---

## Output Mapping — `DevCrewOutput` TypedDict

The crew returns `{"code_artifacts": List[CodeArtifact]}` which is merged into `SDLCState.code_artifacts`.

| Crew output key | TypedDict field | Type |
|-----------------|-----------------|------|
| `code_artifacts[].artifact_id` | `CodeArtifact.artifact_id` | `str` |
| `code_artifacts[].type` | `CodeArtifact.type` | `str` (`java_service`, `react_component`, `test_suite`) |
| `code_artifacts[].repo` | `CodeArtifact.repo` | `str` |
| `code_artifacts[].file_path` | `CodeArtifact.file_path` | `str` |
| `code_artifacts[].git_branch` | `CodeArtifact.git_branch` | `str` |
| `code_artifacts[].git_commit_sha` | `CodeArtifact.git_commit_sha` | `str` |
| `code_artifacts[].content_hash` | `CodeArtifact.content_hash` | `str` |

Validated by `DevCrewOutput` Pydantic model in `output_models.py`.

---

## Pydantic Output Models

```python
class CodeArtifactModel(BaseModel):
    artifact_id: str
    type: str
    repo: str
    file_path: str
    git_branch: str
    git_commit_sha: str
    content_hash: str

class DevCrewOutput(BaseModel):
    code_artifacts: List[CodeArtifactModel]
```

All models use `model_config = ConfigDict(extra='allow')`.

---

## Mock vs Real Mode

| Mode | Behaviour |
|------|-----------|
| `MOCK_MODE=true` | Returns `{"code_artifacts": [...]}` — 3 hardcoded artefacts: `artifact-001` (java_service), `artifact-002` (react_component), `artifact-003` (test_suite) with fake git SHAs. No CrewAI imports. |
| `MOCK_MODE=false` | Real hierarchical CrewAI crew. LLM from `get_llm("write_code")` (Sonnet). GitHub and Figma tools used. Tech Lead delegates java and react tasks then reviews. |

---

## File Locations

| File | Path |
|------|------|
| Crew implementation | `agent-engine/src/platform/crews/dev_crew.py` |
| Output model | `agent-engine/src/platform/crews/output_models.py` |
| CrewAI tools | `agent-engine/src/platform/tools/crewai_tools.py` |
| GitHub client | `agent-engine/src/platform/tools/github_tools.py` |
| Figma client | `agent-engine/src/platform/tools/figma_tools.py` |
| Tests | `agent-engine/tests/test_crews.py::TestDevCrew` |
