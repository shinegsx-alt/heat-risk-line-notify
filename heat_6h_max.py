"""
從勞動部職安署「高氣溫作業防護資訊網」的 API 抓宜蘭 7 個鄉鎮的熱危害等級，
輸出三個群組（獨立山 / 礁溪 / 宜蘭）在「執行當下 + 未來 6 小時」內的最高等級。

每個鄉鎮的資料來源：
  1. 現在的風險等級（Heatindex.ashx）
  2. 未來 6 小時逐時預報（trend.aspx，就是網頁上那張預估圖表）

用法：
    python heat_6h_max.py
"""

import json
import re
import ssl
import sys
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter

BASE_URL = "https://hiosha.osha.gov.tw/content/info/"

COUNTY = "宜蘭縣"
# 群組名稱 → 鄉鎮市（完整名稱，拿去網站查詢用）
GROUPS = {
    "獨立山": ["三星鄉", "大同鄉"],
    "礁溪": ["礁溪鄉", "頭城鎮"],
    "宜蘭": ["宜蘭市", "壯圍鄉", "員山鄉"],
}

# 網站儀表板的刻度：26.7 / 32.2 / 40.6 / 54.4 分別是第一～四級的起點
LEVEL_THRESHOLDS = [(54.4, 4), (40.6, 3), (32.2, 2), (26.7, 1)]
LEVEL_NAMES = {0: "未達高溫風險", 1: "第一級", 2: "第二級", 3: "第三級", 4: "第四級"}


class _LenientCertAdapter(HTTPAdapter):
    """職安署網站的憑證缺少 Subject Key Identifier，Python 3.13 起預設的
    嚴格檢查（VERIFY_X509_STRICT）會直接拒絕連線。這裡仍然驗證憑證，
    只關掉那個嚴格旗標。"""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def heat_level(heat_index: float) -> int:
    for threshold, level in LEVEL_THRESHOLDS:
        if heat_index >= threshold:
            return level
    return 0


def _json(resp: requests.Response) -> dict:
    # 伺服器沒有宣告 charset，requests 會猜錯編碼，所以自己用 UTF-8 解
    resp.raise_for_status()
    return json.loads(resp.content.decode("utf-8"))


def new_session() -> tuple[requests.Session, str]:
    """建立連線並取得網頁裡的 sessionID（查詢 API 要帶這個值）"""
    s = requests.Session()
    s.mount("https://", _LenientCertAdapter())
    s.headers["User-Agent"] = "Mozilla/5.0"
    resp = s.get(BASE_URL + "heat1.aspx", timeout=30)
    resp.raise_for_status()
    m = re.search(r"sessionID:\s*'([^']+)'", resp.content.decode("utf-8"))
    if not m:
        raise RuntimeError("在 heat1.aspx 找不到 sessionID，網站格式可能改了")
    return s, m.group(1)


def town_max_level(s: requests.Session, session_id: str, town: str) -> int:
    """查一個鄉鎮，回傳「現在 + 未來 6 小時」的最高風險等級。
    trend.aspx 讀的是同一個 session 最後一次查詢的地點，所以鄉鎮要依序查，不能並行。"""
    addr = _json(s.post(
        BASE_URL + "Heatindex.ashx?t=checkAddress",
        data={"type": "checkAddress", "inputAddress": COUNTY + town},
        timeout=30,
    ))["Data"]
    if not addr:
        raise RuntimeError(f"網站找不到地址：{COUNTY}{town}")

    current = _json(s.post(
        BASE_URL + "Heatindex.ashx",
        data={
            "type": "0", "city": addr["city"], "area": addr["area"],
            "temperature": "", "humidity": "",
            "lat": addr["lat"], "lng": addr["lng"],
            "isSun": "false", "isVitality": "false",
            "sessionID": session_id, "queryType": "0", "Note": "",
        },
        timeout=30,
    ))["Data"]
    if not current:
        raise RuntimeError(f"{town} 查詢沒有回傳資料")

    # trend.aspx 的熱指數直接寫在圖表 JS 的 data: [...] 裡
    trend = s.get(BASE_URL + "trend.aspx", timeout=30).content.decode("utf-8")
    m = re.search(r"\bdata\s*:\s*\[([^\]]*)\]", trend)
    forecast = [float(x) for x in m.group(1).split(",") if x.strip()] if m else []

    return max([int(current["riskLv"])] + [heat_level(hi) for hi in forecast])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"{datetime.now():%m/%d %H:%M} 未來6小時熱危害最高等級")
    # 開 session 很慢（網站載入 heat1.aspx 要 20 秒左右），所有鄉鎮共用一個
    s, session_id = new_session()
    for group, towns in GROUPS.items():
        levels = []
        for town in towns:
            try:
                levels.append(town_max_level(s, session_id, town))
            except Exception as e:
                print(f"[警告] {town} 查詢失敗：{e}", file=sys.stderr)
        print(f"{group}：{LEVEL_NAMES[max(levels)] if levels else '無資料'}")


if __name__ == "__main__":
    main()
