"""
查詢熱危害風險等級並截圖，存到 screenshots/ 資料夾。
截圖之後會由 GitHub Actions 的步驟 commit + push 回 repo，
再讓 send_line_image.py 用 raw.githubusercontent.com 的網址推播給 LINE。

環境變數：
    HEAT_ADDRESS   要查詢的地區，例如 "台北市信義區"（預設見下方）

輸出：
    在 GitHub Actions 環境下，會把截圖的相對路徑寫進 $GITHUB_OUTPUT 的 `path`
    本機執行則直接印在終端機
"""

import os
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

HEAT_ADDRESS = os.environ.get("HEAT_ADDRESS", "台北市信義區")
HEAT_PAGE_URL = "https://hiosha.osha.gov.tw/content/info/heat1.aspx"
SCREENSHOT_DIR = "screenshots"


def capture_heat_risk_screenshot(address: str) -> str:
    """查詢指定地區的熱危害風險等級，截圖存檔，回傳相對路徑"""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(SCREENSHOT_DIR, f"heat_risk_{timestamp}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1024, "height": 900})
        page.goto(HEAT_PAGE_URL, wait_until="networkidle")

        page.fill("#ContentPlaceHolder1_txtAddress", address)
        page.click('input[onclick="QueryGeolocation();"]')

        # 等查詢結果的 AJAX 回來並畫完圖表
        page.wait_for_timeout(2000)

        # .heat-cal 這個區塊包含查詢表單與風險等級量表，取第一個(桌面版)
        result_block = page.locator(".heat-cal").first
        result_block.screenshot(path=save_path)

        browser.close()

    return save_path.replace("\\", "/")


if __name__ == "__main__":
    path = capture_heat_risk_screenshot(HEAT_ADDRESS)
    print(f"截圖完成: {path}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"path={path}\n")
