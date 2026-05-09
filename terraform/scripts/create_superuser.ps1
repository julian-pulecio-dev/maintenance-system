param(
  [Parameter(Mandatory = $true)]  [string]$Email,
  [Parameter(Mandatory = $true)]  [string]$Password,
  [string]$Name          = "",
  [string]$ContainerName = "app"
)

$ErrorActionPreference = "Stop"

function Select-FromList {
  param([string]$Label, [string[]]$Items)
  if ($Items.Count -eq 1) { return $Items[0] }
  Write-Host "Available ${Label}s:"
  for ($i = 0; $i -lt $Items.Count; $i++) {
    Write-Host "  [$i] $($Items[$i])"
  }
  $idx = Read-Host "Select $Label number"
  return $Items[$idx]
}

Write-Host "=== 1. Looking for available clusters ===" -ForegroundColor Cyan
$ClusterArns = (aws ecs list-clusters --output json | ConvertFrom-Json).clusterArns

if ($ClusterArns.Count -eq 0) {
  Write-Host "No ECS clusters found." -ForegroundColor Red
  exit 1
}

$ClusterArn  = Select-FromList -Label "cluster" -Items $ClusterArns
$ClusterName = $ClusterArn -replace ".*/", ""
Write-Host "Selected cluster: $ClusterName" -ForegroundColor Green

Write-Host "=== 2. Looking for services in the cluster ===" -ForegroundColor Cyan
$ServiceArns = (aws ecs list-services --cluster $ClusterName --output json | ConvertFrom-Json).serviceArns

if ($ServiceArns.Count -eq 0) {
  Write-Host "No services found in cluster $ClusterName." -ForegroundColor Red
  exit 1
}

$ServiceArn  = Select-FromList -Label "service" -Items $ServiceArns
$ServiceName = $ServiceArn -replace ".*/", ""
Write-Host "Selected service: $ServiceName" -ForegroundColor Green

Write-Host "=== 3. Getting active task for the service ===" -ForegroundColor Cyan
$TaskArns = (aws ecs list-tasks --cluster $ClusterName --service-name $ServiceName --output json | ConvertFrom-Json).taskArns

if ($TaskArns.Count -eq 0) {
  Write-Host "No active tasks in service $ServiceName." -ForegroundColor Red
  exit 1
}

$TaskArn = $TaskArns[0]
Write-Host "Task found: $TaskArn" -ForegroundColor Green

Write-Host "=== 4. Running migrations ===" -ForegroundColor Cyan
aws ecs execute-command `
  --cluster $ClusterName `
  --task $TaskArn `
  --container $ContainerName `
  --interactive `
  --command "python manage.py migrate --no-input"

if ($LASTEXITCODE -ne 0) {
  Write-Host "Error running migrations." -ForegroundColor Red
  exit 1
}

Write-Host "Migrations applied." -ForegroundColor Green

Write-Host "=== 5. Creating superuser ===" -ForegroundColor Cyan
$Command = "python manage.py create_superuser_global --email `"$Email`" --password `"$Password`""
if ($Name -ne "") {
  $Command += " --name `"$Name`""
}

aws ecs execute-command `
  --cluster $ClusterName `
  --task $TaskArn `
  --container $ContainerName `
  --interactive `
  --command $Command

if ($LASTEXITCODE -ne 0) {
  Write-Host "Error creating superuser." -ForegroundColor Red
  exit 1
}

Write-Host "Superuser created: $Email" -ForegroundColor Green
