"""
獨立執行的觀察者程式：輪詢 trigger.flag 這個旗標檔案，
看到了就執行一次 daily_run.py（截圖 7 個鄉鎮市 + push + 等 GitHub Actions
推播到 LINE 群組跑完），跑完才繼續下一輪輪詢。

要跟 line_webhook_listener.py 分開，是因為 daily_run.py 需要啟動瀏覽器，
若由「接收外部網路請求的程式」直接觸發，容易被本機防護軟體判定為可疑行為
而攔截。這支程式由使用者自己在終端機啟動，跟手動執行 `python daily_run.py`
是同樣的信任層級，不會被攔截。

執行期間的行為：
- 每 3 秒檢查一次旗標檔案
- 看到旗標，立刻刪除它（這樣執行期間新進來的觸發，會在下一輪被重新偵測到，
  不會憑空消失，但也不會因為連續打好幾次關鍵字就疊加執行好幾輪）
- 執行 daily_run.py，直到它完全結束（包含等 GitHub Actions 推播完成）才繼續輪詢
  → 這段期間內旗標又被放上的話，會在這輪結束後自動接著跑一次，不會漏掉

用法：
    python trigger_watcher.py
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
TRIGGER_FLAG = REPO_DIR / "trigger.flag"
POLL_INTERVAL = 3


def run_once():
    print(f"[{datetime.now()}] 偵測到觸發旗標，開始執行 daily_run.py ...")
    result = subprocess.run(
        [sys.executable, str(REPO_DIR / "daily_run.py")],
        cwd=REPO_DIR,
    )
    print(f"[{datetime.now()}] daily_run.py 執行完畢，returncode={result.returncode}")


if __name__ == "__main__":
    print(f"開始輪詢觸發旗標: {TRIGGER_FLAG}（每 {POLL_INTERVAL} 秒檢查一次）")
    while True:
        if TRIGGER_FLAG.exists():
            TRIGGER_FLAG.unlink()
            run_once()
        time.sleep(POLL_INTERVAL)
