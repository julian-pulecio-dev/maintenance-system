#!/usr/bin/env bash
# Prepares ECS for a clean `terraform destroy` by:
#   1. Deregistering the Application Auto Scaling target on the main API service
#      so the policy cannot replace tasks that are being terminated.
#   2. Scaling both long-running ECS services down to 0.
#   3. Waiting until all tasks have stopped.
#
# Usage:
#   ./scripts/teardown-infra.sh                              # terraform already initialised
#   ./scripts/teardown-infra.sh --backend backend-prod.hcl  # init with S3 backend first
#
# After this script completes, run:
#   cd terraform && terraform destroy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"

# ── Parse arguments ───────────────────────────────────────────────────────

BACKEND_CONFIG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend)
      BACKEND_CONFIG="${2:?'--backend requires a file argument, e.g. backend-prod.hcl'}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--backend <backend-config-file>]"
      exit 1
      ;;
  esac
done

# ── 1. Terraform init (optional) ─────────────────────────────────────────

cd "$TF_DIR"

if [[ -n "$BACKEND_CONFIG" ]]; then
  echo "Initialising Terraform with backend config: $BACKEND_CONFIG"
  terraform init -backend-config="$BACKEND_CONFIG" -input=false -reconfigure > /dev/null
  echo "  Done."
elif [[ ! -d ".terraform" ]]; then
  echo "ERROR: Terraform is not initialised. Run from the terraform/ directory:"
  echo "  terraform init -backend-config=backend-prod.hcl"
  echo "Or pass the backend config to this script:"
  echo "  $0 --backend backend-prod.hcl"
  exit 1
fi

# ── 2. Read cluster / service names from Terraform outputs ─────────────────

echo ""
echo "Reading Terraform outputs..."

MAIN_CLUSTER=$(terraform output -raw ecs_cluster_name)
MAIN_SERVICE=$(terraform output -raw ecs_service_name)
OUTBOX_CLUSTER=$(terraform output -raw outbox_cluster_name)
OUTBOX_SERVICE=$(terraform output -raw outbox_service_name)

echo "  Main API : cluster=$MAIN_CLUSTER  service=$MAIN_SERVICE"
echo "  Outbox   : cluster=$OUTBOX_CLUSTER  service=$OUTBOX_SERVICE"

# ── 3. Deregister the autoscaling target ─────────────────────────────────
# The main API service has a TargetTrackingScaling policy. Without removing
# it first, Application Auto Scaling will keep recreating tasks as ECS tries
# to drain them, making the service impossible to destroy cleanly.

RESOURCE_ID="service/$MAIN_CLUSTER/$MAIN_SERVICE"

echo ""
echo "Deregistering autoscaling target ($RESOURCE_ID)..."

if aws application-autoscaling deregister-scalable-target \
     --service-namespace ecs \
     --resource-id "$RESOURCE_ID" \
     --scalable-dimension "ecs:service:DesiredCount" 2>/dev/null; then
  echo "  Autoscaling target deregistered."
else
  echo "  No autoscaling target found — already removed or never registered."
fi

# ── 4. Scale both services down to 0 ─────────────────────────────────────

echo ""
echo "Scaling services down to 0..."

aws ecs update-service \
  --cluster "$MAIN_CLUSTER" \
  --service  "$MAIN_SERVICE" \
  --desired-count 0 \
  --output json > /dev/null
echo "  $MAIN_SERVICE desired count → 0."

aws ecs update-service \
  --cluster "$OUTBOX_CLUSTER" \
  --service  "$OUTBOX_SERVICE" \
  --desired-count 0 \
  --output json > /dev/null
echo "  $OUTBOX_SERVICE desired count → 0."

# ── 5. Wait for all tasks to stop ────────────────────────────────────────
# `services-stable` resolves when runningCount == desiredCount (both 0).

echo ""
echo "Waiting for tasks to drain (this may take up to 2 minutes)..."

aws ecs wait services-stable \
  --cluster "$MAIN_CLUSTER" \
  --services "$MAIN_SERVICE"
echo "  $MAIN_SERVICE: drained."

aws ecs wait services-stable \
  --cluster "$OUTBOX_CLUSTER" \
  --services "$OUTBOX_SERVICE"
echo "  $OUTBOX_SERVICE: drained."

# ── Done ─────────────────────────────────────────────────────────────────

echo ""
echo "All tasks stopped. Run the following to destroy the infrastructure:"
echo ""
echo "  cd terraform && terraform destroy"
echo ""
