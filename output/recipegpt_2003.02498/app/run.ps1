# run.ps1 — RecipeGPT CLI quickstart (Windows PowerShell)
# Usage:  .\run.ps1            # runs the dependency-free evaluation demo
#         .\run.ps1 -Gen       # also installs torch/transformers + real GPT-2 gen
param([switch]$Gen)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

# Prefer a real (non-Store) python.
$py = "python"
try { & $py -c "import sys; assert sys.version_info>=(3,9)" } catch {
  Write-Host "python 3.9+ not found on PATH" -ForegroundColor Red; exit 1
}

Write-Host "== Evaluation module (no heavy deps) ==" -ForegroundColor Cyan
& $py main.py --mode evaluate

if ($Gen) {
  Write-Host "`n== Installing generation deps (torch, transformers) ==" -ForegroundColor Cyan
  & $py -m pip install -r requirements.txt
  Write-Host "`n== Real GPT-2 inference: instructions from title+ingredients ==" -ForegroundColor Cyan
  & $py main.py --mode gen-instructions
}
