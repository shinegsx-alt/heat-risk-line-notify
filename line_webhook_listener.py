"""
常駐監聽 LINE Webhook：群組裡收到含有「熱危害」關鍵字的訊息時，
觸發本機的 daily_run.py（截圖 7 個鄉鎮市 + push 到 GitHub），
push 之後由 GitHub Actions 自動把截圖推播回 LINE 群組
（見 .github/workflows/send-line-on-push.yml）。

這支程式本身不需要任何 LINE token——它只負責「聽到關鍵字就觸發本機截圖流程」，
真正推播圖片給 LINE 的動作是 GitHub Actions 那邊用 repo 的 Secrets 做的。

用法：
    python line_webhook_listener.py

需要搭配 ngrok（或其他方式）把本機的 5000 port 曝露成公開 HTTPS 網址，
並在 LINE Developers Console 把 Webhook URL 設成該網址 + /callback。
建議申請 ngrok 的免費「固定網域」，這樣網址就不會每次重啟都變動，
不用每次都回去 LINE Developers Console 改設定。
"""

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, request

REPO_DIR = Path(__file__).resolve().parent
TRIGGER_KEYWORD = "熱危害"

app = Flask(__name__)
_running = threading.Lock()  # 避免同時觸發兩次截圖流程，重複的觸發會被忽略


def run_daily_task():
    if not _running.acquire(blocking=False):
        print("已經有一個任務在執行中，這次觸發被忽略")
        return
    try:
        print(f"[{datetime.now()}] 開始執行 daily_run.py ...")
        # 用獨立的新主控台視窗執行（而不是用管線捕捉輸出），
        # 避免從 Flask 背景執行緒用管線重導向啟動 Playwright 瀏覽器時，
        # Windows 底層巢狀管線+無主控台的情境下出現奇怪的進程建立失敗
        process = subprocess.Popen(
            [sys.executable, str(REPO_DIR / "daily_run.py")],
            cwd=REPO_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        process.wait()
        print(f"[{datetime.now()}] daily_run.py 執行完畢，returncode={process.returncode}")
    finally:
        _running.release()


@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json(silent=True) or {}
    for event in body.get("events", []):
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        text = message.get("text", "")
        if TRIGGER_KEYWORD in text:
            print(f"偵測到關鍵字「{TRIGGER_KEYWORD}」，觸發截圖流程")
            threading.Thread(target=run_daily_task, daemon=True).start()

    return "OK", 200


@app.route("/", methods=["GET"])
def health():
    return "line_webhook_listener is running", 200


if __name__ == "__main__":
    print(f"監聽關鍵字「{TRIGGER_KEYWORD}」，等待 LINE Webhook 呼叫 /callback ...")
    app.run(host="0.0.0.0", port=5000)
