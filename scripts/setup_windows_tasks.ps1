# setup_windows_tasks.ps1 - Windows Task Scheduler equivalents of the Linux cron jobs
#
# Registers two per-user tasks (no admin needed, idempotent - re-run to update):
#   SimplexMind-Ingest    every 5 min   conversation_ingest.py --quiet --log
#                         (crash-recovery safety net; the Stop hook is the primary path)
#   SimplexMind-Autotune  Sun 04:00     subconscious_autotune.py
#                         (weekly keyword mining; journals to logs/subconscious_autotune.log)
#
# Both run the repo venv's pythonw.exe (no console window). The scripts do their own
# file logging, so no shell redirection is involved. Create the venv first:
#   py -m venv venv; venv\Scripts\pip install -r requirements.txt
#
# Remove the tasks with:
#   Unregister-ScheduledTask -TaskName SimplexMind-Ingest,SimplexMind-Autotune -Confirm:$false

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Pythonw  = Join-Path $RepoRoot 'venv\Scripts\pythonw.exe'
$Ingest   = Join-Path $RepoRoot 'src\utils\agent_skills\conversation\conversation_ingest.py'
$Autotune = Join-Path $RepoRoot 'src\utils\agent_skills\subconscious\subconscious_autotune.py'

if (-not (Test-Path $Pythonw)) {
    Write-Error "venv interpreter not found at $Pythonw - create the venv first (py -m venv venv; venv\Scripts\pip install -r requirements.txt)"
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Every 5 minutes, indefinitely (PS 5.1 needs an explicit long repetition duration)
$ingestTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$ingestAction = New-ScheduledTaskAction -Execute $Pythonw `
    -Argument "`"$Ingest`" --quiet --log" -WorkingDirectory $RepoRoot
Register-ScheduledTask -TaskName 'SimplexMind-Ingest' -Action $ingestAction `
    -Trigger $ingestTrigger -Settings $settings -Force | Out-Null
Write-Output "registered SimplexMind-Ingest (every 5 min)"

$autotuneTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 04:00
$autotuneAction = New-ScheduledTaskAction -Execute $Pythonw `
    -Argument "`"$Autotune`"" -WorkingDirectory $RepoRoot
Register-ScheduledTask -TaskName 'SimplexMind-Autotune' -Action $autotuneAction `
    -Trigger $autotuneTrigger -Settings $settings -Force | Out-Null
Write-Output "registered SimplexMind-Autotune (Sun 04:00)"
