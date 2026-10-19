"""
用 LINE Messaging API 推播一則文字訊息給指定使用者/群組。

環境變數：
    LINE_CHANNEL_ACCESS_TOKEN  LINE Developers Console -> Messaging API 分頁產生
    LINE_USER_ID               目標使用者或群組的 ID
    TEXT_FILE                  要推播的文字檔路徑（UTF-8）
"""

import os
import sys
from pathlib import Path

import requests

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_line_text(token: str, user_id: str, text: str) -> requests.Response:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }
    return requests.post(LINE_PUSH_URL, headers=headers, json=payload)


if __name__ == "__main__":
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")
    text_file = os.environ.get("TEXT_FILE", "")

    missing = [
        name
        for name, val in [
            ("LINE_CHANNEL_ACCESS_TOKEN", token),
            ("LINE_USER_ID", user_id),
            ("TEXT_FILE", text_file),
        ]
        if not val
    ]
    if missing:
        sys.exit(f"缺少必要設定: {', '.join(missing)}")

    text = Path(text_file).read_text(encoding="utf-8").strip()
    if not text:
        sys.exit(f"{text_file} 是空的，不推播")

    print(f"推播文字:\n{text}")
    resp = send_line_text(token, user_id, text)
    if resp.status_code == 200:
        print("LINE 訊息推播成功")
    else:
        sys.exit(f"LINE 推播失敗，狀態碼: {resp.status_code}\n{resp.text}")
