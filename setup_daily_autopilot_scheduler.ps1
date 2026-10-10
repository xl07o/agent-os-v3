# setup_daily_autopilot_scheduler.ps1
# ينشئ مهمة Windows Task Scheduler تشغّل daily_autopilot.py --quick كل يوم 2:00 صباحاً
# التشغيل: powershell -ExecutionPolicy Bypass -File setup_daily_autopilot_scheduler.ps1

$pythonPath = "C:\Python314\python.exe"
$scriptPath = Join-Path $PSScriptRoot "daily_autopilot.py"
$taskName   = "AgentOS-DailyAutopilot-Nightly"

$action   = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" --quick" -WorkingDirectory $PSScriptRoot
$trigger  = New-ScheduledTaskTrigger -Daily -At "02:00"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Write-Host "تحقق: schtasks /query /tn `"$taskName`" /fo LIST /v"
