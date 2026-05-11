#Requires -Version 5.1
<#
.SYNOPSIS
    Prepares ECS for a clean `terraform destroy`.

.DESCRIPTION
    Queries AWS directly (no Terraform state required) to find all ECS clusters
    that have running services, then for each one:
      1. Deregisters the Application Auto Scaling target (prevents the policy
         from replacing tasks that are being terminated).
      2. Scales the service down to 0.
      3. Waits until all tasks have stopped.

    After this script completes, run:
        cd terraform; terraform destroy

.EXAMPLE
    .\terraform\scripts\teardown_infra.ps1
#>

$ErrorActionPreference = "Stop"

# -- 1. List all ECS clusters ---------------------------------------------

Write-Host "=== 1. Looking for ECS clusters with active services ===" -ForegroundColor Cyan

$ClusterArns = (aws ecs list-clusters --output json | ConvertFrom-Json).clusterArns

if ($ClusterArns.Count -eq 0) {
    Write-Host "No ECS clusters found." -ForegroundColor Red
    exit 1
}

# Build a list of (cluster, service) pairs that have at least one service.
$Targets = @()

foreach ($ClusterArn in $ClusterArns) {
    $ClusterName = $ClusterArn -replace ".*/", ""
    $ServiceArns = (aws ecs list-services --cluster $ClusterName --output json | ConvertFrom-Json).serviceArns

    foreach ($ServiceArn in $ServiceArns) {
        $ServiceName = $ServiceArn -replace ".*/", ""
        $Targets += [PSCustomObject]@{ Cluster = $ClusterName; Service = $ServiceName }
        Write-Host "  Found: cluster=$ClusterName  service=$ServiceName" -ForegroundColor Green
    }
}

if ($Targets.Count -eq 0) {
    Write-Host "No ECS services found in any cluster. Nothing to drain." -ForegroundColor Yellow
    exit 0
}

# -- 2. Confirm before proceeding -----------------------------------------

Write-Host ""
Write-Host "The following services will be scaled to 0:" -ForegroundColor Yellow
foreach ($t in $Targets) {
    Write-Host "  cluster=$($t.Cluster)  service=$($t.Service)"
}
Write-Host ""
$confirm = Read-Host "Proceed? (y/N)"
if ($confirm -notmatch "^[Yy]$") {
    Write-Host "Aborted." -ForegroundColor Red
    exit 0
}

# -- 3. Deregister autoscaling + scale down each service ------------------

foreach ($t in $Targets) {
    $ResourceId = "service/$($t.Cluster)/$($t.Service)"

    Write-Host ""
    Write-Host "=== Processing $($t.Service) ===" -ForegroundColor Cyan

    # Deregister autoscaling target (silently ignore if not registered)
    Write-Host "  Deregistering autoscaling target ($ResourceId)..."
    $ErrorActionPreference = "Continue"
    $null = aws application-autoscaling deregister-scalable-target `
        --service-namespace ecs `
        --resource-id $ResourceId `
        --scalable-dimension "ecs:service:DesiredCount" 2>&1
    $ErrorActionPreference = "Stop"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Autoscaling target deregistered." -ForegroundColor Green
    } else {
        Write-Host "  No autoscaling target found -- skipping." -ForegroundColor DarkGray
    }

    # Scale to 0
    Write-Host "  Scaling to 0..."
    aws ecs update-service `
        --cluster      $t.Cluster `
        --service      $t.Service `
        --desired-count 0 `
        --output json | Out-Null
    Write-Host "  Desired count set to 0." -ForegroundColor Green
}

# -- 4. Wait for all services to drain ------------------------------------

Write-Host ""
Write-Host "=== Waiting for all tasks to stop ===" -ForegroundColor Cyan
Write-Host "(This may take up to 2 minutes...)"

foreach ($t in $Targets) {
    Write-Host "  Waiting for $($t.Service)..."
    aws ecs wait services-stable `
        --cluster  $t.Cluster `
        --services $t.Service
    Write-Host "  ${($t.Service)}: drained." -ForegroundColor Green
}

# -- Done -----------------------------------------------------------------

Write-Host ""
Write-Host "All tasks stopped. Run the following to destroy the infrastructure:" -ForegroundColor Green
Write-Host ""
Write-Host "  cd terraform; terraform destroy"
Write-Host ""
