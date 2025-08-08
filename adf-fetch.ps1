# Export-AdfInventory.ps1
# Requires: az login; az account set --subscription "<SUB_ID>"

param(
  [string]$SubscriptionId = (az account show --query id -o tsv),
  [string]$OutDir = "./adf-inventory"
)

$ErrorActionPreference = "Stop"
az account set --subscription $SubscriptionId | Out-Null
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$factories = az datafactory list -o json | ConvertFrom-Json
if (-not $factories) { Write-Host "No ADFs found."; exit 0 }

$api = "2018-06-01"                   # Stable ADF ARM API
$apiPreview = "2018-06-01-preview"    # For Managed VNet/MPE if needed

$all = @()

foreach ($f in $factories) {
  $rg  = $f.resourceGroup
  $fn  = $f.name
  Write-Host "▶︎ Inspecting $fn ($rg)"

  # 1) Factory (identity, publicNetworkAccess, git, global params, etc.)
  $factory = az datafactory show -g $rg -n $fn -o json | ConvertFrom-Json

  # 2) Integration Runtimes (type, SHIR vs Managed, status)
  $irs = az datafactory integration-runtime list -g $rg --factory-name $fn -o json | ConvertFrom-Json
  $irDetails = @()
  foreach ($ir in $irs) {
    $irDetail = az datafactory integration-runtime show -g $rg --factory-name $fn -n $ir.name -o json | ConvertFrom-Json
    # Try to get node/heartbeat status if available
    try {
      $status = az datafactory integration-runtime get-status -g $rg --factory-name $fn -n $ir.name -o json | ConvertFrom-Json
    } catch { $status = $null }
    $irDetails += [pscustomobject]@{
      name   = $ir.name
      type   = $ir.properties.type
      desc   = $ir.properties.description
      status = $status
    }
  }

  # 3) Managed Virtual Network(s) and Managed Private Endpoints (if using Managed VNet)
  # NOTE: ADF uses a Microsoft-managed VNet; you won't see your own VNet/subnet here.
  $mvnets = $null; $mpes = @()
  try {
    $mvnets = az rest --method get `
      --url "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$rg/providers/Microsoft.DataFactory/factories/$fn/managedVirtualNetworks?api-version=$api" `
      -o json | ConvertFrom-Json
  } catch {
    try {
      $mvnets = az rest --method get `
        --url "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$rg/providers/Microsoft.DataFactory/factories/$fn/managedVirtualNetworks?api-version=$apiPreview" `
        -o json | ConvertFrom-Json
    } catch { $mvnets = $null }
  }

  if ($mvnets?.value) {
    foreach ($mv in $mvnets.value) {
      $mvName = $mv.name
      try {
        $mpeList = az rest --method get `
          --url "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$rg/providers/Microsoft.DataFactory/factories/$fn/managedVirtualNetworks/$mvName/managedPrivateEndpoints?api-version=$apiPreview" `
          -o json | ConvertFrom-Json
        if ($mpeList?.value) {
          $mpes += $mpeList.value | ForEach-Object {
            [pscustomobject]@{
              name        = $_.name
              provisioning= $_.properties.provisioningState
              groupId     = $_.properties.groupId
              fqdns       = $_.properties.fqdns
              privateLink = $_.properties.privateLinkResourceId
              connection  = $_.properties.connectionState.status
            }
          }
        }
      } catch { }
    }
  }

  # 4) Linked services (auth model: Managed Identity vs Key/ConnString)
# Replace the whole $linkedSlim = ... block with this:
$linkedSlim = $linked | ForEach-Object {
  $tp = $_.properties.typeProperties
  $hasProp = { param($o,$n) $o -and ($o.PSObject.Properties.Name -contains $n) }

  if (&$hasProp $tp 'credential')        { $auth = 'CredentialRef' }
  elseif (&$hasProp $tp 'connectionString'){ $auth = 'ConnString' }
  elseif (&$hasProp $tp 'url')           { $auth = 'URL' }
  elseif ($_.properties.PSObject.Properties.Name -contains 'connectVia') { $auth = 'ViaIR' }
  elseif ((&$hasProp $tp 'authentication') -and ($tp.authentication -eq 'ManagedIdentity')) { $auth = 'ManagedIdentity' }
  else { $auth = 'Unknown' }

  [pscustomobject]@{
    name       = $_.name
    type       = $_.properties.type
    auth       = $auth
    connectVia = $_.properties.connectVia?.referenceName  # okay on PS7; on PS5.1 change to: ($_.properties.connectVia.referenceName)
  }
}

  # 5) Public network access & identities
  $pna   = $factory.properties?.publicNetworkAccess
  $ident = $factory.identity

  # Collect
  $rec = [pscustomobject]@{
    subscriptionId = $SubscriptionId
    resourceGroup  = $rg
    factoryName    = $fn
    location       = $factory.location
    publicNetworkAccess = $pna
    identity       = $ident
    managedVirtualNetworks = $mvnets?.value
    managedPrivateEndpoints = $mpes
    integrationRuntimes = $irDetails
    linkedServices  = $linkedSlim
    gitConfiguration= $factory.properties?.repoConfiguration
    globalParameters= $factory.properties?.globalParameters
    diagnostics     = (az monitor diagnostic-settings list --resource $factory.id -o json | ConvertFrom-Json)
  }

  $all += $rec
  $rec | ConvertTo-Json -Depth 10 | Out-File -Encoding utf8 "$OutDir/$($fn)-inventory.json"
}

# Also emit a CSV summary for quick scanning
$summary = $all | ForEach-Object {
  [pscustomobject]@{
    Factory             = $_.factoryName
    RG                  = $_.resourceGroup
    Location            = $_.location
    PublicNetworkAccess = $_.publicNetworkAccess
    HasManagedVNet      = [bool]$_.managedVirtualNetworks
    IR_Count            = ($_.integrationRuntimes | Measure-Object).Count
    MPE_Count           = ($_.managedPrivateEndpoints | Measure-Object).Count
    LinkedServices      = ($_.linkedServices | ForEach-Object { "$($_.name)[$($_.auth)]" }) -join "; "
  }
}
$summary | Export-Csv -NoTypeInformation -Encoding UTF8 "$OutDir/_summary.csv"

Write-Host "✅ Inventory written to $OutDir"