$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "python3" }
Set-Location $root
& $python backend/manage.py runserver --settings=config.test_settings 0.0.0.0:8000