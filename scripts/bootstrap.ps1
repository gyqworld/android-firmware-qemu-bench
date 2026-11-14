param([Parameter(ValueFromRemainingArguments=$true)][string[]]$SetupArguments)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$python = $null
foreach ($candidate in @('python.exe', 'python3.exe')) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
        & $command.Source -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $command.Source; break }
    }
}
if (-not $python -and (Test-Path -LiteralPath (Join-Path $root 'runtime\python\python.exe'))) {
    $python = Join-Path $root 'runtime\python\python.exe'
}
if (-not $python) {
    if ($SetupArguments -contains '--offline') { throw 'Offline mode requires an existing supported Python.' }
    $lock = Get-Content -LiteralPath (Join-Path $root 'scripts\dependencies\bootstrap.lock.json') -Raw | ConvertFrom-Json
    $spec = $lock.python
    $cache = Join-Path $root 'runtime\cache'
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $archive = Join-Path $cache $spec.filename
    if (-not (Test-Path -LiteralPath $archive)) {
        $partial = $archive + '.partial'
        Invoke-WebRequest -Uri $spec.url -OutFile $partial -UseBasicParsing
        if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.sha256) { throw 'Python download digest mismatch.' }
        Move-Item -LiteralPath $partial -Destination $archive
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.sha256) { throw 'Python cache digest mismatch.' }
    $target = Join-Path $root 'runtime\python'
    $python = Join-Path $target 'python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        Expand-Archive -LiteralPath $archive -DestinationPath $target
        $pth = Join-Path $target 'python311._pth'
        Add-Content -LiteralPath $pth -Value @('..\..', '..\..\scripts', '..\python-packages', 'import site')
    }
}
& $python (Join-Path $root 'scripts\setup_dependencies.py') @SetupArguments
exit $LASTEXITCODE
