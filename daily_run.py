"""
每天早上定時執行的主流程，由本機的 Windows 工作排程器觸發（政府網站會擋掉
GitHub Actions 雲端機房的 IP，所以「截圖」這段一定要在本機、台灣網路環境下執行）。

流程：
1. 對 LOCATIONS 裡的每個地點截圖（iPhone 版面），存成 screenshots/<日期>-<地點>.jpg
2. git add + commit + push 回 GitHub
3. push 之後，GitHub Actions 的 .github/workflows/send-line-on-push.yml
   會自動偵測到新截圖，逐一推播到 LINE 群組（那一段是在雲端執行，
   因為只是連 github.com/line.me，不會被政府網站的防火牆擋到）

用法：
    python daily_run.py
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_DIR = Path(__file__).resolve().parent
HEAT_PAGE_URL = "https://hiosha.osha.gov.tw/content/info/heat1.aspx"
LOCATIONS = ["宜蘭", "礁溪"]
SCREENSHOT_DIR = REPO_DIR / "screenshots"

# winget 裝的 Git 預設路徑；如果之後 'git' 指令本身在 PATH 裡可以用了，
# 改回 GIT = "git" 也可以
GIT = r"C:\Program Files\Git\cmd\git.exe"


def capture_one(browser, iphone_device: dict, address: str, save_path: Path):
    page = browser.new_page(**iphone_device)
    try:
        page.goto(HEAT_PAGE_URL, wait_until="domcontentloaded")
        page.wait_for_selector("#ContentPlaceHolder1_txtAddressPhone", state="visible", timeout=30000)
        page.fill("#ContentPlaceHolder1_txtAddressPhone", address)
        page.click('input[onclick="QueryGeolocationPhone();"]')
        # 等查詢結果的 AJAX 回來並畫完圖表
        page.wait_for_timeout(2000)
        # .heat-cal 這個區塊包含查詢表單與風險等級量表（手機/桌面共用同一個容器，
        # 由 CSS media query 切換顯示哪一版）
        result_block = page.locator(".heat-cal").first
        result_block.screenshot(path=str(save_path), type="jpeg", quality=90)
    finally:
        page.close()


def capture_all() -> list[Path]:
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    saved = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        iphone_device = p.devices["iPhone 13"]
        for loc in LOCATIONS:
            save_path = SCREENSHOT_DIR / f"{date_str}-{loc}.jpg"
            capture_one(browser, iphone_device, loc, save_path)
            print(f"截圖完成: {save_path}")
            saved.append(save_path)
        browser.close()
    return saved


def run(cmd: list[str]):
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True, encoding="utf-8")
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"指令失敗: {' '.join(cmd)}")


def git_commit_and_push(paths: list[Path]):
    rel_paths = [str(p.relative_to(REPO_DIR)) for p in paths]
    run([GIT, "add", *rel_paths])

    diff_check = subprocess.run([GIT, "diff", "--cached", "--quiet"], cwd=REPO_DIR)
    if diff_check.returncode == 0:
        print("沒有新變更，不需要 commit")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    run([GIT, "commit", "-m", f"熱危害風險等級截圖 {date_str}"])
    run([GIT, "push"])


if __name__ == "__main__":
    saved_paths = capture_all()
    git_commit_and_push(saved_paths)
    print("完成：已推送截圖，接下來由 GitHub Actions 自動推播到 LINE 群組")
