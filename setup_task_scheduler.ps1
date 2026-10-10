# setup_task_scheduler.ps1
# ينشئ مهمة Windows Task Scheduler تشغّل task_queue.py run كل ساعة
# التشغيل: powershell -ExecutionPolicy Bypass -File setup_task_scheduler.ps1

$pythonPath = "C:\Python314\python.exe"
$scriptPath = Join-Path $PSScriptRoot "agent_os\task_queue.py"
$taskName   = "AgentOS-TaskQueue-Hourly"

$action   = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" run" -WorkingDirectory $PSScriptRoot
$trigger  = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At (Get-Date)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Write-Host "تحقق: schtasks /query /tn $taskName"
