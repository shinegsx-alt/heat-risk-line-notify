"""
LINE Messaging API - 推播訊息 (Push Message) 範例

使用前準備：
1. 到 LINE Developers Console (https://developers.line.biz/) 建立 Messaging API Channel
2. 取得 Channel Access Token (長期權杖，在 Channel 設定的 "Messaging API" 分頁產生)
3. 取得目標使用者的 User ID (使用者需先加該官方帳號為好友；
   User ID 可透過 Webhook 事件、或 LINE Login 取得)

安裝依賴：
    pip install requests
"""

import requests

CHANNEL_ACCESS_TOKEN = "HFhEvnFz10SgLQFR8EzFg+L2j6qkrN1baY6mkEugbUg4F+OJ/YG/2X/7gVUf4LqMH4mA5jzXp/qomyNNjKTnTk7hizCnVvL6g+HlWzlt5k/cYQBDPi27dHdFf+88NNu7tQwz4squkbMd9h6sU5FDZQdB04t89/1O/w1cDnyilFU="
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_line_message(user_id: str, message: str) -> requests.Response:
    """傳送純文字訊息給指定的 LINE user_id"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "to": user_id,
        "messages": [
            {"type": "text", "text": message}
        ],
    }

    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return response


if __name__ == "__main__":
    target_user_id = "目標使用者的_USER_ID"
    text = "這是一則測試訊息！"

    resp = send_line_message(target_user_id, text)

    if resp.status_code == 200:
        print("訊息傳送成功")
    else:
        print(f"傳送失敗，狀態碼: {resp.status_code}")
        print(resp.text)
