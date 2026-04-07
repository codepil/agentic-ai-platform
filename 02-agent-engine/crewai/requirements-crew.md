# Requirements Crew

Parent blueprint: [blueprint.md](../../blueprint.md)

---

## Purpose

The Requirements Crew elicits, structures, and validates product requirements from a Jira epic and PRD. It produces INVEST-compliant user stories, BDD acceptance criteria, identified SAP integration touchpoints, and a list of open ambiguities — all as a `RequirementsOutput` TypedDict that flows into the LangGraph SDLC state.

---

## Process Type

**`Process.sequential`**

Tasks execute in order: Business Analyst → Requirements Lead → SAP Specialist. Each agent's output is the context for the next.

---

## Agent Roster

### 1. Business Analyst

| Field | Value |
|-------|-------|
| Role | Business Analyst |
| Goal | Parse the Jira epic and PRD to extract all business requirements including edge cases |
| Tools | `Read Jira Epic` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Senior Business Analyst with 12 years of experience in retail and e-commerce. You have worked on SAP Commerce Cloud and Hybris implementations and understand how business requirements translate to SAP integration touchpoints. You are meticulous in capturing edge cases and always ask clarifying questions when scope is ambiguous.

---

### 2. Requirements Lead

| Field | Value |
|-------|-------|
| Role | Requirements Lead |
| Goal | Structure requirements into INVEST-compliant user stories with BDD acceptance criteria |
| Tools | `Create Jira Subtask` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Requirements Engineering Lead certified in SAFe Agile. You write INVEST-compliant user stories with clear BDD acceptance criteria. You have built product backlogs for 50+ enterprise applications and know how to split epics into sprint-sized stories.

---

### 3. SAP Specialist

| Field | Value |
|-------|-------|
| Role | SAP Specialist |
| Goal | Identify all SAP BAPIs, RFCs, OData services and IDOc types required |
| Tools | `Add Jira Comment` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Senior SAP Functional Consultant with 15 years of S/4HANA experience across MM, SD, and WM modules. You can identify the exact BAPI, RFC, OData service, or IDOc type needed for any business process. You are familiar with SAP Integration Suite and have designed over 200 SAP integration scenarios.

---

## Task Definitions

### `parse_task`

| Field | Value |
|-------|-------|
| Agent | Business Analyst |
| Context dependencies | — (first task) |
| Description | Read the Jira epic via `Read Jira Epic` tool, then parse the PRD. Extract functional requirements, non-functional requirements, and edge cases. |
| Expected output | JSON list of raw requirements: `{title, description, type, priority}` |

---

### `structure_task`

| Field | Value |
|-------|-------|
| Agent | Requirements Lead |
| Context dependencies | `[parse_task]` |
| Description | Convert raw requirements into user stories (`As a <role>, I want <feature> so that <benefit>`). Write Given/When/Then acceptance criteria. Create Jira subtasks via `Create Jira Subtask`. |
| Expected output | JSON: `{user_stories, acceptance_criteria, ambiguities, jira_subtask_ids}` |

---

### `sap_task`

| Field | Value |
|-------|-------|
| Agent | SAP Specialist |
| Context dependencies | `[structure_task]` |
| Description | Review all user stories and identify every SAP BAPI, RFC, OData service, and IDOc type required. Add a Jira comment summarising SAP dependencies. |
| Expected output | JSON list of SAP function module / OData service names |

---

## Crew Configuration

| Parameter | Value |
|-----------|-------|
| `process` | `Process.sequential` |
| `verbose` | `True` |
| `memory` | `True` |
| `max_rpm` | `10` |

---

## Output Mapping — `RequirementsOutput` TypedDict

| Crew output key | TypedDict field | Type |
|-----------------|-----------------|------|
| `user_stories` | `requirements.user_stories` | `List[Dict]` |
| `acceptance_criteria` | `requirements.acceptance_criteria` | `List[Dict]` |
| `sap_dependencies` | `requirements.sap_dependencies` | `List[str]` |
| `ambiguities` | `requirements.ambiguities` | `List[str]` |
| `jira_subtask_ids` | `requirements.jira_subtask_ids` | `List[str]` |

The crew output is also validated by `RequirementsCrewOutput` Pydantic model in `output_models.py`.

---

## Pydantic Output Models

```python
class UserStory(BaseModel):
    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    story_points: int

class AcceptanceCriteria(BaseModel):
    story_id: str
    given: str
    when: str
    then: str

class RequirementsCrewOutput(BaseModel):
    user_stories: List[UserStory]
    acceptance_criteria: List[AcceptanceCriteria]
    sap_dependencies: List[str]
    ambiguities: List[str]
    jira_subtask_ids: List[str]
```

All models use `model_config = ConfigDict(extra='allow')`.

---

## Mock vs Real Mode

| Mode | Behaviour |
|------|-----------|
| `MOCK_MODE=true` | Returns `_MOCK_OUTPUT` — hardcoded `RequirementsOutput` dict with 3 user stories, 2 acceptance criteria, 2 SAP BAPIs, 1 ambiguity, 2 Jira IDs. No CrewAI imports occur. |
| `MOCK_MODE=false` | Real CrewAI `Agent`/`Task`/`Crew` objects are instantiated. LLM is obtained from `get_llm("requirements_analysis")` (Sonnet). Tools call real Jira APIs. LLM output is parsed into the `RequirementsOutput` shape. |

The `if self.mock_mode:` guard in `kickoff()` ensures CrewAI is never imported during test runs.

---

## File Locations

| File | Path |
|------|------|
| Crew implementation | `agent-engine/src/platform/crews/requirements_crew.py` |
| Output model | `agent-engine/src/platform/crews/output_models.py` |
| CrewAI tools | `agent-engine/src/platform/tools/crewai_tools.py` |
| Jira client | `agent-engine/src/platform/tools/jira_tools.py` |
| Tests | `agent-engine/tests/test_crews.py::TestRequirementsCrew` |
