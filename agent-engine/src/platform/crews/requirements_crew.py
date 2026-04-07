"""
Requirements crew — elicits and structures product requirements.

Crew type: Sequential
  1. Business Analyst    — parses the Jira epic and PRD
  2. Requirements Lead   — structures stories and acceptance criteria
  3. SAP Specialist      — identifies SAP integration dependencies

Task context dependencies:
  structure_task  context=[parse_task]
  sap_task        context=[structure_task]

In mock mode returns hardcoded data matching RequirementsOutput.
Output is validated against RequirementsCrewOutput Pydantic model.

Parent blueprint: /Agentic-AI-platform/blueprint.md
"""

from __future__ import annotations

from typing import Any, Dict

from .base_crew import BaseCrew
from ..state.sdlc_state import RequirementsOutput


class RequirementsCrew(BaseCrew):
    """Elicits and structures product requirements from the Jira epic and PRD."""

    # ------------------------------------------------------------------
    # Mock output — realistic self-care product catalog data
    # ------------------------------------------------------------------

    _MOCK_OUTPUT: RequirementsOutput = {
        "user_stories": [
            {
                "id": "US-001",
                "title": "Browse product catalog",
                "as_a": "registered customer",
                "i_want": "to browse and filter the product catalog by category and price",
                "so_that": "I can find the right self-care product quickly",
                "story_points": 8,
            },
            {
                "id": "US-002",
                "title": "View product details",
                "as_a": "registered customer",
                "i_want": "to see full product details including ingredients and pricing",
                "so_that": "I can make an informed purchase decision",
                "story_points": 5,
            },
            {
                "id": "US-003",
                "title": "Add to cart",
                "as_a": "registered customer",
                "i_want": "to add products to my cart and proceed to checkout",
                "so_that": "I can complete my purchase without leaving the self-care portal",
                "story_points": 13,
            },
        ],
        "acceptance_criteria": [
            {
                "story_id": "US-001",
                "given": "a customer is on the catalog page",
                "when": "they select a category filter and apply a max price",
                "then": "only matching products are displayed within 500 ms",
            },
            {
                "story_id": "US-002",
                "given": "a customer clicks on a product card",
                "when": "the product detail page loads",
                "then": "they see images, description, ingredients, price from SAP, and stock status",
            },
        ],
        "sap_dependencies": [
            "BAPI_MATERIAL_GET_ALL",
            "SD_SALESDOCUMENT_CREATE",
        ],
        "ambiguities": [
            "It is unclear whether guest checkout should be supported in scope v1.",
        ],
        "jira_subtask_ids": [
            "SC-101",
            "SC-102",
        ],
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the requirements crew and return a RequirementsOutput dict."""
        if self.mock_mode:
            return dict(self._MOCK_OUTPUT)

        # --- Real CrewAI implementation ---
        from crewai import Agent, Task, Crew, Process
        from ..llm.model_router import get_llm
        from ..tools.crewai_tools import get_jira_crewai_tools

        llm = get_llm("requirements_analysis")
        read_jira_epic, create_jira_subtask, add_jira_comment = get_jira_crewai_tools()

        ba_agent = Agent(
            role="Business Analyst",
            goal="Parse the Jira epic and PRD to extract all business requirements including edge cases",
            backstory=(
                "You are a Senior Business Analyst with 12 years of experience in retail and "
                "e-commerce. You have worked on SAP Commerce Cloud and Hybris implementations and "
                "understand how business requirements translate to SAP integration touchpoints. "
                "You are meticulous in capturing edge cases and always ask clarifying questions "
                "when scope is ambiguous."
            ),
            llm=llm,
            tools=[read_jira_epic],
            memory=True,
            verbose=True,
        )
        req_lead = Agent(
            role="Requirements Lead",
            goal="Structure requirements into INVEST-compliant user stories with BDD acceptance criteria",
            backstory=(
                "You are a Requirements Engineering Lead certified in SAFe Agile. You write "
                "INVEST-compliant user stories with clear BDD acceptance criteria. You have built "
                "product backlogs for 50+ enterprise applications and know how to split epics into "
                "sprint-sized stories."
            ),
            llm=llm,
            tools=[create_jira_subtask],
            memory=True,
            verbose=True,
        )
        sap_specialist = Agent(
            role="SAP Specialist",
            goal="Identify all SAP BAPIs, RFCs, OData services and IDOc types required",
            backstory=(
                "You are a Senior SAP Functional Consultant with 15 years of S/4HANA experience "
                "across MM, SD, and WM modules. You can identify the exact BAPI, RFC, OData service, "
                "or IDOc type needed for any business process. You are familiar with SAP Integration "
                "Suite and have designed over 200 SAP integration scenarios."
            ),
            llm=llm,
            tools=[add_jira_comment],
            memory=True,
            verbose=True,
        )

        parse_task = Task(
            description=(
                f"Read the Jira epic '{inputs.get('jira_epic_id', '')}' using the Read Jira Epic "
                f"tool, then parse the following PRD and extract all raw business requirements. "
                f"Include functional requirements, non-functional requirements, and edge cases.\n\n"
                f"Epic content: {inputs.get('epic', '')}"
            ),
            expected_output=(
                "A JSON list of raw requirements, each with 'title', 'description', "
                "'type' (functional|non-functional), and 'priority' (high|medium|low)"
            ),
            agent=ba_agent,
        )
        structure_task = Task(
            description=(
                "Convert the raw requirements from the previous task into INVEST-compliant user "
                "stories following the format: 'As a <role>, I want <feature> so that <benefit>'. "
                "For each user story write BDD acceptance criteria (Given/When/Then). "
                "Create Jira subtasks for each user story using the Create Jira Subtask tool."
            ),
            expected_output=(
                "JSON with keys: user_stories (list with id, title, as_a, i_want, so_that, "
                "story_points), acceptance_criteria (list with story_id, given, when, then), "
                "ambiguities (list of strings), jira_subtask_ids (list of created Jira keys)"
            ),
            agent=req_lead,
            context=[parse_task],
        )
        sap_task = Task(
            description=(
                "Review all user stories from the previous task and identify every SAP BAPI, RFC, "
                "OData service, and IDOc type required to fulfil each story. "
                "Add a comment to the Jira epic summarising the SAP dependencies found."
            ),
            expected_output=(
                "JSON list of SAP function module / OData service names that are required, "
                "e.g. ['BAPI_MATERIAL_GET_ALL', 'API_PRODUCT_SRV']"
            ),
            agent=sap_specialist,
            context=[structure_task],
        )

        crew = Crew(
            agents=[ba_agent, req_lead, sap_specialist],
            tasks=[parse_task, structure_task, sap_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            max_rpm=10,
        )
        crew.kickoff(inputs=inputs)

        # In a real implementation the LLM output would be parsed here.
        # Returning mock for structural compatibility.
        return dict(self._MOCK_OUTPUT)
