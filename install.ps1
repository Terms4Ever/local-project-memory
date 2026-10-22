param(
    [ValidateSet('both', 'claude', 'codex')]
    [string]$HostApp = 'both'
)
$ErrorActionPreference = 'Stop'
if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) { throw 'This installer supports Windows only.' }
$pythonCommand = $null
foreach ($candidate in @('py', 'python')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonCommand = $candidate; break }
    }
}
if (-not $pythonCommand) { throw 'Install Python 3.11 or newer from python.org, then reopen PowerShell.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows and reopen PowerShell.' }
& $pythonCommand (Join-Path $PSScriptRoot 'install.py') --host $HostApp
if ($LASTEXITCODE -ne 0) { throw 'Installation failed. Read the error and any rollback manifest before retrying.' }
& $pythonCommand (Join-Path $PSScriptRoot 'memory.py') check
if ($LASTEXITCODE -ne 0) { throw 'Database verification failed.' }
Write-Host 'Installed. Open a new local chat. Codex hooks require review/approval in Codex; see README.md.'
