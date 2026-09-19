import os
import sys
import requests

print("=== 正在啟動 V3.0 直連免圖床穩定版腳本 ===")

# 1. 讀取 LINE 的環境變數密鑰
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")

def send_line_screenshot():
    # 🟢 關鍵：直接將截圖 API 的直連網址當作發送目標（每次 LINE 去抓都是當下的最新圖）
    # width=1280 (地圖全寬), crop=900 (擷取高度避免多餘空白), maxAge=1 (確保完全即時不抓舊快取)
    screenshot_url = "https://thum.io"
    
    url = "https://line.me"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_TO_ID,
        "messages": [
            {
                "type": "image",
                "originalContentUrl": screenshot_url,
                "previewImageUrl": screenshot_url
            }
        ]
    }
    
    print("正在通知 LINE 伺服器擷取職安署熱危害地圖...")
    res = requests.post(url, headers=headers, json=payload)
    print(f"LINE 伺服器回應狀態碼: {res.status_code}")
    
    if res.status_code == 200:
        print("任務成功完成！LINE 已成功排程發送圖片。")
    else:
        print(f"發送失敗，詳細錯誤原因: {res.text}")
        sys.exit(1)

if __name__ == "__main__":
    send_line_screenshot()
