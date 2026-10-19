"""
LINE 群組名稱 ↔ Group ID 對映表。

line_webhook_listener.py 收到 Webhook 事件時會呼叫 record_event()：
  - 官方帳號被拉進群組（join）
  - 群組裡有人傳訊息（message）
都會把該群組記進 line_groups.json，並用 LINE API 查出群組名稱。
官方帳號被移出群組（leave）時會標記為已離開。

查詢 LINE 群組名稱需要 Channel Access Token，從以下來源讀取（先找到先用）：
  1. 環境變數 LINE_CHANNEL_ACCESS_TOKEN
  2. repo 資料夾裡的 line_token.txt（已被 .gitignore 排除，不會進 git）
沒有 Token 也能記錄 Group ID，只是名稱會是空的。

查看對映表：
    python line_groups.py
"""

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

import requests

REPO_DIR = Path(__file__).resolve().parent
GROUPS_PATH = REPO_DIR / "line_groups.json"
TOKEN_PATH = REPO_DIR / "line_token.txt"
GROUP_SUMMARY_URL = "https://api.line.me/v2/bot/group/{group_id}/summary"

_lock = threading.Lock()  # Flask 會用多個執行緒處理 Webhook，寫檔要排隊


def load_token() -> str:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token and TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    return token


def load_groups() -> dict:
    if GROUPS_PATH.exists():
        return json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
    return {}


def fetch_group_name(group_id: str) -> str:
    """用 LINE API 查群組名稱；沒有 Token 或查詢失敗就回傳空字串"""
    token = load_token()
    if not token:
        return ""
    if not token.isascii() or " " in token:
        # 真正的 Token 只會有英數和符號；有中文代表 line_token.txt 還是範例文字
        print("line_token.txt 的內容不是有效的 Token（還是範例文字？），請換成真正的 Channel Access Token")
        return ""
    try:
        resp = requests.get(
            GROUP_SUMMARY_URL.format(group_id=group_id),
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("groupName", "")
        print(f"查詢群組名稱失敗({group_id})，狀態碼: {resp.status_code} {resp.text}")
    except requests.RequestException as e:
        print(f"查詢群組名稱失敗({group_id}): {e}")
    return ""


def record_event(event: dict) -> None:
    """依 Webhook 事件更新對映表；不是群組來源的事件直接略過"""
    source = event.get("source", {})
    if source.get("type") != "group":
        return
    group_id = source.get("groupId")
    if not group_id:
        return

    event_type = event.get("type")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        groups = load_groups()
        entry = groups.get(group_id, {"name": "", "first_seen": now})
        entry["last_seen"] = now
        if event_type == "leave":
            entry["active"] = False
        else:
            entry["active"] = True
            # 剛加入時、或之前沒查到名稱時才查，避免每則訊息都打一次 API；
            # 群組改名後，把官方帳號移出再拉回來就會更新
            if event_type == "join" or not entry["name"]:
                entry["name"] = fetch_group_name(group_id) or entry["name"]
        groups[group_id] = entry
        GROUPS_PATH.write_text(
            json.dumps(groups, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    print(f"群組對映表已更新: {entry['name'] or '(未知名稱)'} = {group_id}（事件: {event_type}）")


def find_group_id(name: str) -> str | None:
    """用群組名稱查 Group ID（只找官方帳號目前還在的群組）"""
    for group_id, entry in load_groups().items():
        if entry.get("active") and entry.get("name") == name:
            return group_id
    return None


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    groups = load_groups()
    if not groups:
        print("對映表是空的：把官方帳號拉進群組，或在已加入的群組裡傳一則訊息就會記錄")
    for group_id, entry in groups.items():
        status = "" if entry.get("active") else "（已離開）"
        print(f"{entry.get('name') or '(未知名稱)'}{status}\t{group_id}\t最後出現 {entry.get('last_seen')}")
