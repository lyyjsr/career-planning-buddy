$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$CommandArguments
    )

    & $Executable @CommandArguments
    if ($LASTEXITCODE -ne 0) {
        throw (
            "Command failed with exit code ${LASTEXITCODE}: " +
            "$Executable $($CommandArguments -join ' ')"
        )
    }
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repositoryRoot "backend\.venv\Scripts\python.exe"
$backendPython = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$npmCommand = (Get-Command "npm.cmd" -ErrorAction Stop).Source
$env:APP_ENV = if ($env:APP_ENV) { $env:APP_ENV } else { "test" }
$env:LLM_PROVIDER = if ($env:LLM_PROVIDER) { $env:LLM_PROVIDER } else { "mock" }
$env:SEARCH_PROVIDER = "mock"
$env:EMBEDDING_PROVIDER = "mock"
$env:DATABASE_URL = if ($env:DATABASE_URL) {
    $env:DATABASE_URL
}
else {
    "postgresql+asyncpg://career_buddy:career_buddy_local@localhost:5432/career_buddy"
}
$env:JWT_SECRET = if ($env:JWT_SECRET) {
    $env:JWT_SECRET
}
else {
    "local-test-secret-with-at-least-32-characters"
}

Push-Location (Join-Path $repositoryRoot "backend")
try {
    Invoke-Checked -Executable $backendPython -CommandArguments @("-m", "ruff", "check", ".")
    Invoke-Checked -Executable $backendPython -CommandArguments @(
        "-m", "mypy", "app", "tests", "scripts", "evals"
    )
    Invoke-Checked -Executable $backendPython -CommandArguments @(
        "-m", "alembic", "upgrade", "head"
    )
    Invoke-Checked -Executable $backendPython -CommandArguments @("-m", "pytest")
    Invoke-Checked -Executable $backendPython -CommandArguments @(
        "-m", "scripts.run_eval", "--no-persist"
    )
}
finally {
    Pop-Location
}

Push-Location (Join-Path $repositoryRoot "frontend")
try {
    Invoke-Checked -Executable $npmCommand -CommandArguments @("test")
    Invoke-Checked -Executable $npmCommand -CommandArguments @("run", "build")
}
finally {
    Pop-Location
}
