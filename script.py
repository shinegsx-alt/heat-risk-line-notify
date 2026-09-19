import os
import sys
import requests

# 從環境變數讀取敏感憑證
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")
TARGET_URL = "https://example.com"  # ◀◀ 更改為你要截圖的網頁網址

def get_screenshot_via_api():
    print(f"正在透過免費 API 擷取網頁: {TARGET_URL} ...")
    
    # 使用免費且穩定的 screenshotlayer API (免註冊直接使用的匿名模式)
    # 或者使用 flashapi 的免費截圖服務
    api_url = f"https://apiflash.com{TARGET_URL}&width=1280&height=800&fresh=true"
    
    # 另一組備用免密鑰 API (如果上面那組不穩，可以換這組)：
    # api_url = f"https://thum.io{TARGET_URL}"
    
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.content
    else:
        print(f"網頁截圖失敗，API 狀態碼: {response.status_code}")
        sys.exit(1)

def upload_to_telegraph(img_bytes):
    print("正在將截圖上傳至 Telegraph...")
    url = "https://telegra.ph"
    files = {"file": ("screenshot.png", img_bytes, "image/png")}
    
    response = requests.post(url, files=files)
    try:
        res_json = response.json()
        if isinstance(res_json, list) and len(res_json) > 0:
            file_path = res_json[0]["src"] # 修正：Telegraph 回傳的物件在陣列第一項
            return f"https://telegra.ph{file_path}"
        else:
            print(f"Telegraph 上傳失敗: {res_json}")
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
