"""
測試用：截圖一個不會被擋的公開網站，驗證「截圖 -> commit/push -> LINE 推播」
這條流程本身是通的，跟 hiosha.osha.gov.tw 連不連得到無關。

等 GitHub Actions 執行環境的問題解決後，把 workflow 裡呼叫的檔名
從 capture_screenshot_test.py 換回 capture_screenshot.py 即可，
其他步驟(commit/push/LINE推播)完全不用改。
"""

import os
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

TEST_URL = "https://www.wikipedia.org"
SCREENSHOT_DIR = "screenshots"


def capture_test_screenshot() -> str:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(SCREENSHOT_DIR, f"test_{timestamp}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1024, "height": 768})
        page.goto(TEST_URL, wait_until="load", timeout=30000)
        page.screenshot(path=save_path)
        browser.close()

    return save_path.replace("\\", "/")


if __name__ == "__main__":
    path = capture_test_screenshot()
    print(f"截圖完成: {path}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"path={path}\n")
