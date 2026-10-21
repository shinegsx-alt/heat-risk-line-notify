"""
把多張圖片（加上一段文字）合併推播到 LINE，每次 push 最多 5 則訊息。

LINE 的訊息額度是「push 次數 × 收訊人數」計算，同一次 push 裡放 1 則或 5 則都算一次，
所以 7 張圖 + 1 段文字原本要 push 8 次，合併後只要 2 次（5 + 3），額度用量少了約 3/4。

環境變數：
    LINE_CHANNEL_ACCESS_TOKEN  LINE Developers Console -> Messaging API 分頁產生
    LINE_USER_ID               目標使用者或群組的 ID
    IMAGE_URLS                 公開可存取的 HTTPS 圖片網址，一行一個（依序推播）
    TEXT_FILE                  （選填）圖片之後要推播的文字檔路徑（UTF-8）
"""

import os
import sys
from pathlib import Path

import requests

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_MESSAGES_PER_PUSH = 5  # LINE push API 一次最多 5 則


def build_messages(image_urls: list[str], text: str) -> list[dict]:
    messages = [
        {"type": "image", "originalContentUrl": url, "previewImageUrl": url}
        for url in image_urls
    ]
    if text:
        messages.append({"type": "text", "text": text})
    return messages


def chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def push(token: str, user_id: str, messages: list[dict]) -> requests.Response:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    return requests.post(
        LINE_PUSH_URL, headers=headers, json={"to": user_id, "messages": messages}, timeout=30
    )


if __name__ == "__main__":
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")
    image_urls = [u.strip() for u in os.environ.get("IMAGE_URLS", "").splitlines() if u.strip()]
    text_file = os.environ.get("TEXT_FILE", "")

    missing = [
        name
        for name, val in [("LINE_CHANNEL_ACCESS_TOKEN", token), ("LINE_USER_ID", user_id)]
        if not val
    ]
    if missing:
        sys.exit(f"缺少必要設定: {', '.join(missing)}")

    text = Path(text_file).read_text(encoding="utf-8").strip() if text_file else ""
    messages = build_messages(image_urls, text)
    if not messages:
        print("沒有圖片也沒有文字，不推播")
        sys.exit(0)

    batches = chunked(messages, MAX_MESSAGES_PER_PUSH)
    print(f"共 {len(image_urls)} 張圖片{' + 1 段文字' if text else ''}，分 {len(batches)} 次推播")
    for i, batch in enumerate(batches, 1):
        resp = push(token, user_id, batch)
        if resp.status_code != 200:
            sys.exit(f"第 {i}/{len(batches)} 次推播失敗，狀態碼: {resp.status_code}\n{resp.text}")
        print(f"第 {i}/{len(batches)} 次推播成功（{len(batch)} 則）")
