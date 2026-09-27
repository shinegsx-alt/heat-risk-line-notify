"""
臨時除錯用：接收 LINE Webhook，把收到的內容印出來，方便從中找出群組的 Group ID。
只是要抓一次 ID，抓到後就可以關掉，不用長期運行、不需要驗證簽章。

安裝依賴：
    pip install flask

使用方式：
1. python webhook_debug.py            (預設監聽 5000 port)
2. 另開一個終端機，用 ngrok 把這個 port 曝露到公開網址：
       ngrok http 5000
   會得到一個類似 https://xxxx.ngrok-free.app 的網址
3. 到 LINE Developers Console -> 你的 Channel -> Messaging API 分頁
   把 Webhook URL 設成: https://xxxx.ngrok-free.app/callback
   打開 "Use webhook"，可以按旁邊的 "Verify" 測試一次連線
4. 在已經加入官方帳號的群組裡發一則訊息
5. 回來看這支程式的終端機輸出，找 "groupId" 那一行
6. 抓到 ID 後，Ctrl+C 關掉這支程式和 ngrok 即可
"""

from flask import Flask, request
import json

app = Flask(__name__)


@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json(silent=True) or {}
    print("\n===== 收到 LINE Webhook =====")
    print(json.dumps(body, ensure_ascii=False, indent=2))

    for event in body.get("events", []):
        source = event.get("source", {})
        source_type = source.get("type")
        if source_type == "group":
            print(f"\n>>> 找到 Group ID: {source.get('groupId')}")
        elif source_type == "room":
            print(f"\n>>> 找到 Room ID: {source.get('roomId')}")
        elif source_type == "user":
            print(f"\n>>> 這是個人來源，User ID: {source.get('userId')}")

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
