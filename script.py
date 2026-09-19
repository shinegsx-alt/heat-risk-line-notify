import os
import sys
import requests
from playwright.sync_api import sync_playwright

# 從環境變數讀取敏感憑證
IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")  # 你的 User ID 或 Group ID
TARGET_URL = "https://hiosha.osha.gov.tw/content/info/heat1.aspx"        # ◀◀ 更改為你要截圖的網頁網址

def take_screenshot():
    print("正在啟動瀏覽器...")
    with sync_playwright() as p:
        # 啟動無頭瀏覽器
        browser = p.chromium.launch(headless=True)
        # 設定視窗大小（可依網頁版面調整，如 RWD 網頁）
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        print(f"正在前往網頁: {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="networkidle") # 等待網路讀取完畢
        
        # 選擇性：如果網頁有彈出視窗、Cookie 同意視窗，可在這裡加入點擊程式碼
        # page.click("button#accept-cookie") 
        
        # 執行截圖，並存入記憶體中
        print("執行網頁截圖...")
        screenshot_bytes = page.screenshot(full_page=True) # full_page=True 會擷取整頁，False 只擷取當前視窗
        browser.close()
        return screenshot_bytes

def upload_to_imgur(img_bytes):
    print("正在將截圖上傳至 Imgur...")
    url = "https://imgur.com"
    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
    files = {"image": img_bytes}
    
    response = requests.post(url, headers=headers, files=files)
    if response.status_dict().get("success") or response.json().get("success"):
        return response.json()["data"]["link"]
    else:
        print(f"Imgur 上傳失敗: {response.text}")
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
        img_bytes = take_screenshot()
        public_url = upload_to_imgur(img_bytes)
        print(f"圖片直連網址: {public_url}")
        send_line_image(public_url)
        print("任務成功完成！")
    except Exception as e:
        print(f"執行發生錯誤: {e}")
