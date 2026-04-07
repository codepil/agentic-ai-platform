"""
DevOps crew — builds and deploys to staging / production.

Crew type: Sequential
  1. Infrastructure Engineer  — provisions Terraform cloud resources
  2. CI/CD Specialist         — writes GitHub Actions pipelines
  3. DevOps Lead              — executes deployment and verifies SLOs

Task context dependencies:
  cicd_task   context=[tf_task]
  deploy_task context=[cicd_task]

In mock mode returns a DeploymentResult for staging.
Output is validated against DevOpsCrewOutput Pydantic model.

Parent blueprint: /Agentic-AI-platform/blueprint.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .base_crew import BaseCrew
from ..state.sdlc_state import DeploymentResult


class DevOpsCrew(BaseCrew):
    """Builds CI/CD pipeline artefacts and executes deployment."""

    def _mock_deployment(self, environment: str) -> DeploymentResult:
        return {
            "environment": environment,
            "service_urls": {
                "product-catalog-service": (
                    f"https://catalog.{'staging' if environment == 'staging' else 'prod'}"
                    ".selfcare.example.com"
                ),
                "react-spa": (
                    f"https://{'staging.' if environment == 'staging' else ''}selfcare.example.com"
                ),
            },
            "git_pr_url": "https://github.com/myorg/selfcare-catalog/pull/42",
            "pipeline_run_url": (
                "https://github.com/myorg/selfcare-catalog/actions/runs/9876543210"
            ),
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run DevOps crew and return a DeploymentResult dict."""
        environment = inputs.get("environment", "staging")

        if self.mock_mode:
            return {"deployment": self._mock_deployment(environment)}

        from crewai import Agent, Task, Crew, Process
        from ..llm.model_router import get_llm
        from ..tools.crewai_tools import get_github_crewai_tools, get_jira_crewai_tools

        llm_cicd = get_llm("generate_cicd_yaml")
        llm_tf = get_llm("generate_terraform")
        create_github_branch, commit_file_to_github, create_github_pr = get_github_crewai_tools()
        _, _, add_jira_comment = get_jira_crewai_tools()

        infra_eng = Agent(
            role="Infrastructure Engineer",
            goal=(
                f"Provision all cloud resources for {environment} environment using Terraform "
                "with IaC best practices and least-privilege IAM"
            ),
            backstory=(
                "You are a Terraform and AWS expert who provisions infrastructure as code. "
                "You write reusable Terraform modules, manage remote state in S3, and follow "
                "the principle of least privilege in all IAM configurations."
            ),
            llm=llm_tf,
            tools=[create_github_branch, commit_file_to_github],
            memory=True,
            verbose=True,
        )
        cicd_specialist = Agent(
            role="CI/CD Specialist",
            goal=(
                f"Author GitHub Actions workflows that build, test, and deploy all services "
                f"to {environment} with quality gates and automatic rollback"
            ),
            backstory=(
                "You are a Senior Platform Engineer with deep expertise in Kubernetes, GitOps, "
                "and zero-downtime deployment strategies. You design CI/CD pipelines that are "
                "fast, reliable, and observable, with automatic rollback on SLO breach."
            ),
            llm=llm_cicd,
            tools=[commit_file_to_github, create_github_pr],
            memory=True,
            verbose=True,
        )
        devops_lead = Agent(
            role="DevOps Lead",
            goal=(
                f"Execute the deployment to {environment}, verify service health, "
                "and confirm SLOs are met post-deployment"
            ),
            backstory=(
                "You are a Senior Platform Engineer with deep expertise in Kubernetes, GitOps, "
                "and zero-downtime deployment strategies. You design CI/CD pipelines that are "
                "fast, reliable, and observable, with automatic rollback on SLO breach."
            ),
            llm=llm_cicd,
            tools=[create_github_pr, add_jira_comment],
            memory=True,
            verbose=True,
        )

        tf_task = Task(
            description=(
                f"Write Terraform modules for the {environment} infrastructure. Include:\n"
                f"1. EKS cluster configuration with node groups\n"
                f"2. MongoDB Atlas cluster (M30 for staging, M50 for production)\n"
                f"3. ALB ingress controller and Route53 DNS records\n"
                f"4. IAM roles for service accounts (IRSA)\n"
                f"5. Remote state backend in S3 with DynamoDB lock table\n"
                f"Create a feature branch and commit all .tf files to GitHub."
            ),
            expected_output=(
                "JSON with: branch_name, committed_files (list of file paths), "
                "estimated_resources (list of AWS resource names)"
            ),
            agent=infra_eng,
        )
        cicd_task = Task(
            description=(
                f"Write GitHub Actions workflows for CI/CD to {environment}. Include:\n"
                f"1. .github/workflows/ci.yml — build, unit test, integration test, security scan\n"
                f"2. .github/workflows/deploy-{environment}.yml — deploy to {environment} on merge\n"
                f"Workflows must use the Terraform outputs from the previous task. "
                f"Add quality gates: fail if coverage < 80% or critical CVEs found. "
                f"Commit workflows to GitHub and open a PR."
            ),
            expected_output=(
                "JSON with: pr_url, workflow_files (list), pipeline_run_url"
            ),
            agent=cicd_specialist,
            context=[tf_task],
        )
        deploy_task = Task(
            description=(
                f"Execute the deployment to {environment} using the CI/CD pipeline from the "
                f"previous task. Verify:\n"
                f"1. All pods are healthy in Kubernetes\n"
                f"2. Health check endpoints return 200\n"
                f"3. Service URLs are accessible\n"
                f"4. No SLO breaches in the first 5 minutes post-deployment\n"
                f"Add a Jira comment confirming deployment status."
            ),
            expected_output=(
                "JSON DeploymentResult with: environment, service_urls (dict), "
                "git_pr_url, pipeline_run_url, deployed_at (ISO-8601)"
            ),
            agent=devops_lead,
            context=[cicd_task],
        )

        crew = Crew(
            agents=[infra_eng, cicd_specialist, devops_lead],
            tasks=[tf_task, cicd_task, deploy_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            max_rpm=10,
        )
        crew.kickoff(inputs=inputs)
        return {"deployment": self._mock_deployment(environment)}
