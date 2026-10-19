"""
常駐監聽 LINE Webhook：群組裡收到含有「熱危害」關鍵字的訊息時，
先執行 heat_6h_max.py（三個群組未來 6 小時最高等級，結果寫進 heat_result.txt），
再觸發本機的 daily_run.py（截圖 7 個鄉鎮市 + 連同 heat_result.txt push 到 GitHub），
push 之後由 GitHub Actions 自動把截圖、接著把等級文字推播回「觸發關鍵字的那個群組」
（見 .github/workflows/send-line-on-push.yml）。

另外，所有群組事件都會記進群組名稱 ↔ ID 對映表 line_groups.json（見 line_groups.py）。

推播圖片給 LINE 的動作是 GitHub Actions 那邊用 repo 的 Secrets 做的；
本機的 LINE Token（line_token.txt）只用來查群組名稱，沒有也不影響截圖流程。

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

import line_groups
from send_line_text import send_line_text

REPO_DIR = Path(__file__).resolve().parent
TRIGGER_KEYWORD = "熱危害"
LOG_DIR = REPO_DIR / "logs"
HEAT_RESULT_PATH = REPO_DIR / "heat_result.txt"
# 這次是哪個群組觸發的；daily_run.py 會跟截圖一起 commit，GitHub Actions 就推播回這個群組
LINE_TARGET_PATH = REPO_DIR / "line_target.txt"

app = Flask(__name__)
_running = threading.Lock()  # 避免同時觸發兩次截圖流程，重複的觸發會被忽略


def run_heat_level(log_file) -> None:
    """執行 heat_6h_max.py，把結果文字寫進 heat_result.txt；
    daily_run.py 會把它跟截圖一起 commit，GitHub Actions 推播完圖片後再把這段文字推到群組。
    查詢失敗就不更新檔案，這次就不會推播文字（截圖照常進行）。"""
    print(f"[{datetime.now()}] 開始執行 heat_6h_max.py ...")
    result = subprocess.run(
        [sys.executable, str(REPO_DIR / "heat_6h_max.py")],
        cwd=REPO_DIR,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    log_file.write(f"---- heat_6h_max.py (returncode={result.returncode}) ----\n")
    log_file.write(result.stdout + result.stderr + "\n")
    log_file.flush()
    if result.returncode == 0 and result.stdout.strip():
        HEAT_RESULT_PATH.write_text(result.stdout.strip() + "\n", encoding="utf-8")
        print(f"熱危害等級結果已寫入 {HEAT_RESULT_PATH.name}")
    else:
        print("heat_6h_max.py 執行失敗，這次不推播熱危害等級文字")


def notify_busy(target: str) -> None:
    """流程正在跑別的群組的請求時，告訴這個群組稍後再試（本機沒有 Token 就只印 log）"""
    token = line_groups.load_token()
    if not target or not token or not token.isascii():
        return
    try:
        send_line_text(token, target, "目前正在處理另一個查詢，請 1～2 分鐘後再傳一次「熱危害」")
    except Exception as e:
        print(f"通知群組稍後再試失敗: {e}")


def run_daily_task(target: str):
    if not _running.acquire(blocking=False):
        print("已經有一個任務在執行中，這次觸發被忽略")
        notify_busy(target)
        return
    try:
        if target:
            # 第二行是觸發時間，確保每次觸發檔案內容都不同，workflow 才會判斷「這次有指定推播對象」
            LINE_TARGET_PATH.write_text(
                f"{target}\n{datetime.now():%Y-%m-%d %H:%M:%S}\n", encoding="utf-8"
            )
        LOG_DIR.mkdir(exist_ok=True)
        log_path = LOG_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        # 把子程序輸出導向真正的檔案，這樣不管執行結果如何都能回頭查看發生了什麼事
        with open(log_path, "w", encoding="utf-8") as log_file:
            run_heat_level(log_file)
            print(f"[{datetime.now()}] 開始執行 daily_run.py ...")
            log_file.write("---- daily_run.py ----\n")
            log_file.flush()
            process = subprocess.Popen(
                [sys.executable, str(REPO_DIR / "daily_run.py")],
                cwd=REPO_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            process.wait()
        print(
            f"[{datetime.now()}] daily_run.py 執行完畢，"
            f"returncode={process.returncode}，log: {log_path}"
        )
        if process.returncode != 0:
            print(f"發生錯誤！請查看 log 檔案內容: {log_path}")
    finally:
        _running.release()


@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json(silent=True) or {}
    for event in body.get("events", []):
        # 不管是不是關鍵字，群組事件都記進群組名稱 ↔ ID 對映表
        try:
            line_groups.record_event(event)
        except Exception as e:
            print(f"更新群組對映表失敗: {e}")

        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        text = message.get("text", "")
        if TRIGGER_KEYWORD in text:
            source = event.get("source", {})
            # 群組 → groupId、多人聊天室 → roomId、私訊 → userId，結果就推播回同一個地方
            target = source.get("groupId") or source.get("roomId") or source.get("userId") or ""
            print(f"偵測到關鍵字「{TRIGGER_KEYWORD}」，觸發截圖流程（推播對象: {target or '預設'}）")
            threading.Thread(target=run_daily_task, args=(target,), daemon=True).start()

    return "OK", 200


@app.route("/", methods=["GET"])
def health():
    return "line_webhook_listener is running", 200


if __name__ == "__main__":
    print(f"監聽關鍵字「{TRIGGER_KEYWORD}」，等待 LINE Webhook 呼叫 /callback ...")
    app.run(host="0.0.0.0", port=5000)
