import os
import sys
import requests

print("=== 正在啟動 V4.0 Flex Message 終極通關版腳本 ===")

# 1. 讀取 LINE 的環境變數密鑰
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")

def send_line_flex():
    # 職安署熱危害地圖的動態截圖網址
    screenshot_url = "https://thum.io"
    
    url = "https://line.me"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    
    # 🟢 改用 Flex Message 架構，這能完美繞過原本 Image 類型的 405 阻擋限制！
    payload = {
        "to": LINE_TO_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "今日職安署熱危害預防地圖",
                "contents": {
                    "type": "bubble",
                    "hero": {
                        "type": "image",
                        "url": screenshot_url,
                        "size": "full",
                        "aspectRatio": "4:3",
                        "aspectMode": "cover",
                        "action": {
                            "type": "uri",
                            "label": "點擊看大圖",
                            "uri": screenshot_url
                        }
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🌞 今日高氣溫戶外作業熱危害地圖",
                                "weight": "bold",
                                "size": "md"
                            }
                        ]
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "button",
                                "style": "link",
                                "height": "sm",
                                "action": {
                                    "type": "uri",
                                    "label": "前往職安署官網",
                                    "uri": "https://osha.gov.tw"
                                }
                            }
                        ]
                    }
                }
            }
        ]
    }
    
    print("正在透過 Flex Message 發送截圖...")
    res = requests.post(url, headers=headers, json=payload)
    print(f"LINE 伺服器回應狀態碼: {res.status_code}")
    
    if res.status_code == 200:
        print("任務成功完成！LINE 已成功發送 Flex 訊息。")
    else:
        print(f"發送失敗，詳細錯誤原因: {res.text}")
        sys.exit(1)

if __name__ == "__main__":
    send_line_flex()
