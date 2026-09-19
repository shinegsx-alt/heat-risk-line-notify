import os
import sys
import requests

# 版本戳記：V2.0_FINAL_STABLE
print("=== 正在啟動 V2.0 終極穩定版截圖腳本 ===")

# 1. 讀取環境變數
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")

def get_screenshot_via_api():
    print("正在請求職安署地圖截圖...")
    
    # 🟢 修正：不再使用任何變數拼接！直接寫死整條 API 網址，防範任何字串錯亂
    api_url = "https://thum.io"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        return response.content
    else:
        print(f"網頁截圖失敗，API 狀態碼: {response.status_code}")
        sys.exit(1)

def upload_to_telegraph(img_bytes):
    print("正在將截圖上傳至 Telegraph 圖床...")
    url = "https://telegra.ph"
    files = {"file": ("screenshot.png", img_bytes, "image/png")}
    
    response = requests.post(url, files=files)
    try:
        res_json = response.json()
        if isinstance(res_json, list) and len(res_json) > 0:
            file_path = res_json[0]["src"]  # 🟢 修正：精準讀取陣列中第一個字典的 src 欄位
            return f"https://telegra.ph{file_path}"
        else:
            print(f"Telegraph 上傳失敗，回傳內容: {res_json}")
            sys.exit(1)
    except Exception as e:
        print(f"解析 Telegraph 失敗: {e}, 內容: {response.text}")
        sys.exit(1)

def send_line_image(image_url):
    print("正在透過 LINE 發送圖片...")
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
                "originalContentUrl": image_url,
                "previewImageUrl": image_url
            }
        ]
    }
    res = requests.post(url, headers=headers, json=payload)
    print(f"LINE 發送結果狀態碼: {res.status_code}")

if __name__ == "__main__":
    try:
        img_bytes = get_screenshot_via_api()
        public_url = upload_to_telegraph(img_bytes)
        print(f"圖片直連網址: {public_url}")
        send_line_image(public_url)
        print("任務成功完成！")
    except Exception as e:
        print(f"執行發生錯誤: {e}")
