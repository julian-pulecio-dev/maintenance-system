# Maintenance System

A multi-tenant REST API for managing industrial asset maintenance and work orders. Built with Django REST Framework, backed by PostgreSQL, and deployed on AWS ECS with an event-driven notification pipeline powered by SNS, SQS, and Lambda.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Local Setup](#local-setup)
4. [Environment Variables](#environment-variables)
5. [Running Tests & Linting](#running-tests--linting)
6. [Teardown](#teardown)
7. [Architecture Overview](#architecture-overview)
8. [Multi-Tenancy](#multi-tenancy)
9. [Authentication & Authorization](#authentication--authorization)
10. [Domain Models](#domain-models)
11. [Asset Lifecycle](#asset-lifecycle)
12. [Work Order Lifecycle](#work-order-lifecycle)
13. [Event-Driven Architecture](#event-driven-architecture)
14. [Background Workers](#background-workers)
15. [Lambda Notifiers](#lambda-notifiers)
16. [API Reference](#api-reference)
17. [Infrastructure (Terraform)](#infrastructure-terraform)
18. [Infrastructure cost estimate](#infrastructure-cost-estimate)
19. [CI/CD Pipelines](#cicd-pipelines)
19. [Design Decisions](#design-decisions)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.9 |
| Framework | Django 4.1 + Django REST Framework 3.13 |
| Database | PostgreSQL 15 |
| Auth | JWT via `djangorestframework-simplejwt` |
| API Docs | `drf-spectacular` (OpenAPI 3 / Swagger UI) |
| CORS | `django-cors-headers` |
| Email | AWS SES (prod) / SMTP or console (local) |
| AWS SDK | `boto3` |
| Messaging | AWS SNS + SQS |
| Serverless | AWS Lambda (Python 3.9) |
| Idempotency Store | AWS DynamoDB |
| Containerization | Docker + Docker Compose |
| Infrastructure | Terraform |
| Compute | AWS ECS Fargate |
| CI | GitHub Actions |
| CD | GitHub Actions → Docker Hub → ECS |
| Linter | flake8 (max-line-length 88) |

---

## Project Structure

```
maintenance-system/
├── app/                                   # Django project root
│   ├── app/                               # Core project package
│   │   ├── settings/
│   │   │   ├── base.py                    # Shared settings (DB, auth, CORS, email)
│   │   │   ├── local.py                   # Local overrides (allow-all CORS)
│   │   │   └── test.py                    # Test overrides (in-memory email)
│   │   ├── urls.py                        # Root URL router
│   │   ├── wsgi.py
│   │   └── management/commands/
│   │       ├── poll_outbox.py             # Long-running outbox dispatcher worker
│   │       └── check_maintenance.py       # Periodic maintenance due-date checker
│   ├── user/                              # Authentication & user management
│   │   ├── models.py                      # User (UUID PK, tenant-scoped), PasswordResetToken
│   │   ├── auth/backends.py               # TenantAwareBackend (email + tenant login)
│   │   ├── serializers.py                 # TenantAwareTokenSerializer
│   │   ├── views.py                       # Create, me, list, forgot/reset password
│   │   └── urls.py
│   ├── tenant/                            # Multi-tenancy plumbing
│   │   ├── models.py                      # Tenant (UUID PK, name)
│   │   ├── middleware.py                  # Attaches request.tenant from X-Tenant-ID header
│   │   ├── permissions.py                 # TenantHeaderRequired, IsStaffOrSuperuser, IsStaffOrAssetSupervisor, IsStaffOrWorkOrderAssignee
│   │   ├── views.py                       # Admin-only CRUD
│   │   └── urls.py
│   ├── asset/                             # Asset management
│   │   ├── models.py                      # Asset, AssetQuerySet, soft-delete, state helpers
│   │   ├── schemas.py                     # JSONField metadata validation
│   │   ├── serializers.py                 # AssetSerializer (computed fields)
│   │   ├── services.py                    # AssetService (atomic mutations + event publishing)
│   │   ├── views.py                       # List/create, detail, restore, supervisor endpoints
│   │   └── urls.py
│   ├── asset_type/                        # Asset classification
│   │   ├── models.py                      # AssetType (tenant-scoped, unique name)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   ├── work_order/                        # Work order management
│   │   ├── models.py                      # WorkOrder, state machine, soft-delete, note appending
│   │   ├── serializers.py                 # WorkOrderSerializer (nested detail fields)
│   │   ├── services.py                    # WorkOrderService (atomic mutations + event publishing)
│   │   ├── views.py                       # CRUD + action endpoints (start/hold/complete/cancel/assign/restore)
│   │   └── urls.py
│   ├── work_order_type/                   # Work order classification
│   │   ├── models.py                      # WorkOrderType (tenant-scoped, unique name)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   └── outbox/                            # Transactional outbox
│       ├── models.py                      # OutboxEvent (status, retries, idempotency_key)
│       ├── serializers.py
│       ├── views.py                       # Read-only inspection endpoints
│       └── urls.py
├── lambdas/                               # AWS Lambda event consumers
│   ├── notifier_base.py                  # Abstract EmailNotifierHandler (idempotency, SES, SQS)
│   ├── asset_email_notifier/
│   │   └── handler.py                    # Asset CRUD email notifier
│   ├── asset_maintenance_email_notifier/
│   │   └── handler.py                    # Maintenance upcoming/overdue email notifier
│   ├── asset_sensor_alert_notifier/
│   │   └── handler.py                    # Sensor alert email notifier (supervisor)
│   ├── work_order_email_notifier/
│   │   └── handler.py                    # Work order state-change email notifier
│   ├── work_order_due_date_notifier/
│   │   └── handler.py                    # Work order due-date upcoming/overdue email notifier
│   └── pyrightconfig.json                # IDE path config
├── terraform/                             # Infrastructure as Code
│   ├── main.tf                           # Root module (wires all submodules)
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars
│   ├── backend.tf / backend-prod.hcl     # S3 remote state backend
│   ├── scripts/                          # Operational scripts (require AWS CLI + Terraform)
│   │   ├── create_superuser.sh           # Create a global superuser on a running ECS task (bash)
│   │   ├── create_superuser.ps1          # Create a global superuser on a running ECS task (PowerShell)
│   │   ├── teardown_infra.sh             # Drain ECS tasks before terraform destroy (bash)
│   │   └── teardown_infra.ps1            # Drain ECS tasks before terraform destroy (PowerShell)
│   └── modules/
│       ├── vpc/                          # VPC, subnets, security groups
│       ├── rds/                          # PostgreSQL RDS instance
│       ├── ecs_django_core/              # Main API: ECS cluster, ALB, task def, migration task
│       ├── ecs_outbox_observer/          # Outbox worker: ECS cluster + service
│       ├── ecs_maintenance_checker/      # Maintenance checker: ECS cluster + service
│       ├── sns/                          # SNS topic for domain events
│       ├── sqs/                          # SQS queue for downstream processing results
│       └── sns_subscriber/              # Lambda + SNS subscription + IAM
├── .github/workflows/
│   ├── checks.yml                        # CI: test + lint on every push
│   └── deploy.yaml                       # CD: build → migrate → deploy on push to master
├── docker-compose.yml                    # Local development environment
├── docker-compose.ci.yml                 # CI environment
├── Dockerfile                            # Multi-stage image (prod / dev via ARG DEV=true)
├── requirements.txt                      # Production dependencies
├── requirements.dev.txt                  # Dev/test dependencies (flake8, black)
└── .flake8                               # Linter config
```

---

## Local Setup

### Prerequisites

- Docker Desktop
- Docker Compose v2

### 1. Clone the repository

```bash
git clone <repo-url>
cd maintenance-system
```

### 2. Create the local environment file

Create `.env.local` at the project root (alongside `docker-compose.yml`):

```env
POSTGRES_USER=maintenance_system_user
POSTGRES_PASSWORD=maintenance_system_password
POSTGRES_DB=maintenance_system_db
DB_USER=maintenance_system_user
DB_PASSWORD=maintenance_system_password
DB_NAME=maintenance_system_db
DB_HOST=app-db
DB_PORT=5432
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=you@example.com
ALLOWED_HOSTS=*
```

### 3. Build and start

```bash
docker compose up --build
```

This will:
1. Build the Django image with `DEV=true` (installs dev dependencies).
2. Start PostgreSQL 15 and wait for it to be healthy.
3. Run `python manage.py migrate` automatically.
4. Start the Django development server on `http://localhost:8000`.

### 4. Create a superuser (first time only)

**Local:**

```bash
docker compose run --rm app python manage.py createsuperuser
```

**Production (ECS):** use the `create_superuser` script, which discovers the running ECS cluster and task automatically and executes the management command inside the container via `aws ecs execute-command`.

```bash
# bash
./terraform/scripts/create_superuser.sh -e admin@example.com -p secret123 -n "Admin"

# PowerShell
.\terraform\scripts\create_superuser.ps1 -Email admin@example.com -Password secret123 -Name "Admin"
```

If multiple clusters or services are found the script will prompt you to select one.

Superusers are not tenant-scoped — they can access admin-only endpoints without the `X-Tenant-ID` header.

### 5. Create a tenant and a regular user

Use the interactive Swagger UI at `http://localhost:8000/api/schema/swagger/`.

```
# Authenticate as superuser, then:
POST /api/tenant/          → create a tenant, copy the returned id
POST /api/user/create/     → create a user (requires X-Tenant-ID header)
```

### 6. Obtain a JWT token

```http
POST /api/token/
Content-Type: application/json
X-Tenant-ID: <tenant-uuid>     ← required for regular users, omit for superusers

{
  "email": "you@example.com",
  "password": "yourpassword"
}
```

Use the returned `access` token as `Authorization: Bearer <token>` in subsequent requests.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_NAME` | Yes | — | PostgreSQL database name |
| `DB_USER` | Yes | — | PostgreSQL username |
| `DB_PASSWORD` | Yes | — | PostgreSQL password |
| `DB_HOST` | Yes | — | PostgreSQL host |
| `DB_PORT` | Yes | — | PostgreSQL port |
| `EMAIL_BACKEND` | No | `smtp.EmailBackend` | Django email backend class |
| `EMAIL_HOST` | No | `smtp.gmail.com` | SMTP host |
| `EMAIL_PORT` | No | `587` | SMTP port |
| `EMAIL_USE_TLS` | No | `True` | SMTP TLS |
| `EMAIL_HOST_USER` | No | — | SMTP credentials |
| `EMAIL_HOST_PASSWORD` | No | — | SMTP credentials |
| `DEFAULT_FROM_EMAIL` | No | EMAIL_HOST_USER | From address for outgoing emails |
| `AWS_SES_REGION_NAME` | No | `us-east-1` | Region used when backend is `django_ses.SESBackend` |
| `ALLOWED_HOSTS` | No | `*` | Comma-separated list of allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | No | — | Extra comma-separated CORS origins |
| `SNS_TOPIC_ARN` | Prod only | — | SNS topic for the outbox dispatcher worker |
| `SQS_RESULTS_URL` | Prod only | — | SQS queue URL for downstream processing results |

---

## Running Tests & Linting

```bash
# Run all tests
docker compose run --rm app python manage.py test

# Run tests for a specific app
docker compose run --rm app python manage.py test work_order

# Run the linter
docker compose run --rm app flake8
```

The test settings (`app.settings.test`) switch to an in-memory email backend so no real emails are sent during tests.

---

## Teardown

```bash
# Stop containers (keeps database volume)
docker compose down

# Stop containers AND destroy the database volume
docker compose down -v
```

To tear down the production AWS infrastructure, first drain all ECS tasks with the teardown script, then run `terraform destroy`. Skipping the first step will cause `terraform destroy` to hang because the Application Auto Scaling policy on the main API service keeps replacing terminated tasks.

```bash
# bash — drain ECS tasks (Terraform already initialised)
./terraform/scripts/teardown_infra.sh

# bash — drain ECS tasks + init Terraform in one step
./terraform/scripts/teardown_infra.sh --backend backend-prod.hcl

# PowerShell — drain ECS tasks (Terraform already initialised)
.\terraform\scripts\teardown_infra.ps1

# PowerShell — drain ECS tasks + init Terraform in one step
.\terraform\scripts\teardown_infra.ps1 -Backend backend-prod.hcl
```

Once all tasks are stopped:

```bash
cd terraform
terraform destroy
```

> **Warning:** `terraform destroy` removes RDS, ECS clusters, SNS topics, SQS queues, Lambda functions, and the VPC. This is irreversible — back up the database first.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Client (Browser / Mobile)                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTPS  (JWT + X-Tenant-ID)
                               ▼
                    ┌──────────────────────┐
                    │  Application Load     │
                    │  Balancer (ALB)       │
                    └──────────┬───────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │  ECS Fargate — Django API       │  ← ecs_django_core
              │  (N tasks, horizontally scaled) │
              └────────────────┬───────────────┘
                               │ write
                               ▼
              ┌────────────────────────────────┐
              │  PostgreSQL 15 (RDS)            │
              │  ┌──────────────────────────┐  │
              │  │  outbox_events table      │  │  ← transactional outbox
              │  └──────────────────────────┘  │
              └────────────────┬───────────────┘
                               │ poll (every 60 s)
                               ▼
              ┌────────────────────────────────┐
              │  ECS Fargate — Outbox Worker    │  ← ecs_outbox_observer
              │  (poll_outbox management cmd)   │
              └────────────────┬───────────────┘
                               │ publish
                               ▼
              ┌────────────────────────────────┐
              │  SNS Topic (domain events)      │
              └───┬────────────┬───────────────┘
          subscribe        subscribe         subscribe
                  │            │                 │
                  ▼            ▼                 ▼
          ┌──────────┐  ┌──────────┐  ┌──────────────────────┐
          │ SQS+Λ    │  │ SQS+Λ    │  │ SQS+Λ                │
          │ asset    │  │ work_    │  │ asset_maintenance     │
          │ email    │  │ order    │  │ email notifier        │
          │ notifier │  │ email    │  └──────────────────────┘
          └──────────┘  │ notifier │
                        └──────────┘
                            │ (all lambdas report results)
                            ▼
              ┌────────────────────────────────┐
              │  SQS Results Queue              │
              └────────────────┬───────────────┘
                               │ poll (every 10 s)
                               ▼
              ┌────────────────────────────────┐
              │  Outbox Worker (results thread) │  ← marks events SENT / FAILED
              └────────────────────────────────┘

              ┌────────────────────────────────┐
              │  ECS Fargate — Maint. Checker   │  ← ecs_maintenance_checker
              │  (check_maintenance cmd)        │  detects overdue assets
              └────────────────────────────────┘
```

---

## Multi-Tenancy

Every resource (Asset, WorkOrder, AssetType, WorkOrderType, User) belongs to a `Tenant`. The system enforces tenant isolation at three layers:

### 1. Header extraction (Middleware)

`tenant/middleware.py` reads the `X-Tenant-ID` header on every request and attaches the resolved `Tenant` instance to `request.tenant`. If the header is missing or the UUID is invalid, the middleware sets `request.tenant = None`.

### 2. Permission enforcement

`TenantHeaderRequired` is a DRF permission class applied to every view (except `/api/token/` and tenant admin endpoints). It rejects requests where `request.tenant is None` with `403 Forbidden`.

### 3. Query-level isolation

Every queryset in views is filtered with `.for_tenant(request.tenant)` before any data is returned or modified. Cross-tenant access returns `404 Not Found` rather than `403`, to avoid leaking resource existence.

**Superusers** do not require the `X-Tenant-ID` header and are authenticated via `IsAdminUser` on admin-only routes.

---

## Authentication & Authorization

### JWT flow

1. `POST /api/token/` with `email` + `password` (+ `X-Tenant-ID` for regular users) → returns `access` and `refresh` tokens.
2. All subsequent requests include `Authorization: Bearer <access>`.
3. Tokens are refreshed via `POST /api/token/refresh/`.

### Tenant-aware login

`TenantAwareBackend` ensures that two users with the same email address in different tenants are treated as separate identities. Login validates both credentials and tenant membership.

### Password reset flow

1. `POST /api/user/forgot-password/` with `email` + `X-Tenant-ID` → creates a `PasswordResetToken` (UUID, 1-hour expiry) and sends an email with the token.
2. `POST /api/user/reset-password/` with `token` + `password` → validates the token, updates the password, marks the token used, and invalidates all other pending tokens for that user.

### Roles & Permissions

The system has three levels of access within a tenant:

| Role | How to obtain | `is_staff` | `is_superuser` |
|---|---|---|---|
| **Regular user** | Created via `POST /api/user/create/` | `false` | `false` |
| **Staff user** | Promoted via `POST /api/user/{id}/promote/` | `true` | `false` |
| **Superuser** | Created via `manage.py createsuperuser` or the ECS script | `false` | `true` |

Staff users and superusers are treated identically for authorization purposes throughout the API. The current user's `is_staff` flag is included in the `GET /api/user/me` response.

#### Permission matrix

| Resource / Action | Regular user | Staff / Superuser |
|---|---|---|
| **Asset Types** — all endpoints | ✗ | ✓ |
| **Work Order Types** — all endpoints | ✗ | ✓ |
| **Assets** — list, retrieve | ✓ | ✓ |
| **Assets** — create, delete, restore, assign supervisor | ✗ | ✓ |
| **Assets** — update (`PATCH`) | ✓ only if `supervisor` | ✓ |
| **Assets** — sensor alert | ✓ only if `supervisor` | ✓ |
| **Work Orders** — list, retrieve | ✓ | ✓ |
| **Work Orders** — create, delete, restore, assign | ✗ | ✓ |
| **Work Orders** — update (`PATCH`) | ✓ only if `assigned_to` | ✓ |
| **Work Orders** — start, hold, complete, cancel | ✓ only if `assigned_to` | ✓ |
| **Users** — promote to staff | ✗ | ✓ |

Object-level checks (supervisor / assigned_to) are enforced by DRF permission classes and applied after the tenant isolation filter, so a user cannot manipulate resources belonging to another tenant even if they happen to be the supervisor or assignee.

---

## Domain Models

### Tenant

```
Tenant
  id            UUID (PK)
  name          CharField
  created_at    DateTimeField (auto)
  updated_at    DateTimeField (auto)
```

### User

```
User
  id            UUID (PK)
  tenant        FK → Tenant (null for superusers)
  email         CharField  ← USERNAME_FIELD
  name          CharField
  is_active     BooleanField
  is_staff      BooleanField
  created_at    DateTimeField (auto)
  updated_at    DateTimeField (auto)

Constraint: unique(tenant, email) for non-superusers
```

### AssetType

```
AssetType
  id            UUID (PK)
  tenant        FK → Tenant
  name          CharField
  description   TextField (optional)
  created_at / updated_at

Constraint: unique(tenant, name)
```

### Asset

```
Asset
  id                                    UUID (PK)
  tenant                                FK → Tenant
  supervisor                            FK → User
  asset_type                            FK → AssetType
  serial_number                         CharField  ← unique per tenant (active assets only)
  name                                  CharField
  location                              CharField
  installation_date                     DateField
  status                                ACTIVE | INACTIVE | MAINTENANCE | FAILED
  description                           TextField (optional)
  last_maintenance_date                 DateField (optional)
  recommended_maintenance_interval_days PositiveIntegerField (> 0)
  metadata                              JSONField
  created_at / updated_at
  deleted_at                            DateTimeField (null = not deleted)

Computed (not stored):
  next_maintenance_date  = last_maintenance_date + interval_days
  is_maintenance_overdue = today > next_maintenance_date
  is_deleted             = deleted_at is not None
  is_operational         = not deleted and status == ACTIVE
```

### WorkOrderType

```
WorkOrderType
  id            UUID (PK)
  tenant        FK → Tenant
  name          CharField
  description   TextField (optional)
  created_at / updated_at

Constraint: unique(tenant, name)
```

### WorkOrder

```
WorkOrder
  id               UUID (PK)
  tenant           FK → Tenant
  asset            FK → Asset
  work_order_type  FK → WorkOrderType
  assigned_to      FK → User  ← required
  created_by       FK → User  ← set from request.user on create
  title            CharField
  description      TextField (optional)
  status           OPEN | IN_PROGRESS | ON_HOLD | COMPLETED | CANCELLED
  priority         LOW | MEDIUM | HIGH | CRITICAL
  scheduled_date   DateField (optional)
  due_date         DateField (optional)
  completed_date   DateField (optional, set automatically on complete)
  notes            TextField (optional, append-only via action endpoints)
  estimated_hours  DecimalField(6,1) (optional, required on complete)
  created_at / updated_at
  deleted_at       DateTimeField (null = not deleted)

Computed:
  is_deleted  = deleted_at is not None
  is_active   = not deleted and status in {OPEN, IN_PROGRESS, ON_HOLD}
  is_overdue  = is_active and due_date < today
```

### OutboxEvent

```
OutboxEvent
  id               UUID (PK)
  tenant           FK → Tenant
  event_type       CharField  (e.g. "work_order.completed")
  aggregate_type   CharField  (e.g. "work_order")
  aggregate_id     UUIDField
  payload          JSONField  (full snapshot of the resource at event time)
  status           PENDING | PROCESSING | SENT | FAILED
  retry_count      PositiveIntegerField (max 3)
  event_version    PositiveIntegerField
  idempotency_key  CharField (nullable, unique per tenant)
  source_service   CharField
  error_message    TextField (optional)
  created_at
  processed_at     DateTimeField (optional)
  last_attempted_at DateTimeField (optional)
```

---

## Asset Lifecycle

```
         ┌─────────┐
         │ Created │  POST /api/asset/
         └────┬────┘
              │  status = ACTIVE (default)
              ▼
         ┌─────────┐
    ┌────│  ACTIVE │────────────────────────────────────────────────────┐
    │    └────┬────┘  PATCH /api/asset/{id}/                            │
    │         │ (status can be freely changed to any value via PATCH)   │
    │         │                                                         │
    │         ├──────────────┬──────────────────┐                       │
    │         ▼              ▼                   ▼                      │
    │    ┌──────────┐  ┌─────────────┐  ┌────────┐                      │
    │    │ INACTIVE │  │ MAINTENANCE │  │ FAILED │                      │
    │    └──────────┘  └─────────────┘  └────────┘                      │
    │                                                                   │
    │  DELETE /api/asset/{id}/  →  soft delete (sets deleted_at)        │
    │         │                                                         │
    │         ▼                                                         │
    │    ┌─────────┐                                                    │
    └───►│ DELETED │  POST /api/asset/{id}/restore/  →  ACTIVE ─────────┘
         └─────────┘
```

**Key behaviors:**

- **Soft delete:** `deleted_at` is set instead of issuing a `DELETE`. Deleted assets are hidden from all list/detail views but remain in the database and can be restored.
- **Serial number uniqueness:** The unique constraint on `(tenant, serial_number)` uses a partial index (`WHERE deleted_at IS NULL`), so a deleted asset's serial number does not block other active assets. Restoring a deleted asset whose serial number is now taken by another active asset raises a `ValidationError`.
- **last_maintenance_date:** Defaults to `installation_date` on creation if not provided. Updated automatically each time a related work order is completed.
- **Maintenance tracking:** The `check_maintenance` worker runs periodically and detects assets where `next_maintenance_date` is within 7 days (publishes `asset.maintenance.upcoming`) or already past (publishes `asset.maintenance.overdue`). Both events trigger emails to the asset's supervisor.
- **Supervisor assignment:** Must belong to the same tenant. Changeable via `POST /api/asset/{id}/supervisor/` or `PATCH /api/asset/{id}/`.
- **Sensor alerts:** Any external system (IoT gateway, monitoring agent) can call `POST /api/asset/{id}/sensor-alert/` to signal that something is wrong with the asset. The endpoint publishes an `asset.sensor_alert` outbox event, which triggers an email to the asset's supervisor via the `asset_sensor_alert_notifier` Lambda. No sensor model exists — alerts are stateless signals carrying an optional `message` and `severity` (`warning` or `critical`).

---

## Work Order Lifecycle

### State machine

```
                        ┌────────────────────────────┐
                        │             OPEN            │◄──────────────┐
                        └────┬──────────┬─────────────┘               │
                             │          │                             │
              start (/start) │          │ hold (/hold)                │
                             ▼          ▼                             │
              ┌─────────────────┐  ┌──────────┐                       │
              │   IN_PROGRESS   │  │  ON_HOLD │◄──────────────────────┤
              └───┬─────────────┘  └──────────┘                       │
                  │    │               │  start (/start)              │
        complete  │    │ hold (/hold)  │                              │
        (/complete│    └──────────────►                               │
                  │                                                   │
                  ▼                                                   │
              ┌──────────┐                                            │
              │ COMPLETED│  (terminal)                                │
              └──────────┘                                            │
                                                                      │
              cancel (/cancel) available from OPEN, IN_PROGRESS, ON_HOLD
                  │                                                   │
                  ▼                                                   │
              ┌──────────┐                                            │
              │ CANCELLED│  (terminal)                                │
              └──────────┘                                            │
                                                                      │
    DELETE /api/work-order/{id}/  →  soft delete (sets deleted_at)    │
    POST   /api/work-order/{id}/restore/ → restores → OPEN ───────────┘
```

**Valid transitions:**

| From | Allowed next states |
|---|---|
| OPEN | IN_PROGRESS, ON_HOLD, CANCELLED |
| IN_PROGRESS | ON_HOLD, COMPLETED, CANCELLED |
| ON_HOLD | IN_PROGRESS, CANCELLED |
| COMPLETED | — (terminal) |
| CANCELLED | — (terminal) |

An attempt to transition outside these rules returns `409 Conflict`.

### Action endpoints

All action endpoints share a common pattern:

1. **Fetch** — work order is retrieved filtered by tenant (`404` if not found or deleted).
2. **Validate transition** — returns `409 Conflict` if the current status does not allow the requested action.
3. **Require `notes`** — every action requires a non-empty `notes` field (`400 Bad Request` if missing).
4. **Execute** — calls the corresponding `WorkOrderService` method inside `@transaction.atomic` with `select_for_update()` to prevent concurrent modification.
5. **Append note** — the `notes` text is prepended to the existing `notes` field with a UTC timestamp:

```
[2025-06-01 10:45 UTC] Technician completed replacement.
---
[2025-05-29 08:00 UTC] Parts arrived, work scheduled.
---
[2025-05-25 14:30 UTC] Waiting on spare parts.
```

### Complete endpoint specifics

`POST /api/work-order/{id}/complete/` requires both `notes` and `estimated_hours`. On success, in a single atomic transaction:
- `status` → `COMPLETED`
- `completed_date` → today (UTC)
- `estimated_hours` → saved to the work order
- `asset.last_maintenance_date` → updated to `completed_date`

### Assign endpoint specifics

`POST /api/work-order/{id}/assign/` requires `assigned_to` (user UUID) and `notes`. The target user must belong to the same tenant. Assignment is only allowed in `OPEN`, `IN_PROGRESS`, or `ON_HOLD` states — assigning a completed or cancelled work order returns `409 Conflict`.

---

## Event-Driven Architecture

The system uses the **Transactional Outbox Pattern** to guarantee that domain events are published reliably, even in the presence of partial failures.

### Why the outbox pattern?

Without it, a service could complete a database write but crash before publishing to SNS, or publish to SNS but have the database write rolled back. The outbox makes the event part of the same database transaction as the business operation, eliminating that inconsistency window.

### Full event flow

```
Step 1 — Business operation (e.g. work order completed)
  └─► WorkOrderService.complete_work_order()  @transaction.atomic
        ├─► UPDATE work_orders SET status='completed', completed_date=today
        ├─► UPDATE assets SET last_maintenance_date=today
        └─► INSERT INTO outbox_events (status='PENDING', event_type='work_order.completed', payload={...})
                                                ↑ same DB transaction

Step 2 — Outbox dispatcher (poll_outbox, every 60 s)
  └─► SELECT FOR UPDATE SKIP LOCKED FROM outbox_events WHERE status='PENDING'
        ├─► UPDATE outbox_events SET status='PROCESSING'
        └─► SNS.publish(TopicArn, Message=json, MessageAttributes={event_type, tenant_id})

Step 3 — Lambda (SNS → SQS → Lambda trigger)
  ├─► DynamoDB.get_item(event_id)  → skip if already processed
  ├─► SES.send_email(to=assigned_to.email, subject=..., body=...)
  ├─► DynamoDB.put_item(event_id, ttl=30 days)
  └─► SQS.send_message(results_queue, {event_id, status: "processed"})

Step 4 — Results processor (poll_outbox results thread, every 10 s)
  └─► SQS.receive_message(results_queue)
        ├─► OutboxEvent.mark_sent()   → status='SENT'
        └─► OutboxEvent.mark_failed() → status='FAILED' (retried up to 3 times)
```

### Event types

| Event | Trigger |
|---|---|
| `asset.created` | Asset created |
| `asset.updated` | Asset updated |
| `asset.deleted` | Asset soft-deleted |
| `asset.restored` | Asset restored |
| `asset.supervisor_assigned` | Supervisor changed |
| `asset.maintenance.upcoming` | Maintenance due within 7 days |
| `asset.maintenance.overdue` | Maintenance past due date |
| `asset.sensor_alert` | External alert signalled via `POST /api/asset/{id}/sensor-alert/` |
| `work_order.created` | Work order created |
| `work_order.updated` | Work order updated |
| `work_order.deleted` | Work order soft-deleted |
| `work_order.restored` | Work order restored |
| `work_order.assigned` | Assignee changed |
| `work_order.started` | Status → IN_PROGRESS |
| `work_order.put_on_hold` | Status → ON_HOLD |
| `work_order.completed` | Status → COMPLETED |
| `work_order.cancelled` | Status → CANCELLED |
| `work_order.due_date.upcoming` | Work order due within 7 days |
| `work_order.due_date.overdue` | Work order past due date |

### SNS message filtering

Each Lambda subscribes to the SNS topic with a **filter policy** on the `event_type` MessageAttribute, so only relevant events are routed to each Lambda — avoiding unnecessary invocations and costs.

---

## Background Workers

### poll_outbox (Outbox Dispatcher)

Deployed as a long-running ECS Fargate task (`python manage.py poll_outbox`). Runs two threads in parallel:

**Dispatcher thread** (every 60 seconds):
1. Recovers `PROCESSING` events stuck for more than 10 minutes (resets them to `PENDING`).
2. Claims up to 100 `PENDING` events using `SELECT FOR UPDATE SKIP LOCKED` — prevents multiple worker instances from processing the same event.
3. Marks them `PROCESSING`.
4. Publishes each to SNS.
5. On publish failure: calls `event.mark_failed(error)`. After 3 failures the event moves permanently to `FAILED`.

**Results thread** (every 10 seconds):
1. Long-polls the SQS results queue (up to 10 messages, 5-second wait).
2. For each message: finds the `OutboxEvent` by `event_id` (locked with `select_for_update`), marks it `SENT` or `FAILED`.
3. Deletes the SQS message after processing.

### check_maintenance (Maintenance Checker)

Deployed as a separate ECS Fargate task (`python manage.py check_maintenance`). For each operational (active, non-deleted) asset with a `last_maintenance_date`:
- If `next_maintenance_date <= today + 7 days` → publishes `asset.maintenance.upcoming`.
- If `next_maintenance_date < today` → publishes `asset.maintenance.overdue`.
- Uses an `idempotency_key` on `OutboxEvent` to prevent duplicate notifications for the same asset on the same day.

---

## Lambda Notifiers

All Lambda functions share the abstract `EmailNotifierHandler` base class (`lambdas/notifier_base.py`).

### Base class responsibilities

- **Lazy AWS clients** — SQS, SES, and DynamoDB clients are created once per Lambda cold start (class-level attributes).
- **Message unwrapping** — handles the SNS-via-SQS envelope format transparently.
- **Idempotency** — checks DynamoDB for the event ID before processing. If found, skips silently. After processing, writes the event ID with a 30-day TTL.
- **Email sending** — delegates `build_subject()` and `build_body()` to the subclass, then sends via SES.
- **Result reporting** — publishes a result message (`{event_id, status}`) to the SQS results queue after processing, regardless of success or failure.

### Concrete notifiers

| Lambda | Subscribed events | Recipient |
|---|---|---|
| `asset_email_notifier` | `asset.created`, `asset.updated`, `asset.deleted` | Asset supervisor |
| `asset_maintenance_email_notifier` | `asset.maintenance.upcoming`, `asset.maintenance.overdue` | Asset supervisor |
| `asset_sensor_alert_notifier` | `asset.sensor_alert` | Asset supervisor |
| `work_order_email_notifier` | All `work_order.*` lifecycle events | Work order `assigned_to` user |
| `work_order_due_date_notifier` | `work_order.due_date.upcoming`, `work_order.due_date.overdue` | Work order `assigned_to` user |

---

## API Reference

Interactive documentation is available at:
- **Swagger UI:** `http://localhost:8000/api/schema/swagger/`
- **ReDoc:** `http://localhost:8000/api/schema/redoc/`
- **OpenAPI schema:** `http://localhost:8000/api/schema/`

All endpoints (except token and user creation) require:
- `Authorization: Bearer <access_token>`
- `X-Tenant-ID: <tenant-uuid>`

### Endpoints summary

Role legend: `[any]` = any authenticated user · `[staff]` = staff or superuser only · `[supervisor]` = staff or asset supervisor · `[assignee]` = staff or work order assignee

```
# Auth
POST   /api/token/                          Obtain JWT token pair
POST   /api/token/refresh/                  Refresh access token
POST   /api/token/verify/                   Verify token

# Users
POST   /api/user/create/                    Register a new user (requires X-Tenant-ID)
GET    /api/user/me                         [any]    Get current user profile (includes is_staff)
PATCH  /api/user/me                         [any]    Update current user
DELETE /api/user/me                         [any]    Delete current user
GET    /api/user/list/                      [any]    List users in the current tenant
POST   /api/user/{id}/promote/              [staff]  Promote user to staff
POST   /api/user/forgot-password/           Send password reset email
POST   /api/user/reset-password/            Reset password with token

# Tenants  (superuser only)
GET    /api/tenant/                          List all tenants
POST   /api/tenant/                          Create tenant
GET    /api/tenant/{id}/                     Retrieve tenant
PATCH  /api/tenant/{id}/                     Update tenant
DELETE /api/tenant/{id}/                     Delete tenant

# Asset Types                               [staff]  all endpoints
GET    /api/asset-type/                      List asset types
POST   /api/asset-type/                      Create asset type
GET    /api/asset-type/{id}/                 Retrieve
PATCH  /api/asset-type/{id}/                 Update
DELETE /api/asset-type/{id}/                 Delete

# Assets
GET    /api/asset/                          [any]        List assets (excludes soft-deleted)
POST   /api/asset/                          [staff]      Create asset
GET    /api/asset/{id}/                     [any]        Retrieve asset
PATCH  /api/asset/{id}/                     [supervisor] Update asset
DELETE /api/asset/{id}/                     [staff]      Soft-delete asset
POST   /api/asset/{id}/restore/             [staff]      Restore soft-deleted asset
POST   /api/asset/{id}/supervisor/          [staff]      Assign supervisor
POST   /api/asset/{id}/sensor-alert/        [supervisor] Report an alert  body: {message?, severity?}

# Work Order Types                          [staff]  all endpoints
GET    /api/work-order-type/                 List work order types
POST   /api/work-order-type/                 Create work order type
GET    /api/work-order-type/{id}/            Retrieve
PATCH  /api/work-order-type/{id}/            Update
DELETE /api/work-order-type/{id}/            Delete  (409 if active work orders exist)

# Work Orders
GET    /api/work-order/                     [any]      List work orders
                                                       Filters: ?status=&priority=&asset=&assigned_to=
POST   /api/work-order/                     [staff]    Create work order
GET    /api/work-order/{id}/                [any]      Retrieve work order
PATCH  /api/work-order/{id}/                [assignee] Update work order
DELETE /api/work-order/{id}/                [staff]    Soft-delete work order
POST   /api/work-order/{id}/restore/        [staff]    Restore      body: {notes}
POST   /api/work-order/{id}/start/          [assignee] → IN_PROGRESS  body: {notes}
POST   /api/work-order/{id}/hold/           [assignee] → ON_HOLD      body: {notes}
POST   /api/work-order/{id}/complete/       [assignee] → COMPLETED    body: {notes, estimated_hours}
POST   /api/work-order/{id}/cancel/         [assignee] → CANCELLED    body: {notes}
POST   /api/work-order/{id}/assign/         [staff]    Reassign       body: {assigned_to, notes}

# Outbox  (read-only inspection)
GET    /api/outbox/                          List outbox events
                                             Filters: ?status=&event_type=&aggregate_type=&aggregate_id=
GET    /api/outbox/{id}/                     Retrieve outbox event
```

---

## Infrastructure (Terraform)

All production infrastructure is defined in `terraform/` and organized into reusable modules.

### Remote state

Terraform state is stored in an S3 bucket configured in `backend-prod.hcl`. This enables safe team collaboration and prevents concurrent applies from corrupting state.

### Modules

#### `vpc`
Creates the network foundation: VPC, public and private subnets across availability zones, internet gateway, route tables, and a shared security group used by ECS tasks and RDS.

#### `rds`
Deploys a PostgreSQL 15 RDS instance. Credentials are read from AWS Secrets Manager at `terraform apply` time — never hardcoded. The instance is placed in private subnets and is only reachable from within the VPC.

#### `ecs_django_core`
The main API service:
- ECS Cluster + Fargate task definition (Django image from Docker Hub).
- Application Load Balancer as the public entry point.
- ECS Service with configurable `desired_count` for horizontal scaling.
- A separate **migration task definition** (same image, runs `manage.py migrate`) used exclusively during deployments.

#### `ecs_outbox_observer`
Runs the outbox dispatcher worker (`poll_outbox`). Has IAM permissions to publish to SNS and to send/receive from the SQS results queue.

#### `ecs_maintenance_checker`
Runs the maintenance checker (`check_maintenance`) on a schedule. Shares DB access with the main API but has no SNS/SQS permissions beyond writing outbox events.

#### `sns`
A single SNS topic that acts as the central event bus. All domain events published by the outbox worker are sent here.

#### `sqs`
An SQS queue where Lambda functions report processing results. The outbox worker polls this queue to mark events `SENT` or `FAILED`.

#### `sns_subscriber`
Provisions a Lambda function for each event consumer:
- Packages the Lambda handler + shared `notifier_base.py` into a ZIP using Terraform `archive_file` `source` blocks (no Lambda Layers needed).
- Attaches an SNS subscription with a `FilterPolicy` on `event_type` so each Lambda only receives relevant events.
- Creates an IAM role with permissions for SES, DynamoDB, and SQS.

### Secrets management

Database credentials live in AWS Secrets Manager. Terraform reads them at apply time and injects them into ECS task definitions as environment variables. No credentials are ever stored in version control or Terraform state in plaintext.

### Infrastructure cost estimate

The following figures are monthly estimates for the `us-east-1` region at a typical small-to-medium production workload. All prices are in USD.

#### Fixed costs (always running)

| Service | Configuration | Est. cost/month |
|---|---|---|
| ECS Fargate — Django API | 1–2 tasks · 0.25 vCPU / 0.5 GB RAM | $9–18 |
| ECS Fargate — Outbox Worker | 1 task continuous · 0.25 vCPU / 0.5 GB RAM | $9 |
| ECS Fargate — Maintenance Checker | 1 task continuous · 0.25 vCPU / 0.5 GB RAM | $9 |
| RDS PostgreSQL 15 | db.t3.micro + 20 GB storage | $15 |
| Application Load Balancer | Fixed charge + LCUs | $17–20 |
| NAT Gateway | 1 AZ (required for private-subnet tasks to reach AWS APIs) | $32 |
| AWS Secrets Manager | ~2 secrets (DB credentials) | $1 |
| CloudWatch Logs | ECS + Lambda log groups | $2–5 |

#### Variable costs (scale with usage)

| Service | Free tier | Beyond free tier |
|---|---|---|
| SNS | 1M requests/month | $0.50 per additional 1M |
| SQS | 1M requests/month | $0.40 per additional 1M |
| Lambda (×5 functions) | 1M invocations/month | $0.20 per additional 1M |
| DynamoDB (idempotency store) | 25 GB + 200M requests/month | Pay-per-request beyond free tier |
| SES | 62,000 emails/month (from EC2/ECS) | $0.10 per additional 1,000 emails |
| S3 (Terraform state) | — | < $0.01 |

At typical notification volumes (hundreds to low thousands of events per day) all variable services stay within or very close to the AWS free tier.

#### Total estimate

| Scenario | Est. cost/month |
|---|---|
| Minimal (1 API task, single-AZ RDS) | ~$95–100 |
| Typical production (2 API tasks) | ~$105–115 |
| High availability (2 API tasks + RDS Multi-AZ) | ~$120–130 |

#### Main cost drivers to watch

- **NAT Gateway ($32/month)** — the largest hidden cost. Required so that Fargate tasks in private subnets can reach SNS, SQS, SES, and ECR. Can be partially replaced with [VPC Endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints.html) for individual AWS services, which eliminates NAT data-transfer charges for those services.
- **ALB ($17–20/month)** — fixed charge regardless of traffic volume.
- **ECS Fargate** — the three always-on workers (API, outbox, maintenance checker) each run 24/7; cost scales linearly with `desired_count` and task size.
- **RDS** — upgrading from `db.t3.micro` to `db.t3.small` roughly doubles the DB cost; enabling Multi-AZ doubles it again.

---

## CI/CD Pipelines

### checks.yml — Continuous Integration

Runs on every push to any branch. Concurrent runs on the same branch are cancelled automatically.

```
Push to any branch
  → docker compose build  (CI config, DEV=true)
  → docker compose up -d
  → Wait for PostgreSQL healthcheck
  → python manage.py migrate   (test settings)
  → python manage.py test      (test settings)
  → flake8
```

### deploy.yaml — Continuous Deployment

Runs only on pushes to `master`. Deployments are serialized (`cancel-in-progress: false`) so two deployments never run simultaneously.

```
Push to master
  → Configure AWS credentials
  → Build Docker image and push to Docker Hub  (:latest)
  → terraform init  (S3 backend)
  → Read Terraform outputs  (cluster, service, migration task ARN, subnets, SG)
  → Run migration ECS task (Fargate, one-shot)
       → Wait for task to stop
       → If exit code != 0: fetch CloudWatch logs and fail the pipeline
  → aws ecs update-service --force-new-deployment  (main API)
  → aws ecs update-service --force-new-deployment  (outbox worker)
```

This guarantees:
1. Migrations always run before new code goes live.
2. A failed migration stops the deployment — the running service is untouched.
3. Both the API and the outbox worker are updated atomically on every release.

---

## Design Decisions

### UUIDs as primary keys

All models use `UUIDField(primary_key=True, default=uuid.uuid4)`. IDs can be generated client-side or in the application layer before hitting the database, data can be safely merged across environments, and sequential integers don't leak business information (e.g., total number of work orders created).

### Soft delete over hard delete

Assets and work orders use a `deleted_at` timestamp instead of physical `DELETE`. This preserves referential integrity (foreign keys to deleted records remain valid), enables audit trails, and allows accidental deletions to be reversed. The unique constraint on `(tenant, serial_number)` uses a partial index (`WHERE deleted_at IS NULL`) so deleted serial numbers are released back for reuse.

### Validation not enforced in `save()`

`Asset.save()` and `WorkOrder.save()` deliberately do not call `self.full_clean()`. Validation is the responsibility of serializers (API boundary input validation), service methods (business rules inside atomic transactions), and model action methods (`start()`, `complete()`, etc.). This avoids double-validation and keeps the service layer in full control of what is checked and when.

### Service layer for all mutations

All writes go through a `*Service` class decorated with `@transaction.atomic`. Each method uses `select_for_update()` to lock the row before modifying it, preventing race conditions when multiple API instances or background workers operate on the same record concurrently.

### Transactional outbox

Publishing to SNS as part of a database transaction is not atomic — SNS is an external system. The outbox pattern solves this by writing the event to `outbox_events` in the same transaction as the business operation. A background worker reads from this table and publishes to SNS separately. Lambda idempotency (DynamoDB) ensures retried deliveries never send duplicate emails.

### Status transition validation at the view layer

Work order status transitions are checked in the view (`_check_transition`) before calling the service, returning `409 Conflict` rather than letting a model `ValidationError` map to `400`. This gives clean HTTP semantics: `400` means malformed request data, `409` means the operation is valid but not allowed in the current state.

### Notes as an append-only audit log

Rather than allowing direct overwrite of the `notes` field, every action endpoint prepends a timestamped entry. This creates an auditable history of when each state change occurred and why, without needing a separate `AuditLog` table.

### Notes required on all action endpoints

Every action endpoint (`start`, `hold`, `complete`, `cancel`, `assign`, `restore`) requires a non-empty `notes` value. This is a deliberate UX constraint that encourages operators to document the reason for every state change, building a useful history directly in the work order record.

### Per-tenant name uniqueness

`AssetType` and `WorkOrderType` names are unique within a tenant, not globally. Two tenants can both have an asset type called "Pump". This maps to how real organizations classify equipment — their taxonomy belongs to them.

### WorkOrderType deletion protection

Deleting a `WorkOrderType` that has associated `WorkOrder` records returns `409 Conflict` (caught via Django's `ProtectedError`). This prevents orphaned work orders and forces operators to reassign or close work orders before removing the type.

### Shared Lambda base class over Lambda Layers

The common Lambda behavior (idempotency, SES sending, SQS reporting) lives in `lambdas/notifier_base.py`. Rather than using Lambda Layers, Terraform bundles this file directly into each Lambda's ZIP archive using `archive_file` `source` blocks — the path is derived from each handler's `source_dir` (i.e. `${source_dir}/../notifier_base.py`), so the `sns_subscriber` module needs no separate `shared_dir` variable. Each Lambda is fully self-contained, and deployments require no extra layer management.

### Sensor alerts as stateless signals

The `POST /api/asset/{id}/sensor-alert/` endpoint intentionally has no `Sensor` model. IoT gateways and monitoring agents call it to signal that something is wrong with an asset; the endpoint only requires an optional `message` and `severity`. The identity of the triggering sensor is irrelevant at the notification layer — the supervisor receives the asset details and the alert description, which is enough context to act. This avoids a sensor registry that would need to be kept in sync with external systems.
