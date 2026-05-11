#!/usr/bin/env bash
# Creates a global superuser by running the create_superuser_global management
# command inside an existing ECS Fargate task via `aws ecs execute-command`.
#
# Usage:
#   ./terraform/scripts/create_superuser.sh -e admin@example.com -p secret123
#   ./terraform/scripts/create_superuser.sh -e admin@example.com -p secret123 -n "Admin" -c app

set -euo pipefail

# ── Parse arguments ───────────────────────────────────────────────────────

EMAIL=""
PASSWORD=""
NAME=""
CONTAINER="app"

usage() {
  echo "Usage: $0 -e <email> -p <password> [-n <name>] [-c <container>]"
  exit 1
}

while getopts "e:p:n:c:" opt; do
  case "$opt" in
    e) EMAIL="$OPTARG" ;;
    p) PASSWORD="$OPTARG" ;;
    n) NAME="$OPTARG" ;;
    c) CONTAINER="$OPTARG" ;;
    *) usage ;;
  esac
done

[[ -z "$EMAIL" || -z "$PASSWORD" ]] && usage

# ── Helper: select from a list ────────────────────────────────────────────

select_from_list() {
  local label="$1"
  shift
  local items=("$@")

  if [[ ${#items[@]} -eq 1 ]]; then
    echo "${items[0]}"
    return
  fi

  echo "Available ${label}s:" >&2
  for i in "${!items[@]}"; do
    echo "  [$i] ${items[$i]}" >&2
  done

  read -rp "Select $label number: " idx
  echo "${items[$idx]}"
}

# ── 1. List clusters ──────────────────────────────────────────────────────

echo "=== 1. Looking for available clusters ==="

mapfile -t CLUSTER_ARNS < <(aws ecs list-clusters --output json | jq -r '.clusterArns[]')

if [[ ${#CLUSTER_ARNS[@]} -eq 0 ]]; then
  echo "No ECS clusters found." >&2
  exit 1
fi

CLUSTER_ARN=$(select_from_list "cluster" "${CLUSTER_ARNS[@]}")
CLUSTER_NAME="${CLUSTER_ARN##*/}"
echo "Selected cluster: $CLUSTER_NAME"

# ── 2. List services ──────────────────────────────────────────────────────

echo "=== 2. Looking for services in the cluster ==="

mapfile -t SERVICE_ARNS < <(aws ecs list-services --cluster "$CLUSTER_NAME" --output json | jq -r '.serviceArns[]')

if [[ ${#SERVICE_ARNS[@]} -eq 0 ]]; then
  echo "No services found in cluster $CLUSTER_NAME." >&2
  exit 1
fi

SERVICE_ARN=$(select_from_list "service" "${SERVICE_ARNS[@]}")
SERVICE_NAME="${SERVICE_ARN##*/}"
echo "Selected service: $SERVICE_NAME"

# ── 3. Get an active task ─────────────────────────────────────────────────

echo "=== 3. Getting active task for the service ==="

TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --output json | jq -r '.taskArns[0]')

if [[ -z "$TASK_ARN" || "$TASK_ARN" == "null" ]]; then
  echo "No active tasks in service $SERVICE_NAME." >&2
  exit 1
fi

echo "Task found: $TASK_ARN"

# ── 4. Run migrations ─────────────────────────────────────────────────────

echo "=== 4. Running migrations ==="

aws ecs execute-command \
  --cluster "$CLUSTER_NAME" \
  --task    "$TASK_ARN" \
  --container "$CONTAINER" \
  --interactive \
  --command "python manage.py migrate --no-input"

echo "Migrations applied."

# ── 5. Create superuser ───────────────────────────────────────────────────

echo "=== 5. Creating superuser ==="

COMMAND="python manage.py create_superuser_global --email \"$EMAIL\" --password \"$PASSWORD\""
if [[ -n "$NAME" ]]; then
  COMMAND+=" --name \"$NAME\""
fi

aws ecs execute-command \
  --cluster "$CLUSTER_NAME" \
  --task    "$TASK_ARN" \
  --container "$CONTAINER" \
  --interactive \
  --command "$COMMAND"

echo "Superuser created: $EMAIL"
