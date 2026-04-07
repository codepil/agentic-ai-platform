# DevOps Crew

Parent blueprint: [blueprint.md](../../blueprint.md)

---

## Purpose

The DevOps Crew provisions cloud infrastructure, authors CI/CD pipelines, and executes the deployment to staging or production. It produces a `DeploymentResult` TypedDict with service URLs, PR URL, pipeline run URL, and deployment timestamp — which flows into the final LangGraph state.

---

## Process Type

**`Process.sequential`**

Tasks execute in order: Infrastructure Engineer → CI/CD Specialist → DevOps Lead. Infrastructure must be provisioned before pipelines are written; pipelines must exist before deployment executes.

---

## Agent Roster

### 1. Infrastructure Engineer

| Field | Value |
|-------|-------|
| Role | Infrastructure Engineer |
| Goal | Provision all cloud resources for the target environment using Terraform with IaC best practices and least-privilege IAM |
| Tools | `Create GitHub Branch`, `Commit File to GitHub` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Terraform and AWS expert who provisions infrastructure as code. You write reusable Terraform modules, manage remote state in S3, and follow the principle of least privilege in all IAM configurations.

---

### 2. CI/CD Specialist

| Field | Value |
|-------|-------|
| Role | CI/CD Specialist |
| Goal | Author GitHub Actions workflows that build, test, and deploy all services to the target environment with quality gates and automatic rollback |
| Tools | `Commit File to GitHub`, `Create GitHub PR` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Senior Platform Engineer with deep expertise in Kubernetes, GitOps, and zero-downtime deployment strategies. You design CI/CD pipelines that are fast, reliable, and observable, with automatic rollback on SLO breach.

---

### 3. DevOps Lead

| Field | Value |
|-------|-------|
| Role | DevOps Lead |
| Goal | Execute the deployment, verify service health, and confirm SLOs are met post-deployment |
| Tools | `Create GitHub PR`, `Add Jira Comment` |
| Memory | `True` |

**Backstory (full prompt text)**

> You are a Senior Platform Engineer with deep expertise in Kubernetes, GitOps, and zero-downtime deployment strategies. You design CI/CD pipelines that are fast, reliable, and observable, with automatic rollback on SLO breach.

---

## Task Definitions

### `tf_task`

| Field | Value |
|-------|-------|
| Agent | Infrastructure Engineer |
| Context dependencies | `[]` (first task) |
| Description | Write Terraform modules for the target environment. Includes: EKS cluster, MongoDB Atlas cluster, ALB ingress + Route53 DNS, IAM roles (IRSA), S3 remote state backend with DynamoDB lock. Create a branch and commit all `.tf` files to GitHub. |
| Expected output | JSON: `{branch_name, committed_files[], estimated_resources[]}` |

---

### `cicd_task`

| Field | Value |
|-------|-------|
| Agent | CI/CD Specialist |
| Context dependencies | `[tf_task]` |
| Description | Write GitHub Actions workflows: `ci.yml` (build/test/scan) and `deploy-{env}.yml` (deploy on merge). Quality gates: fail if coverage < 80% or critical CVEs exist. Commit workflows and open a PR. |
| Expected output | JSON: `{pr_url, workflow_files[], pipeline_run_url}` |

---

### `deploy_task`

| Field | Value |
|-------|-------|
| Agent | DevOps Lead |
| Context dependencies | `[cicd_task]` |
| Description | Execute the deployment using the CI/CD pipeline. Verify all pods are healthy, health checks return 200, service URLs are accessible, and no SLO breaches occur in the first 5 minutes. Add a Jira comment confirming deployment status. |
| Expected output | JSON `DeploymentResult`: `{environment, service_urls{}, git_pr_url, pipeline_run_url, deployed_at}` |

---

## Crew Configuration

| Parameter | Value |
|-----------|-------|
| `process` | `Process.sequential` |
| `verbose` | `True` |
| `memory` | `True` |
| `max_rpm` | `10` |

---

## Output Mapping — `DeploymentResult` TypedDict

The crew returns `{"deployment": DeploymentResult}` which is merged into `SDLCState.deployment`.

| Crew output key | TypedDict field | Type |
|-----------------|-----------------|------|
| `deployment.environment` | `deployment.environment` | `str` (`"staging"` / `"production"`) |
| `deployment.service_urls` | `deployment.service_urls` | `Dict[str, str]` |
| `deployment.git_pr_url` | `deployment.git_pr_url` | `str` |
| `deployment.pipeline_run_url` | `deployment.pipeline_run_url` | `str` |
| `deployment.deployed_at` | `deployment.deployed_at` | `str` (ISO-8601) |

Validated by `DevOpsCrewOutput` Pydantic model in `output_models.py`.

---

## Pydantic Output Models

```python
class DeploymentResultModel(BaseModel):
    environment: str
    service_urls: Dict[str, str]
    git_pr_url: str
    pipeline_run_url: str
    deployed_at: str

class DevOpsCrewOutput(BaseModel):
    deployment: DeploymentResultModel
```

All models use `model_config = ConfigDict(extra='allow')`.

---

## Mock vs Real Mode

| Mode | Behaviour |
|------|-----------|
| `MOCK_MODE=true` | Returns `_mock_deployment(environment)` — generates a `DeploymentResult` with environment-specific service URLs (`staging.*` or `prod.*`), a hardcoded GitHub PR URL, pipeline URL, and the current UTC timestamp as `deployed_at`. No CrewAI imports. |
| `MOCK_MODE=false` | Real sequential CrewAI crew. LLMs: `get_llm("generate_terraform")` (Haiku) for Infra Engineer, `get_llm("generate_cicd_yaml")` (Haiku) for CI/CD Specialist and DevOps Lead. GitHub tools commit Terraform and workflow files. Jira tools add deployment comments. |

### Environment Determination

The `environment` is read from `inputs.get("environment", "staging")`. The workflow invokes the DevOps crew twice:
1. `devops_node` with `environment="staging"` → staging deployment
2. `deploy_prod_node` with `environment="production"` → production deployment (after human approval)

---

## File Locations

| File | Path |
|------|------|
| Crew implementation | `agent-engine/src/platform/crews/devops_crew.py` |
| Output model | `agent-engine/src/platform/crews/output_models.py` |
| CrewAI tools | `agent-engine/src/platform/tools/crewai_tools.py` |
| GitHub client | `agent-engine/src/platform/tools/github_tools.py` |
| Jira client | `agent-engine/src/platform/tools/jira_tools.py` |
| Tests | `agent-engine/tests/test_crews.py::TestDevOpsCrew` |
