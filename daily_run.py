"""
查詢+推播的主流程。由 line_webhook_listener.py 在 LINE 群組收到「熱危害」關鍵字時
呼叫（也可以手動執行測試）。截圖一定要在本機、台灣網路環境下執行，因為政府網站會
擋掉 GitHub Actions 雲端機房的 IP。

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
import time
from datetime import datetime
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

REPO_DIR = Path(__file__).resolve().parent
HEAT_PAGE_URL = "https://hiosha.osha.gov.tw/content/info/heat1.aspx"
GITHUB_OWNER = "shinegsx-alt"
GITHUB_REPO = "heat-risk-line-notify"
# 對應 .github/workflows/send-line-on-push.yml 裡的 name
WORKFLOW_NAME = "新截圖推播到LINE群組"
# (顯示用短名稱, 拿去網站查詢的完整地址)
# 地址太模糊會被地理定位猜錯地方（例如單打「宜蘭」曾經被猜成三星鄉），
# 所以查詢一律用完整縣市+鄉鎮市區名稱，檔名再用短名稱
LOCATIONS = [
    ("宜蘭市", "宜蘭縣宜蘭市"),
    ("員山鄉", "宜蘭縣員山鄉"),
    ("壯圍鄉", "宜蘭縣壯圍鄉"),
    ("大同鄉", "宜蘭縣大同鄉"),
    ("三星鄉", "宜蘭縣三星鄉"),
    ("礁溪鄉", "宜蘭縣礁溪鄉"),
    ("頭城鎮", "宜蘭縣頭城鎮"),
]
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
        for display_name, query_address in LOCATIONS:
            save_path = SCREENSHOT_DIR / f"{date_str}-{display_name}.jpg"
            capture_one(browser, iphone_device, query_address, save_path)
            print(f"截圖完成: {save_path}")
            saved.append(save_path)
        browser.close()
    return saved


def run(cmd: list[str]):
    print("$", " ".join(cmd))
    result = subprocess.run(
        cmd, cwd=REPO_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"指令失敗: {' '.join(cmd)}")


def git_commit_and_push(paths: list[Path]) -> str | None:
    """commit+push，回傳這次 push 的 commit SHA；沒有新變更則回傳 None"""
    rel_paths = [str(p.relative_to(REPO_DIR)) for p in paths]
    run([GIT, "add", *rel_paths])

    diff_check = subprocess.run([GIT, "diff", "--cached", "--quiet"], cwd=REPO_DIR)
    if diff_check.returncode == 0:
        print("沒有新變更，不需要 commit")
        return None

    date_str = datetime.now().strftime("%Y-%m-%d")
    run([GIT, "commit", "-m", f"熱危害風險等級截圖 {date_str}"])
    run([GIT, "push"])

    sha_result = subprocess.run(
        [GIT, "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True
    )
    return sha_result.stdout.strip()


def wait_for_workflow_completion(sha: str, timeout: int = 300, poll_interval: int = 5) -> None:
    """輪詢 GitHub API，等這個 commit 觸發的推播 workflow 真的跑完（成功或失敗都算完成），
    這樣才能確保「整個抓圖到貼圖」的流程結束後，才把鎖釋放讓下一次關鍵字觸發可以進來。
    （這是 repo 的 public 唯讀 API，不需要 token；查不到/逾時就直接放行，不會卡死整支程式）
    """
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs"
    deadline = time.monotonic() + timeout
    print(f"等待 GitHub Actions 推播 workflow 執行完畢(commit {sha[:7]})...")

    while time.monotonic() < deadline:
        try:
            resp = requests.get(api_url, params={"head_sha": sha}, timeout=10)
            resp.raise_for_status()
            runs = [
                r for r in resp.json().get("workflow_runs", [])
                if r.get("name") == WORKFLOW_NAME
            ]
            if runs:
                if all(r.get("status") == "completed" for r in runs):
                    conclusions = [r.get("conclusion") for r in runs]
                    print(f"推播 workflow 已完成，結果: {conclusions}")
                    return
        except requests.RequestException as e:
            print(f"查詢 GitHub Actions 狀態失敗（略過，繼續等待）: {e}")

        time.sleep(poll_interval)

    print("等待 GitHub Actions 逾時，直接繼續（可能仍在背景執行）")


if __name__ == "__main__":
    saved_paths = capture_all()
    pushed_sha = git_commit_and_push(saved_paths)
    if pushed_sha:
        wait_for_workflow_completion(pushed_sha)
        print("完成：截圖已推送，GitHub Actions 的 LINE 推播也已執行完畢")
    else:
        print("完成：這次沒有新截圖需要推送")
