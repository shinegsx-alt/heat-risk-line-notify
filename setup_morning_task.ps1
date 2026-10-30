# 一次性設定：註冊 Windows 工作排程器，每天早上 07:00 執行 morning_run.py，
# 把熱危害截圖 + 等級推播到「宜陽巡路隊」群組。
#
# 會開一個看得見的視窗顯示每個步驟，跑完停在畫面上（1 小時後自動關閉，或按任意鍵關閉）。
# 因為要顯示視窗，只有「已登入這台電腦」時才會執行；07:00 時電腦關機或睡眠，
# 會在下次開機/喚醒後補跑一次。
#
# 用法（用一般權限執行即可，不需要系統管理員）：
#     .\setup_morning_task.ps1

$repoDir = $PSScriptRoot
$scriptPath = Join-Path $repoDir "morning_run.py"
$taskName = "熱危害每日0700推播-宜陽巡路隊"

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    Write-Error "找不到 python，請確認 Python 已安裝並加入 PATH"
    exit 1
}

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $repoDir
$trigger = New-ScheduledTaskTrigger -Daily -At "07:00"
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
# Interactive：在目前登入的桌面上開視窗，看得到執行過程
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "每天 07:00 執行 morning_run.py：熱危害截圖 + 未來6小時等級推播到宜陽巡路隊群組" `
    -Force | Out-Null

Write-Host "設定完成：每天 07:00 會開視窗執行 morning_run.py，推播到「宜陽巡路隊」。"
Write-Host "立刻手動跑一次排程: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "只測試不推播:       python morning_run.py --dry-run"
Write-Host "移除這個排程:       Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
