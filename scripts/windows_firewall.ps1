param(
  [Parameter(Mandatory=$true)][ValidateSet('add','remove')][string]$Mode,
  [Parameter(Mandatory=$true)][string]$RulePrefix,
  [string]$Candidate,
  [string]$Node
)
$ErrorActionPreference='Stop'
if ($RulePrefix -notmatch '^devneya-acceptance-[0-9a-f-]+$') { throw 'Invalid test rule prefix' }
if ($Mode -eq 'remove') {
  Get-NetFirewallRule -Name "$RulePrefix-*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  exit 0
}
try {
  $candidatePath = (Get-Item -LiteralPath $Candidate).FullName
  $nodePath = [IO.Path]::GetFullPath($Node)
  if ([IO.Path]::GetFileName($nodePath) -ne 'node.exe' -or (Test-Path -LiteralPath $nodePath)) {
    throw 'Expected an unextracted Node executable for the cold start'
  }
  New-NetFirewallRule -Name "$RulePrefix-candidate" -DisplayName "$RulePrefix candidate" -Direction Outbound -Action Block -Program $candidatePath -Profile Any | Out-Null

  # Firewall path validation requires a resolvable application path. Register
  # the exact path, then remove the placeholder before the launcher extracts Node.
  $nodeDirectory = [IO.Path]::GetDirectoryName($nodePath)
  $createdDirectories = @()
  for ($cursor = $nodeDirectory; -not [IO.Directory]::Exists($cursor); $cursor = [IO.Path]::GetDirectoryName($cursor)) {
    $createdDirectories += $cursor
  }
  [IO.Directory]::CreateDirectory($nodeDirectory) | Out-Null
  try {
    [IO.File]::Open($nodePath, [IO.FileMode]::CreateNew).Dispose()
    try {
      New-NetFirewallRule -Name "$RulePrefix-node" -DisplayName "$RulePrefix Node" -Direction Outbound -Action Block -Program $nodePath -Profile Any | Out-Null
    } finally {
      [IO.File]::Delete($nodePath)
    }
  } finally {
    foreach ($directory in $createdDirectories) {
      [IO.Directory]::Delete($directory, $false)
    }
  }
} catch {
  Get-NetFirewallRule -Name "$RulePrefix-*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  throw
}
