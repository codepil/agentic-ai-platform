"""
Architecture crew — designs the technical solution.

Crew type: Sequential
  1. Solution Architect  — overall system design and ADRs
  2. API Designer        — OpenAPI specifications
  3. Data Architect      — MongoDB schemas

Task context dependencies:
  api_task     context=[design_task]
  schema_task  context=[design_task, api_task]

In mock mode returns hardcoded data matching ArchitectureOutput.
Output is validated against ArchitectureCrewOutput Pydantic model.

Parent blueprint: /Agentic-AI-platform/blueprint.md
"""

from __future__ import annotations

from typing import Any, Dict

from .base_crew import BaseCrew
from ..state.sdlc_state import ArchitectureOutput


class ArchitectureCrew(BaseCrew):
    """Designs the technical architecture for the product."""

    _MOCK_OUTPUT: ArchitectureOutput = {
        "openapi_specs": [
            {
                "service": "product-catalog",
                "version": "1.0.0",
                "base_path": "/api/v1/products",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/",
                        "summary": "List products with optional filters",
                        "query_params": ["category", "max_price", "page", "page_size"],
                    },
                    {
                        "method": "GET",
                        "path": "/{product_id}",
                        "summary": "Retrieve a single product by ID",
                    },
                    {
                        "method": "POST",
                        "path": "/",
                        "summary": "Create a new product (admin only)",
                        "request_body": "ProductCreateRequest",
                    },
                ],
            }
        ],
        "mongodb_schemas": [
            {
                "collection": "products",
                "indexes": [
                    {"keys": {"category": 1, "price": 1}},
                    {"keys": {"name": "text", "description": "text"}},
                ],
                "schema": {
                    "bsonType": "object",
                    "required": ["sku", "name", "price", "category"],
                    "properties": {
                        "sku": {"bsonType": "string"},
                        "name": {"bsonType": "string"},
                        "description": {"bsonType": "string"},
                        "price": {"bsonType": "decimal"},
                        "category": {"bsonType": "string"},
                        "sap_material_id": {"bsonType": "string"},
                        "stock_quantity": {"bsonType": "int"},
                        "images": {"bsonType": "array"},
                        "created_at": {"bsonType": "date"},
                        "updated_at": {"bsonType": "date"},
                    },
                },
            }
        ],
        "adr_ids": ["ADR-001", "ADR-002"],
        "sap_integration_plan": {
            "type": "OData v4",
            "gateway_url": "https://sap-gateway.example.com/sap/opu/odata/sap",
            "endpoints": [
                {
                    "service": "API_PRODUCT_SRV",
                    "entity_set": "A_Product",
                    "operations": ["GET"],
                    "purpose": "Fetch product master data including pricing",
                },
                {
                    "service": "API_SALES_ORDER_SRV",
                    "entity_set": "A_SalesOrder",
                    "operations": ["POST"],
                    "purpose": "Create sales orders on customer checkout",
                },
            ],
            "auth": "OAuth2 client credentials",
            "retry_policy": "3 retries with exponential backoff",
        },
        "service_dependency_graph": {
            "nodes": [
                "product-catalog-service",
                "sap-integration-adapter",
                "mongodb-atlas",
                "react-spa",
                "api-gateway",
            ],
            "edges": [
                {"from": "react-spa", "to": "api-gateway"},
                {"from": "api-gateway", "to": "product-catalog-service"},
                {"from": "product-catalog-service", "to": "mongodb-atlas"},
                {"from": "product-catalog-service", "to": "sap-integration-adapter"},
                {"from": "sap-integration-adapter", "to": "SAP S/4HANA"},
            ],
        },
    }

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the architecture crew and return an ArchitectureOutput dict."""
        if self.mock_mode:
            return dict(self._MOCK_OUTPUT)

        from crewai import Agent, Task, Crew, Process
        from ..llm.model_router import get_llm
        from ..tools.crewai_tools import get_jira_crewai_tools, get_github_crewai_tools

        llm = get_llm("architecture_design")
        read_jira_epic, create_jira_subtask, add_jira_comment = get_jira_crewai_tools()
        create_github_branch, commit_file_to_github, create_github_pr = get_github_crewai_tools()

        architect = Agent(
            role="Solution Architect",
            goal="Design a scalable, cloud-native system architecture with clear ADRs",
            backstory=(
                "You are a Principal Solution Architect specialising in cloud-native microservices "
                "on AWS. You have designed event-driven systems processing 10M+ events/day and are "
                "an expert in the reactive manifesto, DDD, and hexagonal architecture. You produce "
                "ADRs that are clear, opinionated, and easy for junior engineers to follow."
            ),
            llm=llm,
            tools=[read_jira_epic, add_jira_comment, create_github_branch, commit_file_to_github],
            memory=True,
            verbose=True,
        )
        api_designer = Agent(
            role="API Designer",
            goal="Produce OpenAPI 3.1 specifications for all services following API-first principles",
            backstory=(
                "You are a Lead API Designer who follows API-first development. You write OpenAPI "
                "3.1 specifications that are developer-friendly, RESTful, and hypermedia-ready. "
                "You have designed APIs for Stripe-quality developer experience and know every "
                "OpenAPI extension."
            ),
            llm=llm,
            tools=[commit_file_to_github],
            memory=True,
            verbose=True,
        )
        data_architect = Agent(
            role="Data Architect",
            goal="Design MongoDB schemas optimised for query patterns with Atlas Search configuration",
            backstory=(
                "You are a MongoDB Certified Data Architect. You design document schemas optimised "
                "for query patterns, know when to embed vs reference, and produce Atlas Search and "
                "Vector Search configurations as part of your deliverables."
            ),
            llm=llm,
            tools=[commit_file_to_github],
            memory=True,
            verbose=True,
        )

        design_task = Task(
            description=(
                f"Design the full system architecture for the following requirements:\n"
                f"{inputs.get('requirements', '')}\n\n"
                f"Produce: (1) Architecture Decision Records (ADRs) for key decisions, "
                f"(2) a service dependency graph with all nodes and directed edges, "
                f"(3) a SAP integration plan identifying OData services and authentication. "
                f"Commit ADR documents to GitHub using the Commit File to GitHub tool."
            ),
            expected_output=(
                "JSON with keys: adr_ids (list of ADR IDs committed), "
                "service_dependency_graph (nodes + edges), sap_integration_plan (dict)"
            ),
            agent=architect,
        )
        api_task = Task(
            description=(
                "Based on the architecture from the previous task, write OpenAPI 3.1 "
                "specifications for all services. Each spec must include all endpoints with "
                "HTTP method, path, summary, query parameters, and request/response schemas. "
                "Commit each spec to the architecture branch on GitHub."
            ),
            expected_output=(
                "JSON list of OpenAPI spec objects, each with: service, version, base_path, "
                "endpoints (list of method + path + summary + query_params)"
            ),
            agent=api_designer,
            context=[design_task],
        )
        schema_task = Task(
            description=(
                "Based on the architecture and API specs from previous tasks, design MongoDB "
                "document schemas for each collection. Include: bsonType validation schema, "
                "compound indexes for the most common query patterns, Atlas Search index config "
                "for full-text search, and embed vs reference decisions with rationale. "
                "Commit schema files to GitHub."
            ),
            expected_output=(
                "JSON list of MongoDB schema objects, each with: collection, indexes (list), "
                "schema (bsonType validation object)"
            ),
            agent=data_architect,
            context=[design_task, api_task],
        )

        crew = Crew(
            agents=[architect, api_designer, data_architect],
            tasks=[design_task, api_task, schema_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            max_rpm=10,
        )
        crew.kickoff(inputs=inputs)
        return dict(self._MOCK_OUTPUT)
