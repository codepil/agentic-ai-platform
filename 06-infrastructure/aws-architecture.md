# AWS Deployment Architecture — Agentic AI Platform

## Table of Contents

1. [Overview](#1-overview)
2. [Network Topology](#2-network-topology)
3. [Component Descriptions](#3-component-descriptions)
4. [Security Group Rules](#4-security-group-rules)
5. [IAM Roles](#5-iam-roles)
6. [Data Flow — SDLC Run](#6-data-flow--sdlc-run)
7. [Deployment Pipeline](#7-deployment-pipeline)
8. [Cost Estimate](#8-cost-estimate)

---

## 1. Overview

The Agentic AI Platform is deployed as a **3-tier architecture** on AWS, starting from a blank AWS account. The three tiers map cleanly to distinct network planes:

| Tier | Technology | AWS Plane |
|------|-----------|-----------|
| Presentation | ReactJS MFEs (Shell + Project + Agent UIs) | S3 + CloudFront (CDN edge) |
| Application | Java Spring Boot (platform-app) + Python FastAPI (agent-engine) | ECS Fargate, Private subnets |
| Data | MongoDB Atlas M30 | Atlas Private Link, Isolated subnets |

### Design Principles

- **Zero-trust networking**: no ECS task has a public IP; all inbound traffic enters through the ALB
- **Secrets never in environment variables at rest**: all secrets injected at task startup from AWS Secrets Manager
- **Immutable infrastructure**: ECR-tagged images promoted through dev → staging → prod; no SSH into containers
- **HA by default in prod**: 2 AZs, 2 NAT Gateways, minimum 2 tasks per service
- **DR via Atlas geo-distribution**: primary cluster in us-east-1, read replica / failover in eu-west-1
- **OIDC-based CI/CD**: GitHub Actions assumes an IAM role via OIDC — no long-lived AWS credentials stored in GitHub

### Primary Region

**us-east-1** — all compute, networking, and AWS-managed services.
MongoDB Atlas has its primary data-bearing nodes in us-east-1; an Atlas electable/read-only node is placed in eu-west-1 for DR.

---

## 2. Network Topology

### VPC Layout

```
AWS Account — us-east-1
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  VPC: agentic-ai-vpc  (10.0.0.0/16)                                                        │
│                                                                                             │
│  ┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────┐│
│  │  Availability Zone: us-east-1a           │  │  Availability Zone: us-east-1b           ││
│  │                                          │  │                                          ││
│  │  ┌────────────────────────────────────┐  │  │  ┌────────────────────────────────────┐  ││
│  │  │  PUBLIC SUBNET  10.0.1.0/24        │  │  │  │  PUBLIC SUBNET  10.0.2.0/24        │  ││
│  │  │  - ALB node (internet-facing)      │  │  │  │  - ALB node (internet-facing)      │  ││
│  │  │  - NAT Gateway A  (EIP-A)          │  │  │  │  - NAT Gateway B  (EIP-B)          │  ││
│  │  └────────────────────────────────────┘  │  │  └────────────────────────────────────┘  ││
│  │              │                           │  │              │                           ││
│  │              │ (default route → IGW)     │  │              │ (default route → IGW)     ││
│  │                                          │  │                                          ││
│  │  ┌────────────────────────────────────┐  │  │  ┌────────────────────────────────────┐  ││
│  │  │  PRIVATE SUBNET  10.0.11.0/24      │  │  │  │  PRIVATE SUBNET  10.0.12.0/24      │  ││
│  │  │  - ECS Fargate: platform-app :8080 │  │  │  │  - ECS Fargate: platform-app :8080 │  ││
│  │  │  - ECS Fargate: agent-engine :8000 │  │  │  │  - ECS Fargate: agent-engine :8000 │  ││
│  │  └────────────────────────────────────┘  │  │  └────────────────────────────────────┘  ││
│  │              │                           │  │              │                           ││
│  │              │ (default route → NAT-A)   │  │              │ (default route → NAT-B)   ││
│  │                                          │  │                                          ││
│  │  ┌────────────────────────────────────┐  │  │  ┌────────────────────────────────────┐  ││
│  │  │  ISOLATED SUBNET  10.0.21.0/24     │  │  │  │  ISOLATED SUBNET  10.0.22.0/24     │  ││
│  │  │  - MongoDB Atlas Private Link ENI  │  │  │  │  - MongoDB Atlas Private Link ENI  │  ││
│  │  │  - VPC Interface Endpoints:        │  │  │  │  - VPC Interface Endpoints:        │  ││
│  │  │    * secretsmanager                │  │  │  │    * secretsmanager                │  ││
│  │  │    * ecr.api / ecr.dkr             │  │  │  │    * ecr.api / ecr.dkr             │  ││
│  │  │    * logs                          │  │  │  │    * logs                          │  ││
│  │  │    * sts                           │  │  │  │    * sts                           │  ││
│  │  └────────────────────────────────────┘  │  │  └────────────────────────────────────┘  ││
│  │  (no default route — no internet path)   │  │  (no default route — no internet path)   ││
│  └──────────────────────────────────────────┘  └──────────────────────────────────────────┘│
│                                                                                             │
│  Internet Gateway (igw-agentic-ai)                                                         │
│  S3 Gateway Endpoint (free — routes S3 traffic without NAT)                                │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                │
         Internet (0.0.0.0/0)
                │
         ┌──────┴──────┐
         │  Route 53   │  platform-api.yourdomain.com → ALB DNS name
         └──────┬──────┘
                │
         ┌──────┴──────┐
         │    ACM      │  *.yourdomain.com TLS certificate
         └─────────────┘
```

### Route Tables

| Route Table | Subnet(s) | Routes |
|-------------|-----------|--------|
| `rtb-public` | 10.0.1.0/24, 10.0.2.0/24 | 10.0.0.0/16 → local; 0.0.0.0/0 → IGW |
| `rtb-private-1a` | 10.0.11.0/24 | 10.0.0.0/16 → local; 0.0.0.0/0 → NAT-A; pl-s3 → S3 GW endpoint |
| `rtb-private-1b` | 10.0.12.0/24 | 10.0.0.0/16 → local; 0.0.0.0/0 → NAT-B; pl-s3 → S3 GW endpoint |
| `rtb-isolated` | 10.0.21.0/24, 10.0.22.0/24 | 10.0.0.0/16 → local only (no IGW, no NAT) |

### VPC Endpoints

All VPC Interface Endpoints are placed in the isolated subnets so that ECS tasks in private subnets reach AWS APIs over the AWS backbone (no NAT GW cost for these calls):

| Endpoint | Type | Purpose |
|----------|------|---------|
| `com.amazonaws.us-east-1.secretsmanager` | Interface | Secrets injection at task start |
| `com.amazonaws.us-east-1.ecr.api` | Interface | ECR image pull (control plane) |
| `com.amazonaws.us-east-1.ecr.dkr` | Interface | ECR image pull (data plane) |
| `com.amazonaws.us-east-1.logs` | Interface | CloudWatch Logs from Fargate |
| `com.amazonaws.us-east-1.sts` | Interface | Task role credential vending |
| `com.amazonaws.us-east-1.s3` | Gateway | ECR layer downloads; no cost |

---

## 3. Component Descriptions

### 3.1 Application Load Balancer (ALB)

| Attribute | Value |
|-----------|-------|
| Scheme | internet-facing |
| Subnets | Public: 10.0.1.0/24, 10.0.2.0/24 |
| Security Group | `sg-alb` (see §4) |
| DNS | `platform-api.yourdomain.com` via Route 53 ALIAS |
| TLS Certificate | ACM `*.yourdomain.com` (auto-renewed) |
| TLS Policy | `ELBSecurityPolicy-TLS13-1-2-2021-06` (TLS 1.2+ only) |
| Access Logs | S3 bucket `agentic-ai-alb-logs` |

**Listeners:**

- **HTTP:80** — redirect rule: `HTTP 301 → https://#{host}:443/#{path}?#{query}`
- **HTTPS:443** — path-based routing:

| Priority | Condition | Target Group | Protocol |
|----------|-----------|-------------|---------|
| 10 | Path `/ws/*` | `tg-platform-app` | WebSocket (HTTP/1.1 upgrade preserved) |
| 20 | Path `/api/*` | `tg-platform-app` | HTTP/1.1 |
| 100 | Default (404) | Fixed response | — |

**Target Group `tg-platform-app`:**
- Protocol: HTTP, Port: 8080
- Health check: `GET /actuator/health`, interval 30s, healthy threshold 2, unhealthy threshold 3
- Deregistration delay: 30s (fast drain for rolling deploys)
- Stickiness: disabled (stateless; WebSocket sessions managed at app level)

> **Note:** agent-engine is NOT registered with the ALB. It is an internal service reachable only from platform-app tasks via internal DNS (`agent-engine.agentic-ai.local:8000` via AWS Cloud Map / ECS Service Connect).

---

### 3.2 ECS Fargate — platform-app (Java Spring Boot)

| Attribute | Value |
|-----------|-------|
| Cluster | `agentic-ai-cluster` |
| Launch type | FARGATE |
| CPU | 1024 (1 vCPU) |
| Memory | 2048 MiB |
| Network mode | `awsvpc` |
| Subnets | Private: 10.0.11.0/24, 10.0.12.0/24 |
| Security Group | `sg-platform-app` |
| Public IP | DISABLED |
| Image | `<account>.dkr.ecr.us-east-1.amazonaws.com/platform-app-repo:<tag>` |
| Task Role | `ecs-task-role-platform-app` |
| Execution Role | `ecs-task-execution-role` |

**Auto Scaling:**
- Min capacity: 2 tasks (HA — one per AZ)
- Max capacity: 6 tasks
- Scale-out: CPU utilization > 70% for 2 consecutive minutes → +1 task
- Scale-in: CPU utilization < 30% for 10 consecutive minutes → -1 task
- Cooldown: 120s scale-out, 300s scale-in

**Environment Variables (injected from Secrets Manager at task start):**

| Variable | Secrets Manager ARN |
|----------|-------------------|
| `OKTA_ISSUER_URI` | `arn:aws:secretsmanager:us-east-1:<acct>:secret:agentic-ai/okta-issuer-uri` |
| `MONGO_URI` | `arn:aws:secretsmanager:us-east-1:<acct>:secret:agentic-ai/mongo-uri` |
| `AGENT_ENGINE_BASE_URL` | `http://agent-engine.agentic-ai.local:8000` (ECS Service Connect) |

**Logging:**
- Log driver: `awslogs`
- Log group: `/ecs/platform-app`
- Retention: 30 days
- Stream prefix: `platform-app`

---

### 3.3 ECS Fargate — agent-engine (Python FastAPI)

| Attribute | Value |
|-----------|-------|
| Cluster | `agentic-ai-cluster` |
| Launch type | FARGATE |
| CPU | 2048 (2 vCPU) |
| Memory | 4096 MiB |
| Network mode | `awsvpc` |
| Subnets | Private: 10.0.11.0/24, 10.0.12.0/24 |
| Security Group | `sg-agent-engine` |
| Public IP | DISABLED |
| Image | `<account>.dkr.ecr.us-east-1.amazonaws.com/agent-engine-repo:<tag>` |
| Task Role | `ecs-task-role-agent-engine` |
| Execution Role | `ecs-task-execution-role` |

> **Why 4 GiB memory?** LLM client libraries (Anthropic SDK, LangChain) load tokenizer models and maintain connection pools in-process. Under concurrent SDLC runs, each FastAPI worker can consume 600–800 MiB. 4 GiB provides headroom for 4 concurrent workers with safe overhead.

**Auto Scaling:**
- Min capacity: 1 task (cost-optimized; scale up on demand)
- Max capacity: 4 tasks
- Scale-out: CPU > 70% for 2 minutes → +1 task
- Scale-in: CPU < 20% for 15 minutes → -1 task (longer cooldown — LLM calls are bursty)

**Environment Variables:**

| Variable | Source |
|----------|--------|
| `MOCK_MODE` | ECS task definition env var (not in Secrets Manager — non-sensitive flag) |
| `ANTHROPIC_API_KEY` | Secrets Manager `agentic-ai/anthropic-api-key` |
| `SLACK_WEBHOOK_URL` | Secrets Manager `agentic-ai/slack-webhook-url` |
| `JIRA_TOKEN` | Secrets Manager `agentic-ai/jira-token` |
| `GITHUB_TOKEN` | Secrets Manager `agentic-ai/github-token` |
| `FIGMA_TOKEN` | Secrets Manager `agentic-ai/figma-token` |

**MOCK_MODE behavior:**
- `MOCK_MODE=true` — agent-engine returns canned JSON responses; no Anthropic API calls made. Used in dev/CI to eliminate API costs and latency.
- `MOCK_MODE=false` (default prod) — live Anthropic Claude calls.

**Logging:**
- Log group: `/ecs/agent-engine`
- Retention: 30 days

---

### 3.4 Amazon ECR (Elastic Container Registry)

| Repository | Scan on Push | Lifecycle Policy |
|-----------|-------------|-----------------|
| `platform-app-repo` | Enabled (OS + programming language CVEs) | Keep last 10 tagged images; expire untagged images after 1 day |
| `agent-engine-repo` | Enabled | Keep last 10 tagged images; expire untagged images after 1 day |

**Image tagging convention:** `<git-short-sha>-<YYYYMMDD>` (e.g., `a3f91bc-20260407`). The `latest` tag is never used in production task definitions — explicit SHA tags ensure rollback traceability.

---

### 3.5 AWS Secrets Manager

All secrets are stored under the prefix `agentic-ai/` for IAM policy scoping:

| Secret Name | Description | Rotation |
|-------------|-------------|---------|
| `agentic-ai/okta-issuer-uri` | Okta OAuth2 issuer URL for Spring Security | Manual |
| `agentic-ai/mongo-uri` | MongoDB Atlas connection string with credentials | Manual (Atlas credential rotation) |
| `agentic-ai/anthropic-api-key` | Anthropic Claude API key | Manual |
| `agentic-ai/slack-webhook-url` | Slack incoming webhook for notifications | Manual |
| `agentic-ai/jira-token` | Jira personal access token | Manual |
| `agentic-ai/github-token` | GitHub App installation token | Manual (90-day expiry alert) |
| `agentic-ai/figma-token` | Figma personal access token | Manual |

**Access pattern:** Secrets are referenced in ECS task definitions using `valueFrom` with the secret ARN. They are injected as environment variables at container startup by the ECS agent — they never appear in CloudWatch Logs or task definition plaintext.

---

### 3.6 MongoDB Atlas Private Link

| Attribute | Value |
|-----------|-------|
| Cluster tier | M30 (dedicated, 8 GB RAM, 40 GB NVMe SSD) |
| Atlas region | us-east-1 (AWS) |
| DR node | eu-west-1 (Atlas electable node, priority 0) |
| Connection method | AWS PrivateLink (VPC endpoint in isolated subnets) |
| Public access | Disabled (IP Access List: VPC endpoint only) |
| TLS | Enforced (Atlas default, cannot be disabled on M30+) |

**PrivateLink Setup:**
1. Atlas generates a PrivateLink service (AWS service endpoint) in us-east-1.
2. AWS VPC Interface Endpoint is created in isolated subnets (10.0.21.0/24, 10.0.22.0/24).
3. ECS tasks in private subnets connect to the Atlas Private Link DNS name: `mongodb+srv://<cluster>.xxxx.mongodb.net` — DNS resolves to the private endpoint IP.
4. No traffic leaves the AWS network.

**Why isolated subnets for the endpoint?** The Atlas PrivateLink endpoint does not need outbound internet access. Placing it in an isolated subnet (no route table entry to NAT or IGW) enforces that even if the endpoint ENI is misconfigured, it cannot be used as an egress path.

---

### 3.7 Amazon CloudWatch

**Log Groups:**

| Log Group | Retention | Services |
|-----------|-----------|---------|
| `/ecs/platform-app` | 30 days | Spring Boot structured JSON logs |
| `/ecs/agent-engine` | 30 days | FastAPI uvicorn + agent step logs |
| `/vpc/flow-logs` | 30 days | VPC Flow Logs (accepted + rejected) |

**Alarms:**

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| `platform-app-cpu-high` | ECS CPUUtilization | > 80% for 5 min | SNS → PagerDuty |
| `platform-app-memory-high` | ECS MemoryUtilization | > 85% for 5 min | SNS → PagerDuty |
| `agent-engine-cpu-high` | ECS CPUUtilization | > 85% for 5 min | SNS → PagerDuty |
| `alb-5xx-rate` | ALB HTTPCode_ELB_5XX_Count | > 10 in 1 min | SNS → Slack |
| `alb-target-5xx-rate` | ALB HTTPCode_Target_5XX_Count | > 20 in 1 min | SNS → Slack |
| `alb-latency-p99` | TargetResponseTime (p99) | > 5s for 3 min | SNS → Slack |
| `active-sdlc-runs` | Custom metric `AgenticAI/ActiveSDLCRuns` | > 50 | SNS → Slack (capacity warning) |

**Custom Metric — ActiveSDLCRuns:**
platform-app publishes this metric via the CloudWatch SDK whenever a SDLC orchestration run transitions to RUNNING or COMPLETED. This provides a business-level SLI separate from infrastructure CPU metrics.

---

### 3.8 Route 53 & ACM

**Route 53:**
- Hosted zone: `yourdomain.com` (public)
- Record: `platform-api.yourdomain.com` → ALIAS to ALB DNS name (no TTL, health-check aware)
- Health check: ALB endpoint `GET /actuator/health` — if unhealthy, Route 53 can failover (optional, configure per requirements)

**ACM:**
- Certificate: `*.yourdomain.com` (wildcard covers `platform-api`, `app`, future subdomains)
- Validation: DNS validation (CNAME record in Route 53, auto-renewed by ACM)
- Attached to: ALB HTTPS:443 listener

---

### 3.9 ReactJS MFEs — CDN Layer

This layer is managed separately from backend infrastructure but documented here for completeness:

| Component | AWS Service | Details |
|-----------|------------|---------|
| MFE bundles | S3 bucket | Versioned, public access blocked; CloudFront is the only origin |
| CDN | CloudFront | OAC (Origin Access Control) restricts direct S3 access |
| TLS | ACM (us-east-1) | `app.yourdomain.com` |
| Invalidation | GitHub Actions | `aws cloudfront create-invalidation` on deploy |
| Security headers | CloudFront response headers policy | HSTS, CSP, X-Frame-Options |

---

## 4. Security Group Rules

### sg-alb (Application Load Balancer)

| Direction | Protocol | Port | Source/Destination | Rationale |
|-----------|----------|------|--------------------|-----------|
| Inbound | TCP | 443 | 0.0.0.0/0, ::/0 | HTTPS from internet |
| Inbound | TCP | 80 | 0.0.0.0/0, ::/0 | HTTP redirect to HTTPS |
| Outbound | TCP | 8080 | sg-platform-app | Forward to platform-app tasks |

### sg-platform-app (ECS Fargate — platform-app)

| Direction | Protocol | Port | Source/Destination | Rationale |
|-----------|----------|------|--------------------|-----------|
| Inbound | TCP | 8080 | sg-alb | ALB health checks + traffic forwarding |
| Outbound | TCP | 8000 | sg-agent-engine | Call agent-engine REST API |
| Outbound | TCP | 443 | VPC endpoints SG | Secrets Manager, ECR, CloudWatch, STS |
| Outbound | TCP | 27017 | sg-atlas-endpoint | MongoDB Atlas via PrivateLink |
| Outbound | TCP | 443 | pl-s3 (prefix list) | S3 Gateway endpoint (ECR layer pulls) |

> **No outbound 0.0.0.0/0** — platform-app has no direct internet egress. NAT Gateway is the only path for any traffic not matching the above rules, and platform-app should not need it in steady state. NAT is available for unexpected outbound (e.g., third-party health check URLs); monitor NAT GW bytes to detect unexpected egress.

### sg-agent-engine (ECS Fargate — agent-engine)

| Direction | Protocol | Port | Source/Destination | Rationale |
|-----------|----------|------|--------------------|-----------|
| Inbound | TCP | 8000 | sg-platform-app | Accept calls only from platform-app |
| Outbound | TCP | 443 | 0.0.0.0/0 (via NAT) | Anthropic API, Slack, Jira, GitHub, Figma |
| Outbound | TCP | 443 | VPC endpoints SG | Secrets Manager, ECR, CloudWatch, STS |
| Outbound | TCP | 27017 | sg-atlas-endpoint | MongoDB Atlas via PrivateLink |
| Outbound | TCP | 443 | pl-s3 (prefix list) | S3 Gateway endpoint |

> agent-engine requires internet egress for external SaaS APIs (Anthropic, Slack, Jira, GitHub, Figma). This egress flows through NAT Gateway → Internet Gateway. All external calls use TLS; outbound port 80 is not allowed.

### sg-vpc-endpoints (VPC Interface Endpoints)

| Direction | Protocol | Port | Source/Destination | Rationale |
|-----------|----------|------|--------------------|-----------|
| Inbound | TCP | 443 | sg-platform-app | platform-app accesses AWS APIs |
| Inbound | TCP | 443 | sg-agent-engine | agent-engine accesses AWS APIs |
| Outbound | All | All | VPC CIDR 10.0.0.0/16 | Responses back into VPC only |

### sg-atlas-endpoint (MongoDB Atlas PrivateLink ENI)

| Direction | Protocol | Port | Source/Destination | Rationale |
|-----------|----------|------|--------------------|-----------|
| Inbound | TCP | 27017 | sg-platform-app | Spring Data MongoDB |
| Inbound | TCP | 27017 | sg-agent-engine | Agent reads/writes run state |
| Outbound | All | All | 10.0.0.0/16 | Responses only |

---

## 5. IAM Roles

### 5.1 ECS Task Execution Role — `ecs-task-execution-role`

**Used by:** ECS agent (not your application code). Controls what the ECS control plane can do on your behalf at task startup.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuth",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECRPull",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": [
        "arn:aws:ecr:us-east-1:<account>:repository/platform-app-repo",
        "arn:aws:ecr:us-east-1:<account>:repository/agent-engine-repo"
      ]
    },
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:<account>:secret:agentic-ai/*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:us-east-1:<account>:log-group:/ecs/platform-app:*",
        "arn:aws:logs:us-east-1:<account>:log-group:/ecs/agent-engine:*"
      ]
    }
  ]
}
```

### 5.2 ECS Task Role — platform-app — `ecs-task-role-platform-app`

**Used by:** application code running inside platform-app containers. Scoped to only what the app needs at runtime (not ECR pull, not Secrets Manager — those are execution role concerns).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "AgenticAI"
        }
      }
    },
    {
      "Sid": "ECSServiceDiscovery",
      "Effect": "Allow",
      "Action": [
        "servicediscovery:DiscoverInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

### 5.3 ECS Task Role — agent-engine — `ecs-task-role-agent-engine`

**Used by:** FastAPI application code. Minimal — agent-engine calls external SaaS APIs (credentials from env vars) and reads/writes MongoDB (connection string from env var). No AWS API calls needed at runtime beyond CloudWatch.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "AgenticAI"
        }
      }
    }
  ]
}
```

### 5.4 GitHub Actions OIDC Role — `github-actions-deploy-role`

**Trust Policy** (OIDC — no static credentials stored in GitHub):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:your-org/agentic-ai-platform:*"
        }
      }
    }
  ]
}
```

**Permissions Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuth",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Sid": "ECRPush",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": [
        "arn:aws:ecr:us-east-1:<account>:repository/platform-app-repo",
        "arn:aws:ecr:us-east-1:<account>:repository/agent-engine-repo"
      ]
    },
    {
      "Sid": "ECSRollingDeploy",
      "Effect": "Allow",
      "Action": [
        "ecs:RegisterTaskDefinition",
        "ecs:DescribeTaskDefinition",
        "ecs:UpdateService",
        "ecs:DescribeServices"
      ],
      "Resource": [
        "arn:aws:ecs:us-east-1:<account>:service/agentic-ai-cluster/platform-app-service",
        "arn:aws:ecs:us-east-1:<account>:service/agentic-ai-cluster/agent-engine-service",
        "*"
      ]
    },
    {
      "Sid": "PassExecutionRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::<account>:role/ecs-task-execution-role"
    }
  ]
}
```

---

## 6. Data Flow — SDLC Run

This traces the complete request path for a user triggering a full SDLC orchestration run from the ReactJS frontend.

```
Step 1: Browser → CloudFront → S3
───────────────────────────────────
User opens app.yourdomain.com in browser.
CloudFront serves ReactJS MFE bundles from S3 (OAC, no public S3 access).
MFE Shell loads, authenticates user with Okta (PKCE flow, tokens stored in memory).

Step 2: ReactJS → Route 53 → ACM → ALB
────────────────────────────────────────
User clicks "Start SDLC Run" in Project MFE.
ReactJS sends:
  POST https://platform-api.yourdomain.com/api/sdlc/runs
  Authorization: Bearer <okta-access-token>
  Content-Type: application/json
  Body: { "projectId": "proj-001", "scope": "full" }

Route 53 resolves platform-api.yourdomain.com → ALB DNS (ALIAS, no TTL).
ALB terminates TLS using ACM wildcard cert.
ALB path rule: /api/* → tg-platform-app (port 8080).

Step 3: ALB → platform-app (ECS Fargate)
──────────────────────────────────────────
ALB forwards HTTP/1.1 request (TLS terminated) to a healthy platform-app task.
Spring Security validates the Okta JWT:
  - Fetches JWKS from OKTA_ISSUER_URI (cached; first call goes through NAT GW to Okta)
  - Validates signature, expiry, audience claim
  - Extracts userId, roles from token claims

Spring Boot controller creates a SdlcRun document in MongoDB Atlas:
  - Status: QUEUED
  - Publishes custom CloudWatch metric: AgenticAI/ActiveSDLCRuns +1

Step 4: platform-app → agent-engine (ECS Service Connect)
───────────────────────────────────────────────────────────
platform-app calls agent-engine via internal DNS:
  POST http://agent-engine.agentic-ai.local:8000/orchestrate
  X-Correlation-Id: <uuid>
  Body: { "runId": "run-abc123", "projectId": "proj-001", "scope": "full" }

Traffic stays entirely within the VPC private subnets.
sg-platform-app → sg-agent-engine on TCP 8000.
No NAT Gateway, no internet.

Step 5: agent-engine → External SaaS APIs (via NAT GW)
────────────────────────────────────────────────────────
agent-engine's orchestrator starts the SDLC pipeline:

  a. Requirements gathering:
     POST https://api.anthropic.com/v1/messages (Claude claude-opus-4-5)
     ← Egress: sg-agent-engine → NAT-A → IGW → internet → Anthropic
     ← Returns: structured requirements JSON

  b. GitHub integration:
     GET https://api.github.com/repos/<org>/<repo>/contents
     ← Fetches codebase structure for context

  c. Jira integration:
     POST https://<org>.atlassian.net/rest/api/3/issue
     ← Creates Jira tickets for each requirement

  d. Figma integration (if design exists):
     GET https://api.figma.com/v1/files/<file-id>
     ← Fetches design tokens and component specs

Step 6: agent-engine → MongoDB Atlas (via PrivateLink)
────────────────────────────────────────────────────────
At each orchestration step, agent-engine writes progress to Atlas:
  db.sdlcRuns.updateOne(
    { _id: "run-abc123" },
    { $set: { status: "RUNNING", currentStep: "requirements" },
      $push: { steps: { name: "requirements", status: "COMPLETE", output: {...} } } }
  )

Connection path: ECS task → sg-atlas-endpoint → Atlas PrivateLink ENI (10.0.21.x/22.x)
  → Atlas VPC endpoint → MongoDB Atlas M30 cluster
All traffic stays on AWS backbone. TLS enforced by Atlas (port 27017 with TLS).

Step 7: agent-engine → platform-app (response)
────────────────────────────────────────────────
agent-engine returns HTTP 202 Accepted to platform-app immediately
(orchestration continues asynchronously).
platform-app returns HTTP 202 to the ALB → browser:
  { "runId": "run-abc123", "status": "RUNNING" }

Step 8: ReactJS polls for status (WebSocket or polling)
─────────────────────────────────────────────────────────
ReactJS Agent MFE connects WebSocket:
  wss://platform-api.yourdomain.com/ws/runs/run-abc123

ALB /ws/* rule → tg-platform-app (WebSocket upgrade preserved by ALB).
platform-app Spring Boot WebSocket endpoint streams step updates to the browser
as each SDLC step completes (reads MongoDB change stream or internal event bus).

Step 9: Slack notification
───────────────────────────
On SDLC run completion, agent-engine posts to Slack:
  POST https://hooks.slack.com/services/<webhook>
  Body: { "text": "SDLC run run-abc123 completed for project proj-001" }
← Egress via NAT GW.

Step 10: CloudWatch metric update
───────────────────────────────────
platform-app publishes: AgenticAI/ActiveSDLCRuns -1 (run completed).
```

---

## 7. Deployment Pipeline

### GitHub Actions Workflows

Two separate workflows run in parallel for independent service deploys.

#### 7.1 platform-app Deploy (`.github/workflows/deploy-platform-app.yml`)

```yaml
name: Deploy platform-app

on:
  push:
    branches: [main]
    paths:
      - 'platform-app/**'
      - '.github/workflows/deploy-platform-app.yml'

permissions:
  id-token: write   # Required for OIDC
  contents: read

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: platform-app-repo
  ECS_CLUSTER: agentic-ai-cluster
  ECS_SERVICE: platform-app-service
  CONTAINER_NAME: platform-app

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<account>:role/github-actions-deploy-role
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set image tag
        id: image-tag
        run: |
          SHORT_SHA=$(git rev-parse --short HEAD)
          DATE=$(date +%Y%m%d)
          echo "tag=${SHORT_SHA}-${DATE}" >> $GITHUB_OUTPUT

      - name: Build, tag, push Docker image
        env:
          REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          TAG: ${{ steps.image-tag.outputs.tag }}
        working-directory: platform-app
        run: |
          docker build -t $REGISTRY/$ECR_REPOSITORY:$TAG .
          docker push $REGISTRY/$ECR_REPOSITORY:$TAG

      - name: Download current task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition platform-app \
            --query taskDefinition \
            > task-definition.json

      - name: Update task definition with new image
        id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: ${{ env.CONTAINER_NAME }}
          image: ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ steps.image-tag.outputs.tag }}

      - name: Deploy to ECS (rolling update)
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: ${{ env.ECS_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true
          # Rolling deploy: ECS replaces tasks one at a time.
          # ALB deregisters old task, drains connections (30s), terminates.
          # New task must pass 2 health checks before ALB routes traffic to it.
```

#### 7.2 agent-engine Deploy (`.github/workflows/deploy-agent-engine.yml`)

Identical structure with:
- `paths: ['agent-engine/**']`
- `ECR_REPOSITORY: agent-engine-repo`
- `ECS_SERVICE: agent-engine-service`
- `CONTAINER_NAME: agent-engine`

### Rolling Deploy Behavior

ECS rolling update configuration on both services:
- `minimumHealthyPercent: 100` — never drop below current running task count (zero-downtime)
- `maximumPercent: 200` — can temporarily double tasks during deploy
- Deploy sequence: launch new task → health check passes → register with ALB → drain old task (30s) → terminate old task

### Rollback

If `wait-for-service-stability: true` times out (10-minute default), the GitHub Actions step fails. The ECS service rolls back automatically to the previous task definition revision. The previous ECR image is retained by the lifecycle policy (last 10 tagged images).

---

## 8. Cost Estimate

All estimates are us-east-1 on-demand pricing as of Q1 2026. Actual costs depend on traffic and LLM call volume.

### Dev Environment

| Component | Configuration | Est. Monthly Cost |
|-----------|---------------|-------------------|
| ECS Fargate — platform-app | 2 tasks × 1vCPU/2GB × 730h | $47 |
| ECS Fargate — agent-engine | 1 task × 2vCPU/4GB × 730h | $47 |
| ALB | 1 ALB, ~1M requests/month | $22 |
| NAT Gateway | 1 NAT GW × 730h + 10 GB data | $37 |
| ECR | 2 repos, ~5 GB storage | $0.50 |
| Secrets Manager | 7 secrets | $2.80 |
| CloudWatch Logs | ~5 GB/month ingestion | $2.50 |
| CloudWatch Alarms | 8 alarms | $0.80 |
| VPC Endpoints (Interface) | 5 endpoints × 730h | $36 |
| Route 53 | 1 hosted zone + queries | $1 |
| MongoDB Atlas M30 | (billed by Atlas, not AWS) | ~$200 |
| **Dev Total (excl. Atlas)** | | **~$197/month** |

### Production Environment

| Component | Configuration | Est. Monthly Cost |
|-----------|---------------|-------------------|
| ECS Fargate — platform-app | Avg 3 tasks × 1vCPU/2GB × 730h | $70 |
| ECS Fargate — agent-engine | Avg 2 tasks × 2vCPU/4GB × 730h | $94 |
| ALB | 1 ALB, ~10M requests/month | $40 |
| NAT Gateway | 2 NAT GWs × 730h + 100 GB data | $96 |
| ECR | 2 repos, ~10 GB storage | $1 |
| Secrets Manager | 7 secrets + API calls | $3 |
| CloudWatch Logs | ~30 GB/month ingestion | $15 |
| CloudWatch Alarms | 8 alarms + dashboards | $5 |
| VPC Endpoints (Interface) | 5 endpoints × 2 AZs × 730h | $72 |
| Route 53 | 1 hosted zone + health checks | $3.50 |
| MongoDB Atlas M30 | (billed by Atlas, not AWS) | ~$350 (with DR node) |
| **Prod Total (excl. Atlas)** | | **~$400/month** |

### Cost Optimization Notes

1. **VPC Endpoints offset NAT GW cost**: Interface Endpoints ($0.01/hour/AZ) eliminate NAT GW data processing charges ($0.045/GB) for ECR, Secrets Manager, CloudWatch, and STS traffic. Break-even at ~10 GB/month of such traffic.
2. **agent-engine min=1 in dev**: Saving 1 task × 2vCPU/4GB saves ~$47/month vs min=2.
3. **Single NAT GW in dev**: Saves ~$32/month vs 2 NAT GWs. Accept the AZ-dependency risk in non-prod.
4. **Fargate Spot for agent-engine**: If workloads are interruption-tolerant (LLM calls can be retried), Fargate Spot reduces compute cost by ~70%. Not recommended for platform-app (user-facing).
5. **S3 + CloudFront for MFEs**: Effectively $0–$5/month for typical traffic (vs EC2-based hosting).
