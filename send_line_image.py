"""
用 LINE Messaging API 推播一張圖片訊息給指定使用者。

環境變數：
    LINE_CHANNEL_ACCESS_TOKEN  LINE Developers Console -> Messaging API 分頁產生
    LINE_USER_ID               目標使用者的 LINE User ID（需已加官方帳號為好友）
    IMAGE_URL                  公開可存取的 HTTPS 圖片網址（LINE 伺服器需要能直接抓到）
"""

import os
import sys

import requests

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_line_image(token: str, user_id: str, image_url: str) -> requests.Response:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "image",
                "originalContentUrl": image_url,
                "previewImageUrl": image_url,
            }
        ],
    }
    return requests.post(LINE_PUSH_URL, headers=headers, json=payload)


if __name__ == "__main__":
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")
    image_url = os.environ.get("IMAGE_URL", "")

    missing = [
        name
        for name, val in [
            ("LINE_CHANNEL_ACCESS_TOKEN", token),
            ("LINE_USER_ID", user_id),
            ("IMAGE_URL", image_url),
        ]
        if not val
    ]
    if missing:
        sys.exit(f"缺少必要設定: {', '.join(missing)}")

    print(f"圖片網址: {image_url}")
    resp = send_line_image(token, user_id, image_url)
    if resp.status_code == 200:
        print("LINE 訊息推播成功")
    else:
        sys.exit(f"LINE 推播失敗，狀態碼: {resp.status_code}\n{resp.text}")
