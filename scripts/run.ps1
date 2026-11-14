param([string]$Entry = 'run.py', [Parameter(ValueFromRemainingArguments=$true)][string[]]$RunnerArguments)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$selection = Join-Path $root 'runtime\python-command.json'
if (Test-Path -LiteralPath $selection) {
    $python = (Get-Content -LiteralPath $selection -Raw | ConvertFrom-Json).python
} else {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
}
& $python (Join-Path $root $Entry) @RunnerArguments
exit $LASTEXITCODE
