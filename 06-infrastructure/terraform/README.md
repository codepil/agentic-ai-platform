# Agentic AI Platform — Terraform Infrastructure

This directory contains all Terraform code for the Agentic AI Platform. The code is organised into reusable modules and two environment roots (`dev` and `prod`). All environments share the same module set; differences in topology, scale, and cost are controlled entirely by variable values.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [First-time Setup](#2-first-time-setup)
3. [Environment Setup Order](#3-environment-setup-order)
4. [Deploy Commands](#4-deploy-commands)
5. [Populating Secrets](#5-populating-secrets)
6. [Building and Pushing Docker Images](#6-building-and-pushing-docker-images)
7. [Atlas Provider Authentication](#7-atlas-provider-authentication)
8. [Module Dependency Graph](#8-module-dependency-graph)
9. [Common Operations](#9-common-operations)

---

## 1. Prerequisites

Install and configure the following tools before running any Terraform commands.

| Tool | Minimum version | Install |
|---|---|---|
| [Terraform](https://developer.hashicorp.com/terraform/install) | >= 1.6 | `brew install terraform` |
| [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) | v2 | `brew install awscli` |
| [Atlas CLI](https://www.mongodb.com/docs/atlas/cli/stable/install-atlas-cli/) | >= 1.14 | `brew install mongodb-atlas-cli` |
| [mongosh](https://www.mongodb.com/docs/mongodb-shell/install/) | >= 2.0 | `brew install mongosh` |
| [Docker](https://docs.docker.com/get-docker/) | >= 24 | Desktop installer |

**AWS credentials** must be configured in your shell before running any command:

```bash
aws configure
# or
export AWS_PROFILE=your-profile
aws sts get-caller-identity   # verify
```

---

## 2. First-time Setup

### 2a. Create the S3 State Bucket

Terraform state is stored remotely in S3 with server-side encryption. Create the bucket once per AWS account (shared across environments via different state keys).

```bash
BUCKET_NAME="your-terraform-state-bucket"   # must be globally unique
AWS_REGION="us-east-1"

aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"

# Enable versioning so you can recover from accidental state deletions
aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms"
      }
    }]
  }'

# Block all public access
aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 2b. Create the DynamoDB Lock Table

State locking prevents concurrent applies from corrupting state.

```bash
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 2c. Enable the S3 Backend

Edit `environments/dev/versions.tf` (and `environments/prod/versions.tf`) and uncomment the `backend "s3"` block, substituting your bucket name:

```hcl
backend "s3" {
  bucket         = "your-terraform-state-bucket"
  key            = "agentic-ai-platform/dev/terraform.tfstate"
  region         = "us-east-1"
  encrypt        = true
  dynamodb_table = "terraform-locks"
}
```

### 2d. Initialise Terraform

Run `init` from inside the environment directory you want to work with:

```bash
cd environments/dev
terraform init
```

If you updated the backend config after a previous `init`, add `-reconfigure`:

```bash
terraform init -reconfigure
```

---

## 3. Environment Setup Order

Some modules depend on outputs from others. Apply them in this order to avoid dependency errors:

```
1. secrets     — Creates Secrets Manager placeholders (ARNs needed by later modules)
2. ecr         — Creates ECR repositories (image URIs needed by ECS)
3. vpc         — VPC, subnets, route tables, NAT Gateway
4. alb         — ALB, target groups, listeners (depends on VPC subnets)
5. ecs         — ECS cluster, task definitions, services (depends on ALB, VPC, Secrets)
6. mongodb     — Atlas project, cluster, PrivateLink (depends on VPC subnets/CIDR)
7. monitoring  — CloudWatch dashboard, alarms, SNS (depends on ALB ARN, ECS names)
```

When running `terraform apply` at the environment root (`environments/dev`), Terraform resolves the dependency graph automatically. However, on first deploy you may need to apply `secrets` and `ecr` first so you can push images before ECS is created.

---

## 4. Deploy Commands

### Dev

```bash
cd environments/dev

# 1. Set sensitive variables — never put these in tfvars
export TF_VAR_atlas_org_id="your-atlas-org-id"
export TF_VAR_mongo_password_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:..."
export TF_VAR_acm_certificate_arn="arn:aws:acm:us-east-1:123456789012:certificate/..."
export MONGODB_ATLAS_PUBLIC_KEY="your-atlas-public-key"
export MONGODB_ATLAS_PRIVATE_KEY="your-atlas-private-key"

# 2. Initialise (first time only, or after provider/backend changes)
terraform init

# 3. Preview changes
terraform plan -out=dev.tfplan

# 4. Apply
terraform apply dev.tfplan

# 5. Verify outputs
terraform output
```

### Prod

```bash
cd environments/prod

# 1. Set sensitive variables
export TF_VAR_atlas_org_id="your-atlas-org-id"
export TF_VAR_mongo_password_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:..."
export TF_VAR_acm_certificate_arn="arn:aws:acm:us-east-1:123456789012:certificate/..."
export MONGODB_ATLAS_PUBLIC_KEY="your-atlas-public-key"
export MONGODB_ATLAS_PRIVATE_KEY="your-atlas-private-key"

# 2. Initialise
terraform init

# 3. Preview changes — ALWAYS review the plan before applying to prod
terraform plan -out=prod.tfplan

# 4. Apply — requires explicit approval in your CI/CD pipeline
terraform apply prod.tfplan

# 5. Verify outputs
terraform output
```

> **Prod apply policy**: Changes to production should only be applied through a CI/CD pipeline (e.g., GitHub Actions) after a pull-request review and approval. Never run `terraform apply` directly against prod from a local machine.

---

## 5. Populating Secrets

The `secrets` module creates Secrets Manager placeholders with empty values. Populate each secret after the first `terraform apply`:

```bash
# MongoDB application user password
aws secretsmanager put-secret-value \
  --secret-id "agentic-ai-platform/dev/mongo-password" \
  --secret-string "$(openssl rand -base64 32)"

# MongoDB connection string (constructed after Atlas cluster is provisioned)
MONGO_CONN=$(terraform -chdir=environments/dev output -raw mongodb_connection_strings | jq -r '.private_srv')
aws secretsmanager put-secret-value \
  --secret-id "agentic-ai-platform/dev/mongo-connection-string" \
  --secret-string "$MONGO_CONN"

# OpenAI API key (agent-engine)
aws secretsmanager put-secret-value \
  --secret-id "agentic-ai-platform/dev/openai-api-key" \
  --secret-string "sk-..."

# Platform app JWT signing secret
aws secretsmanager put-secret-value \
  --secret-id "agentic-ai-platform/dev/jwt-secret" \
  --secret-string "$(openssl rand -hex 32)"
```

Repeat the above for the `prod` environment, substituting `dev` with `prod` in the secret IDs.

---

## 6. Building and Pushing Docker Images

### ECR Login

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-east-1"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS \
      --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
```

### Build and Push — platform-app (Java / Spring Boot)

```bash
ECR_PLATFORM_APP="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/platform-app"
IMAGE_TAG="$(git rev-parse --short HEAD)"  # use git SHA for traceability

docker build \
  --platform linux/amd64 \
  -t "${ECR_PLATFORM_APP}:${IMAGE_TAG}" \
  -t "${ECR_PLATFORM_APP}:latest" \
  -f services/platform-app/Dockerfile \
  services/platform-app/

docker push "${ECR_PLATFORM_APP}:${IMAGE_TAG}"
docker push "${ECR_PLATFORM_APP}:latest"

echo "Pushed: ${ECR_PLATFORM_APP}:${IMAGE_TAG}"
```

### Build and Push — agent-engine (Python)

```bash
ECR_AGENT_ENGINE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/agent-engine"
IMAGE_TAG="$(git rev-parse --short HEAD)"

docker build \
  --platform linux/amd64 \
  -t "${ECR_AGENT_ENGINE}:${IMAGE_TAG}" \
  -t "${ECR_AGENT_ENGINE}:latest" \
  -f services/agent-engine/Dockerfile \
  services/agent-engine/

docker push "${ECR_AGENT_ENGINE}:${IMAGE_TAG}"
docker push "${ECR_AGENT_ENGINE}:latest"

echo "Pushed: ${ECR_AGENT_ENGINE}:${IMAGE_TAG}"
```

> In production, always update `terraform.tfvars` with the pinned `IMAGE_TAG` (not `latest`) before running `terraform apply`, so deployments are reproducible and rollbacks are straightforward.

---

## 7. Atlas Provider Authentication

The MongoDB Atlas Terraform provider reads credentials from environment variables. Set these in your shell (or CI/CD secrets store) before running any Terraform command that touches the `mongodb` module:

```bash
# Create an API key in the Atlas UI: Organization > Access Manager > API Keys
# Grant the key "Organization Project Creator" and "Project Owner" roles.

export MONGODB_ATLAS_PUBLIC_KEY="abcdefgh"        # Atlas API public key
export MONGODB_ATLAS_PRIVATE_KEY="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

Verify the credentials work using the Atlas CLI:

```bash
atlas auth login          # interactive browser login (optional)
atlas projects list       # should list your Atlas projects
```

---

## 8. Module Dependency Graph

The following diagram shows how modules depend on each other at the environment root level. Arrows indicate "depends on".

```
environments/dev (or prod)
│
├── module.secrets
│     └── (no upstream dependencies)
│
├── module.ecr
│     └── (no upstream dependencies)
│
├── module.vpc
│     └── (no upstream dependencies)
│
├── module.alb
│     └── module.vpc  (vpc_id, public_subnet_ids)
│
├── module.ecs
│     ├── module.vpc     (vpc_id, private_subnet_ids)
│     ├── module.alb     (security_group_id, target_group_arn)
│     └── module.secrets (secret_arns, mongo_connection_string_arn)
│
├── module.mongodb
│     └── module.vpc  (vpc_id, isolated_subnet_ids, vpc_cidr)
│
└── module.monitoring
      ├── module.alb  (alb_arn_suffix)
      └── module.ecs  (cluster_name, service names, desired counts)
```

**Build order** (Terraform resolves this automatically, shown for clarity):

```
secrets → ecr → vpc → alb → ecs
                    ↘ mongodb
                    ↘ monitoring (after alb + ecs)
```

---

## 9. Common Operations

### Rolling Deploy (update ECS service with new image)

After pushing a new Docker image, trigger a rolling replacement of ECS tasks:

```bash
ENV="dev"   # or prod
CLUSTER="platform-${ENV}"

# Force a new deployment — ECS will pull the latest image tag and replace tasks
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "platform-app-${ENV}" \
  --force-new-deployment \
  --region us-east-1

# Watch the deployment progress
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "platform-app-${ENV}" \
  --region us-east-1

echo "Deployment complete"
```

To deploy a specific image tag via Terraform instead (recommended for prod):

```bash
# 1. Update terraform.tfvars with the new image tag
# platform_app_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/platform-app:abc1234"

# 2. Plan and apply
cd environments/prod
terraform plan -out=prod.tfplan
terraform apply prod.tfplan
```

### Scale an ECS Service

Scale up or down without a full `terraform apply` (useful for incident response):

```bash
ENV="prod"
CLUSTER="platform-${ENV}"
SERVICE="agent-engine-${ENV}"
DESIRED_COUNT=4

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --desired-count "$DESIRED_COUNT" \
  --region us-east-1

echo "Scaled $SERVICE to $DESIRED_COUNT tasks"
```

> Remember to update `terraform.tfvars` with the new `desired_count` value afterwards so Terraform does not revert the change on the next apply.

### Destroy an Environment

```bash
# Dev only — prod has deletion_protection=true on the ALB
cd environments/dev

# Preview what will be destroyed
terraform plan -destroy -out=destroy.tfplan

# Destroy (irreversible — all data including the MongoDB Atlas cluster will be deleted)
terraform apply destroy.tfplan
```

> For prod, you must first disable deletion protection on the ALB and set `deletion_protection = false` in `terraform.tfvars`, then run `terraform apply` to update the ALB, and only then run `terraform destroy`. This is intentional friction to prevent accidental production deletions.

### Inspect MongoDB Connection String

```bash
cd environments/dev
terraform output -json mongodb_connection_strings | jq .
```

### View CloudWatch Dashboard

```bash
cd environments/dev
terraform output monitoring_dashboard_url
# Opens the URL in your browser
open "$(terraform output -raw monitoring_dashboard_url)"
```

### Check Terraform State

```bash
# List all resources tracked in state
terraform state list

# Inspect a specific resource
terraform state show module.mongodb.mongodbatlas_cluster.this

# Remove a resource from state without destroying it (use with caution)
# terraform state rm <resource_address>
```
