# 部署到新電腦

GitHub repo（`https://github.com/shinegsx-alt/heat-risk-line-notify`）不用動，
Secrets（`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID`）跟雲端的
`send-line-on-push.yml` 都已經設好，新機器只是換一個「本機截圖 + 觸發」的地方。

## A. 新電腦要裝的軟體

### 1. Python
- https://www.python.org/downloads/windows/ 下載安裝
- **安裝時務必勾選「Add python.exe to PATH」**
- 裝完重開終端機，確認：`python --version`

### 2. Git for Windows
```bash
winget install --id Git.Git -e --source winget
```
裝完重開終端機，確認：`git --version`

### 3. Python 套件
```bash
pip install playwright requests flask
python -m playwright install chromium
```
（`playwright install chromium` 會下載約 150MB 的瀏覽器核心，務必等它完整跑完）

### 4. ngrok
- https://ngrok.com/download 下載
- 登入**同一個 ngrok 帳號**（`shinegsx@gmail.com`），執行：
```bash
ngrok config add-authtoken 你的authtoken
```
- 固定網域是綁在帳號上、不是綁在機器上，同帳號登入即可沿用之前申請的固定網域，
  **LINE Developers Console 的 Webhook URL 不用改**

## B. Clone 專案

```bash
git clone https://github.com/shinegsx-alt/heat-risk-line-notify.git
cd heat-risk-line-notify
```

第一次 push 會跳出瀏覽器要求登入 GitHub 帳號做一次性授權：
```bash
git commit --allow-empty -m "test"
git push
```
授權完成後，之後自動觸發的 push 都不用再登入。

## C. LINE 帳號設定

**如果延用現有的 LINE 官方帳號 → 這整節可以跳過。**

只有要換成全新官方帳號時才需要：

1. 建立 LINE 官方帳號：https://www.linebiz.com/tw/service/line-official-account/
2. 建立 Messaging API Channel：https://developers.line.biz/console/
3. Channel 頁面 → Messaging API 分頁 → 發行長期 Channel Access Token
4. LINE Official Account Manager（https://manager.line.biz/）→ 設定 → 回應設定 →
   「加入群組・多人聊天室」設為允許
5. 把官方帳號拉進目標 LINE 群組
6. 用 `webhook_debug.py` + ngrok 抓一次 Group ID
7. 到 GitHub repo 的 Settings → Secrets and variables → Actions，設定
   `LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID`（填群組 ID）

## D. 設定固定網域檔案

在 repo 資料夾建立 `ngrok_domain.txt`（已被 .gitignore 排除，不會進 git），
內容只填一行，你的 ngrok 固定網域（不要加 `https://`），可以複製
`ngrok_domain.txt.example` 改檔名再填入實際網域。

## E. 手動測試

```bash
.\start_services.ps1
```
這支腳本會背景啟動 ngrok 和 `line_webhook_listener.py`（不開視窗），
輸出分別存在 `logs\ngrok_out.log` 和 `logs\listener_out.log`。

在 LINE 群組打「熱危害」測試，確認：
1. `logs\listener_out.log` 出現「偵測到關鍵字...」
2. 約 1-2 分鐘後截圖 7 張完成、push 成功
3. LINE 群組收到 7 張圖

## F. 設定開機自動啟動

確認手動測試沒問題後：
```bash
.\setup_autostart.ps1
```
這會註冊一個 Windows 工作排程器任務「熱危害LINE監聽服務」，
之後每次**登入**這台電腦，就會自動背景啟動 ngrok + 監聽程式，不用手動再開視窗。

移除自動啟動：
```powershell
Unregister-ScheduledTask -TaskName "熱危害LINE監聽服務" -Confirm:$false
```

## G. 舊電腦收尾

舊電腦上的 ngrok 和 `line_webhook_listener.py` 記得停掉，避免兩台電腦同時搶著
回應同一個 Webhook URL（ngrok 免費帳號同時間通常也只能有一個 tunnel 在跑）。
如果舊電腦有設定過開機自動啟動，也要一併 `Unregister-ScheduledTask` 移除。
