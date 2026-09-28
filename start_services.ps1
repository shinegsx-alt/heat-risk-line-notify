# 背景啟動 ngrok + line_webhook_listener.py（不開視窗，輸出導向 logs/ 資料夾）
# 給開機自動啟動用，也可以手動執行測試。
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

Write-Host "啟動 ngrok（網域: $domain）..."
Start-Process -FilePath "ngrok" `
    -ArgumentList "http", "5000", "--domain=$domain" `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "ngrok_out.log") `
    -RedirectStandardError (Join-Path $logDir "ngrok_err.log")

Start-Sleep -Seconds 3

Write-Host "啟動 line_webhook_listener.py ..."
Start-Process -FilePath "python" `
    -ArgumentList (Join-Path $repoDir "line_webhook_listener.py") `
    -WorkingDirectory $repoDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "listener_out.log") `
    -RedirectStandardError (Join-Path $logDir "listener_err.log")

Write-Host "都啟動了（背景執行，沒有視窗）。可以看 logs\ngrok_out.log 和 logs\listener_out.log 確認狀態。"
