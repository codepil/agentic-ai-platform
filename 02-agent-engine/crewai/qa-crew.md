# QA Crew

Parent blueprint: [blueprint.md](../../blueprint.md)

---

## Purpose

The QA Crew validates all code artefacts produced by the Dev Crew. It executes unit, integration, and E2E test suites, runs SAST and SCA security scans, produces code review findings, and makes a binary quality gate decision (`passed: True/False`). The output is a `QAResults` TypedDict that drives the LangGraph retry / escalation logic.

---

## Process Type

**`Process.sequential`**

Tasks execute in order: Test Automation Engineer → Security Analyst → QA Lead. Security scan is informed by test results; QA Lead synthesises both to make the final quality gate decision.

---

## Agent Roster

### 1. Test Automation Engineer

| Field | Value |
|-------|-------|
| Role | Test Automation Engineer |
| Goal | Execute the full test suite and produce a detailed quality report with pass/fail counts and coverage metrics |
| Tools | `Add Jira Comment` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a QA Engineering Lead who has built CI-integrated test pipelines at scale. You orchestrate test execution across unit, integration, and E2E layers and produce actionable quality reports for development teams.

---

### 2. Security Analyst

| Field | Value |
|-------|-------|
| Role | Security Analyst |
| Goal | Run SAST, SCA, and supply chain security scans and identify all vulnerabilities above informational severity |
| Tools | `Add Jira Comment` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are an Application Security Engineer specialised in OWASP Top 10, SAST, SCA, and supply chain security. You use Snyk, Checkmarx, and custom SAST rules to catch security issues before they reach production.

---

### 3. QA Lead

| Field | Value |
|-------|-------|
| Role | QA Lead |
| Goal | Synthesise test and security results into a clear quality gate decision and create Jira issues for all failures |
| Tools | `Create Jira Subtask`, `Add Jira Comment` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a QA Engineering Lead who has built CI-integrated test pipelines at scale. You orchestrate test execution across unit, integration, and E2E layers and produce actionable quality reports for development teams.

---

## Task Definitions

### `test_task`

| Field | Value |
|-------|-------|
| Agent | Test Automation Engineer |
| Context dependencies | `[]` (first task) |
| Description | Execute unit, integration, and E2E test suites on the code artefacts. Report total/passed/failed/skipped/coverage for units; total/passed/failed/duration for integration; total/passed/failed/browser/duration for E2E. Add Jira comments on failed test issues. |
| Expected output | JSON: `{unit_test_results, integration_test_results, e2e_test_results}` |

---

### `sec_task`

| Field | Value |
|-------|-------|
| Agent | Security Analyst |
| Context dependencies | `[test_task]` |
| Description | Run SAST and SCA scans on all code artefacts. Report vulnerabilities by severity. Create Jira subtasks for critical/high vulnerabilities. |
| Expected output | JSON: `{security_scan_results: {vulnerabilities_critical, vulnerabilities_high, vulnerabilities_medium, vulnerabilities_low, scanner}}` |

---

### `summary_task`

| Field | Value |
|-------|-------|
| Agent | QA Lead |
| Context dependencies | `[test_task, sec_task]` |
| Description | Determine quality gate: `passed=True` only if unit coverage ≥ 80%, zero critical CVEs, zero E2E failures. Compile `code_review_findings`. Write `failure_summary` if failed. |
| Expected output | JSON: `{passed, code_review_findings, failure_summary}` |

---

## Quality Gate Rules

`passed = True` requires ALL of:
1. Unit test coverage ≥ 80%
2. Zero critical security vulnerabilities
3. Zero E2E test failures

---

## Crew Configuration

| Parameter | Value |
|-----------|-------|
| `process` | `Process.sequential` |
| `verbose` | `True` |
| `memory` | `True` |
| `max_rpm` | `10` |

---

## Output Mapping — `QAResults` TypedDict

| Crew output key | TypedDict field | Type |
|-----------------|-----------------|------|
| `passed` | `qa_results.passed` | `bool` |
| `unit_test_results` | `qa_results.unit_test_results` | `Dict` |
| `integration_test_results` | `qa_results.integration_test_results` | `Dict` |
| `security_scan_results` | `qa_results.security_scan_results` | `Dict` |
| `code_review_findings` | `qa_results.code_review_findings` | `List[str]` |
| `e2e_test_results` | `qa_results.e2e_test_results` | `Dict` |
| `failure_summary` | `qa_results.failure_summary` | `Optional[str]` |

Validated by `QACrewOutput` Pydantic model in `output_models.py`.

---

## Pydantic Output Models

```python
class QACrewOutput(BaseModel):
    passed: bool
    unit_test_results: Dict[str, Any]
    integration_test_results: Dict[str, Any]
    security_scan_results: Dict[str, Any]
    code_review_findings: List[str]
    e2e_test_results: Dict[str, Any]
    failure_summary: Optional[str] = None
```

Uses `model_config = ConfigDict(extra='allow')`.

---

## Mock vs Real Mode

| Mode | Behaviour |
|------|-----------|
| `MOCK_MODE=true` | Returns `_MOCK_PASS` by default (142 unit tests all passing, 87.4% coverage, 0 critical CVEs). Pass `{"force_fail": True}` in inputs to get `_MOCK_FAIL` (24 unit failures, 1 critical CVE, 3 E2E failures). No CrewAI imports. |
| `MOCK_MODE=false` | Real sequential CrewAI crew. LLMs: `get_llm("summarise_qa")` (Haiku) for QA Lead and Test Automation, `get_llm("security_scan")` (Sonnet) for Security Analyst. Jira tools create issues for failures. |

### Retry Integration

When `passed=False`, the LangGraph `route_after_qa` function:
- Returns `"qa_retry"` if `qa_iteration < max_qa_iterations`
- Returns `"error"` if iterations exhausted

The `qa_failed_handler_node` formats `failure_summary` and `code_review_findings` into `human_feedback` that the Dev Crew uses on retry.

---

## File Locations

| File | Path |
|------|------|
| Crew implementation | `agent-engine/src/platform/crews/qa_crew.py` |
| Output model | `agent-engine/src/platform/crews/output_models.py` |
| CrewAI tools | `agent-engine/src/platform/tools/crewai_tools.py` |
| Jira client | `agent-engine/src/platform/tools/jira_tools.py` |
| Tests | `agent-engine/tests/test_crews.py::TestQACrew` |
