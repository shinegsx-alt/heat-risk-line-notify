"""
每天早上 07:00 由 Windows 工作排程器執行（見 setup_morning_task.ps1），
把熱危害截圖 + 三群組未來 6 小時最高等級推播到「宜陽巡路隊」群組。

跟群組打「熱危害」觸發的流程一樣（heat_6h_max.py → daily_run.py → GitHub Actions 推播），
差別是推播對象固定為 TARGET_GROUP_NAME，而且會開一個看得見的視窗，
每個步驟、每行輸出都即時顯示，跑完會停在畫面上，方便確認狀態。
同樣的內容也會存一份到 logs/morning_YYYYMMDD_HHMMSS.log。

群組 ID 從 line_groups.json 查（群組名稱 ↔ ID 對映表，見 line_groups.py）。

用法：
    python morning_run.py            正式執行（會截圖、push、推播到群組）
    python morning_run.py --dry-run  只查群組 ID 和熱危害等級，不截圖、不 push、不推播
"""

import msvcrt
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import line_groups
from run_lock import RunLock

REPO_DIR = Path(__file__).resolve().parent
LOG_DIR = REPO_DIR / "logs"
HEAT_RESULT_PATH = REPO_DIR / "heat_result.txt"
LINE_TARGET_PATH = REPO_DIR / "line_target.txt"

TARGET_GROUP_NAME = "宜陽巡路隊"
# 剛好有群組觸發的流程在跑時，最多等這麼久再放棄（截圖+推播一輪約 2～3 分鐘）
LOCK_WAIT_SECONDS = 10 * 60
# 跑完後視窗停留多久自動關閉（期間按任意鍵可以立刻關閉）
KEEP_WINDOW_SECONDS = 60 * 60

_log_file = None


def log(msg: str = "") -> None:
    """同時印到視窗和寫進 log 檔"""
    line = f"[{datetime.now():%H:%M:%S}] {msg}" if msg else ""
    print(line, flush=True)
    if _log_file:
        _log_file.write(line + "\n")
        _log_file.flush()


def step(title: str) -> None:
    log()
    log(f"===== {title} =====")


def run_and_stream(script: str) -> tuple[int, str]:
    """執行 repo 裡的 Python 腳本，輸出一行一行即時顯示；回傳 (returncode, 標準輸出全文)"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    process = subprocess.Popen(
        [sys.executable, str(REPO_DIR / script)],
        cwd=REPO_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    lines = []
    for line in process.stdout:
        line = line.rstrip("\r\n")
        lines.append(line)
        log(f"  {line}")
    process.wait()
    return process.returncode, "\n".join(lines)


def wait_for_lock(lock: RunLock) -> bool:
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    if lock.try_acquire():
        return True
    log("另一個截圖流程正在執行（可能是群組剛好打了「熱危害」），等它跑完...")
    while time.monotonic() < deadline:
        time.sleep(10)
        if lock.try_acquire():
            log("已輪到這次執行")
            return True
    return False


def main(dry_run: bool) -> bool:
    step(f"每日 07:00 熱危害推播 → {TARGET_GROUP_NAME}" + ("（測試模式，不推播）" if dry_run else ""))

    step("1/4 查詢群組 ID")
    group_id = line_groups.find_group_id(TARGET_GROUP_NAME)
    if not group_id:
        log(f"✗ 在 line_groups.json 找不到「{TARGET_GROUP_NAME}」")
        log("  請在該群組隨便傳一則訊息讓 listener 記錄，或執行 python line_groups.py 確認名稱")
        return False
    log(f"✓ {TARGET_GROUP_NAME} = {group_id[:6]}…")

    lock = RunLock()
    if not dry_run and not wait_for_lock(lock):
        log(f"✗ 等了 {LOCK_WAIT_SECONDS // 60} 分鐘還在忙，這次放棄")
        return False
    try:
        step("2/4 查詢未來 6 小時熱危害等級（約 20 秒）")
        code, output = run_and_stream("heat_6h_max.py")
        if code == 0 and output.strip():
            log("✓ 等級查詢完成")
            if not dry_run:
                HEAT_RESULT_PATH.write_text(output.strip() + "\n", encoding="utf-8")
        else:
            log(f"✗ 等級查詢失敗（returncode={code}），這次只推播截圖、不附文字")

        if dry_run:
            log()
            log("測試模式：到這裡為止，不截圖、不 push、不推播")
            return code == 0

        step("3/4 截圖 7 個鄉鎮 + push 到 GitHub")
        # 第二行是時間，確保每次內容都不同，workflow 才會採用這個推播對象
        LINE_TARGET_PATH.write_text(
            f"{group_id}\n{datetime.now():%Y-%m-%d %H:%M:%S}\n", encoding="utf-8"
        )
        code, _ = run_and_stream("daily_run.py")
        if code != 0:
            log(f"✗ daily_run.py 失敗（returncode={code}），請看上面的訊息")
            return False

        step("4/4 完成")
        log(f"✓ 截圖已 push，GitHub Actions 已推播到「{TARGET_GROUP_NAME}」")
        log("  如果群組沒收到，到 GitHub → Actions 看最新一次「新截圖推播到LINE群組」的紀錄")
        return True
    finally:
        lock.release()


def keep_window_open() -> None:
    """排程開出來的視窗跑完會直接關掉，所以停在畫面上讓人看結果"""
    print(f"\n視窗會在 {KEEP_WINDOW_SECONDS // 60} 分鐘後自動關閉，按任意鍵可以立刻關閉...", flush=True)
    deadline = time.monotonic() + KEEP_WINDOW_SECONDS
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            msvcrt.getwch()
            return
        time.sleep(0.2)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dry_run = "--dry-run" in sys.argv
    os.system(f"title 熱危害 07:00 推播 - {TARGET_GROUP_NAME}")

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"morning_{datetime.now():%Y%m%d_%H%M%S}.log"
    with open(log_path, "w", encoding="utf-8") as _log_file:
        try:
            ok = main(dry_run)
        except Exception as e:
            log(f"✗ 發生未預期的錯誤: {e!r}")
            ok = False
        log()
        log(("✓✓ 全部成功" if ok else "✗✗ 有步驟失敗") + f"，log 檔: {log_path}")

    if not dry_run or sys.stdin.isatty():
        keep_window_open()
    sys.exit(0 if ok else 1)
