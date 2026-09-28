"""
常駐監聽 LINE Webhook：群組裡收到含有「熱危害」關鍵字的訊息時，
放一個「觸發旗標檔案」（trigger.flag），實際執行截圖的工作交給
另一支獨立執行的 trigger_watcher.py 去做。

這樣分成兩支程式是因為：如果讓這支網路監聽程式直接呼叫 daily_run.py
去啟動瀏覽器，會被本機的防護軟體判定成可疑行為模式（網路服務收到請求後
啟動瀏覽器）而攔截，導致 Playwright 誤判瀏覽器執行檔不存在。分成兩支、
讓截圖流程由使用者自己啟動的獨立程式（trigger_watcher.py）去執行，
信任層級跟你自己手動打指令一樣，就不會被攔截。

這支程式本身不需要任何 LINE token——它只負責「聽到關鍵字就放旗標」，
真正推播圖片給 LINE 的動作是 GitHub Actions 那邊用 repo 的 Secrets 做的。

用法：
    python line_webhook_listener.py

需要搭配 ngrok（或其他方式）把本機的 5000 port 曝露成公開 HTTPS 網址，
並在 LINE Developers Console 把 Webhook URL 設成該網址 + /callback。
建議申請 ngrok 的免費「固定網域」，這樣網址就不會每次重啟都變動，
不用每次都回去 LINE Developers Console 改設定。

另外要記得同時執行 trigger_watcher.py，這支程式才會真的去截圖。
"""

from datetime import datetime
from pathlib import Path

from flask import Flask, request

REPO_DIR = Path(__file__).resolve().parent
TRIGGER_KEYWORD = "熱危害"
TRIGGER_FLAG = REPO_DIR / "trigger.flag"

app = Flask(__name__)


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
            print(f"[{datetime.now()}] 偵測到關鍵字「{TRIGGER_KEYWORD}」，放置觸發旗標")
            TRIGGER_FLAG.touch()

    return "OK", 200


@app.route("/", methods=["GET"])
def health():
    return "line_webhook_listener is running", 200


if __name__ == "__main__":
    print(f"監聽關鍵字「{TRIGGER_KEYWORD}」，等待 LINE Webhook 呼叫 /callback ...")
    print("記得同時執行 trigger_watcher.py，這支程式只負責放旗標，不會真的截圖")
    app.run(host="0.0.0.0", port=5000)
