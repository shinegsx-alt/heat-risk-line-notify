"""
跨程序的執行鎖：line_webhook_listener.py（群組觸發）和 morning_run.py（每天 07:00 排程）
都會跑 daily_run.py 去截圖 + git commit/push，兩個同時跑會互相干擾，所以共用這把鎖。

用作業系統的檔案鎖（logs/run.lock），程式結束或當掉時 Windows 會自動釋放，不會卡死。
"""

import msvcrt
from pathlib import Path

LOCK_PATH = Path(__file__).resolve().parent / "logs" / "run.lock"


class RunLock:
    def __init__(self):
        self._file = None

    def try_acquire(self) -> bool:
        """拿到鎖回傳 True；別人正在用就回傳 False（不等待）"""
        LOCK_PATH.parent.mkdir(exist_ok=True)
        f = open(LOCK_PATH, "a+")
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            return False
        self._file = f
        return True

    def release(self) -> None:
        if self._file:
            self._file.seek(0)
            msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            self._file.close()
            self._file = None
