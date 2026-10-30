# 啟動 ngrok + line_webhook_listener.py，各開一個看得見的視窗，方便掌握狀態：
#   - ngrok 視窗：顯示連線狀態和每一筆 LINE Webhook 請求
#   - listener 視窗：顯示收到的訊息、群組對映表更新、觸發的截圖流程
# 關掉視窗就等於停止服務。每次截圖流程的詳細輸出另存在 logs/run_*.log。
# 給開機自動啟動用，也可以手動執行（重新執行會先停掉舊的再重新啟動）。
#
# 使用前，要先在這個資料夾建立 ngrok_domain.txt，內容只填一行：你的 ngrok 固定網域
# 例如：xxxx-xx-xx.ngrok-free.app（不要加 https:// 前綴）

$repoDir = $PSScriptRoot
$domainFile = Join-Path $repoDir "ngrok_domain.txt"

if (-not (Test-Path $domainFile)) {
    Write-Error "找不到 $domainFile，請先建立這個檔案，內容填入你的 ngrok 固定網域（例如 xxxx.ngrok-free.app），不要加 https://"
    exit 1
}
$domain = (Get-Content $domainFile -Raw).Trim()
if (-not $domain) {
    Write-Error "$domainFile 內容是空的，請填入 ngrok 固定網域"
    exit 1
}

$logDir = Join-Path $repoDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 先停掉之前啟動的（包含舊版背景執行的），避免 5000 port 和 ngrok 網域被佔用
$listenerScript = Join-Path $repoDir "line_webhook_listener.py"
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*line_webhook_listener.py*" } |
    ForEach-Object {
        Write-Host "停止舊的 listener（PID $($_.ProcessId)）..."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Get-Process -Name "ngrok" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "停止舊的 ngrok（PID $($_.Id)）..."
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

Write-Host "啟動 ngrok（網域: $domain）..."
Start-Process -FilePath "ngrok" `
    -ArgumentList "http", "5000", "--domain=$domain" `
    -WindowStyle Normal

Start-Sleep -Seconds 3

Write-Host "啟動 line_webhook_listener.py ..."
# 用 cmd 開視窗才能設定視窗標題；-u 讓輸出即時顯示
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/k", "title LINE監聽-熱危害 && python -u `"$listenerScript`"" `
    -WorkingDirectory $repoDir `
    -WindowStyle Normal

Write-Host "都啟動了：ngrok 和「LINE監聽-熱危害」各一個視窗，關掉視窗就會停止服務。"
