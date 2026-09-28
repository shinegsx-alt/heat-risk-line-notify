# 一次性設定：註冊 Windows 工作排程器，讓「登入這台電腦」時自動背景執行
# start_services.ps1（進而啟動 ngrok + line_webhook_listener.py）。
#
# !! 只在正式部署的機器上執行這支腳本，不要在開發機上跑 !!
#
# 使用前務必先在這個資料夾建立 ngrok_domain.txt（見 start_services.ps1 的說明）。
#
# 用法（用一般權限執行即可，不需要系統管理員）：
#     .\setup_autostart.ps1

$repoDir = $PSScriptRoot
$domainFile = Join-Path $repoDir "ngrok_domain.txt"

if (-not (Test-Path $domainFile)) {
    Write-Error "找不到 $domainFile，請先建立這個檔案並填入 ngrok 固定網域，再執行這支腳本"
    exit 1
}

$scriptPath = Join-Path $repoDir "start_services.ps1"
$taskName = "熱危害LINE監聽服務"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "登入時自動啟動 ngrok + line_webhook_listener.py，等待LINE群組關鍵字「熱危害」觸發截圖流程" `
    -Force

Write-Host "設定完成：下次登入這台電腦時，會自動背景啟動 ngrok 與監聽程式。"
Write-Host "現在要立刻測試的話，直接執行: .\start_services.ps1"
Write-Host "要移除這個自動啟動設定，執行: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
