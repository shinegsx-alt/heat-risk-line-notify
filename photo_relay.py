"""
「宜陽巡路隊」照片轉傳：紅字含「礁溪」的 3 張照片 + 1 張天氣相符的 LED 燈車照片 → 目標群組

流程（listener 收到圖片事件時呼叫 handle_event）：
  1. 只處理來源群組（宜陽巡路隊）裡「一次選 3 張」送出的照片（LINE 事件的 imageSet.total == 3）
  2. 每張收到就先下載到本機暫存 photo_relay_data/incoming/<imageSet.id>/
  3. 3 張到齊後另開執行緒處理：
     a. 本機紅色預檢：3 張左上角都要有紅字
     b. Claude Haiku：讀紅字 + 判斷天氣；紅字要有「礁溪」
     c. 天氣：戶外照片的判斷，依 雨 > 陰 > 晴（多雲當晴）取一個
     d. 到 WEATHER_ROOT 底下名稱含「未選用」+ 天氣字（晴/陰/雨）的資料夾挑一張
        （優先挑沒有 MMDD. 日期前綴的）
     e. 3 張原圖 + 天氣照片放進 OneDrive\\圖片\\<民國日期 1151110>\\，天氣照片是「移動」過去
        （從未選用資料夾移除）
     f. 4 張圖由 listener 經 ngrok 網址提供（/relay/<隨機碼>/<n>.jpg），一次 push 到目標群組
  找不到相符天氣照片、或判斷不出天氣時，只傳 3 張並在 log 記錄。

離線測試（不經 LINE）：
    python photo_relay.py a.jpg b.jpg c.jpg --dry-run            # 只辨識、只印出會挑哪張，不搬檔不推播
    python photo_relay.py a.jpg b.jpg c.jpg --no-push            # 實際建資料夾、搬天氣照片，但不推播
    python photo_relay.py a.jpg b.jpg c.jpg --weather 雨 --dry-run  # 跳過 Claude，指定天氣
"""

import argparse
import json
import re
import secrets
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from PIL import Image, ImageOps

import line_groups
from photo_ocr_test import RED_MIN_RATIO, ask_claude, crop_top, load_client, red_ratio

REPO_DIR = Path(__file__).resolve().parent

# ---- 設定 ----
SOURCE_GROUP_NAME = "宜陽巡路隊"
# 宜陽巡路隊的 Group ID（line_groups.json 查不到名稱時用這個比對）
SOURCE_GROUP_IDS = {"C39b294f05263f6b0b70a06b5238148d6"}
TARGET_GROUP_ID = "C61fd8276de5c3224cc772c3763768de5"
REQUIRED_KEYWORD = "礁溪"
PHOTOS_PER_SET = 3
MODEL = "claude-haiku-5-5"

PICTURES_DIR = Path(r"C:\Users\Owner\OneDrive\圖片")
WEATHER_ROOT = PICTURES_DIR / "115礁溪巡查LED燈車"
UNUSED_MARK = "未選用"
# Claude 判斷的天氣 → 資料夾名稱要含的字
WEATHER_FOLDER_WORD = {"晴": "晴", "多雲": "晴", "陰": "陰", "雨": "雨"}
WEATHER_PRIORITY = ["雨", "陰", "晴"]  # 3 張判斷不一致時，取最「濕」的

DATA_DIR = REPO_DIR / "photo_relay_data"  # 已在 .gitignore（工人照片不能進公開 repo）
INCOMING_DIR = DATA_DIR / "incoming"
SERVE_DIR = DATA_DIR / "serve"
LOG_PATH = DATA_DIR / "relay.log"
NGROK_DOMAIN_PATH = REPO_DIR / "ngrok_domain.txt"

INCOMPLETE_SET_TIMEOUT = timedelta(minutes=10)  # 3 張沒到齊，超過這個時間就丟掉
SERVE_KEEP = timedelta(days=1)                  # ngrok 提供的圖片保留多久
LINE_CONTENT_URL = "https://api-data.line.me/v2/bot/message/{message_id}/content"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")
DATE_PREFIX_RE = re.compile(r"^\d{4}\.\s*")  # 例如「1029.IMG2026...」「1028. IMG2026...」

_lock = threading.Lock()
_pending: dict[str, dict] = {}  # imageSet.id → {"created", "total", "files": {index: Path}, "user"}


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def roc_today() -> str:
    now = datetime.now()
    return f"{now.year - 1911}{now:%m%d}"


# ---------------------------------------------------------------- LINE 事件
def is_source_group(group_id: str) -> bool:
    if group_id in SOURCE_GROUP_IDS:
        return True
    name = line_groups.load_groups().get(group_id, {}).get("name", "")
    return name == SOURCE_GROUP_NAME


def handle_event(event: dict) -> None:
    """listener 對每個 message/image 事件呼叫；很快就回傳，下載和處理在背景執行緒"""
    source = event.get("source", {})
    group_id = source.get("groupId", "")
    if not group_id or not is_source_group(group_id):
        return
    message = event.get("message", {})
    image_set = message.get("imageSet")
    if not image_set or image_set.get("total") != PHOTOS_PER_SET:
        log(f"來源群組收到照片，但不是一次選 {PHOTOS_PER_SET} 張（imageSet={image_set}），略過")
        return
    threading.Thread(
        target=_download_and_collect,
        args=(message["id"], image_set, source.get("userId", "")),
        daemon=True,
    ).start()


def _download_and_collect(message_id: str, image_set: dict, user_id: str) -> None:
    set_id, index, total = image_set["id"], image_set["index"], image_set["total"]
    try:
        path = download_line_image(message_id, INCOMING_DIR / set_id, f"{index}.jpg")
    except Exception as e:
        log(f"下載照片失敗（set {set_id} 第 {index} 張）：{e}")
        return
    ready = None
    with _lock:
        _drop_stale_sets()
        entry = _pending.setdefault(
            set_id, {"created": datetime.now(), "total": total, "files": {}, "user": user_id}
        )
        entry["files"][index] = path
        log(f"收到照片 set {set_id[:8]} 第 {index}/{total} 張")
        if len(entry["files"]) == total:
            ready = [entry["files"][i] for i in sorted(entry["files"])]
            del _pending[set_id]
    if ready:
        try:
            process_set(ready)
        except Exception as e:
            log(f"處理 set {set_id[:8]} 發生錯誤：{e!r}")


def _drop_stale_sets() -> None:
    now = datetime.now()
    for set_id in [k for k, v in _pending.items() if now - v["created"] > INCOMPLETE_SET_TIMEOUT]:
        log(f"set {set_id[:8]} 超過 {INCOMPLETE_SET_TIMEOUT} 沒收齊，丟棄")
        shutil.rmtree(INCOMING_DIR / set_id, ignore_errors=True)
        del _pending[set_id]


def _token() -> str:
    token = line_groups.load_token()
    if not token or not token.isascii() or " " in token:
        raise RuntimeError("沒有有效的 LINE Channel Access Token（line_token.txt）")
    return token


def download_line_image(message_id: str, folder: Path, name: str) -> Path:
    resp = requests.get(
        LINE_CONTENT_URL.format(message_id=message_id),
        headers={"Authorization": f"Bearer {_token()}"},
        timeout=60,
    )
    resp.raise_for_status()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(resp.content)
    return path


# ---------------------------------------------------------------- 處理一組
def analyze(paths: list[Path], client) -> tuple[bool, str, list[dict]]:
    """回傳 (是否要轉傳, 天氣或空字串, 每張的辨識結果)"""
    results = []
    for p in paths:
        img = Image.open(p)
        ratio, _ = red_ratio(crop_top(img, 0.25))
        if ratio < RED_MIN_RATIO:
            log(f"  {p.name}：左上角沒有紅字（紅色 {ratio:.2%}），整組略過")
            return False, "", results
        r = ask_claude(client, MODEL, img)
        results.append(r)
        log(f"  {p.name}：紅字={r.get('lines')} 天氣={r.get('weather')}"
            f"（{'戶外' if r.get('is_outdoor') else '室內'}）{r['_usage']}")
        if not r.get("has_red_text"):
            log(f"  {p.name}：Claude 判定沒有紅字，整組略過")
            return False, "", results

    if not any(REQUIRED_KEYWORD in "".join(r.get("lines", [])) for r in results):
        log(f"  紅字裡沒有「{REQUIRED_KEYWORD}」，整組略過")
        return False, "", results
    return True, combine_weather(results), results


def combine_weather(results: list[dict]) -> str:
    words = {WEATHER_FOLDER_WORD[r["weather"]] for r in results
             if r.get("is_outdoor") and r.get("weather") in WEATHER_FOLDER_WORD}
    return next((w for w in WEATHER_PRIORITY if w in words), "")


def find_weather_photo(weather: str) -> Path | None:
    """在 WEATHER_ROOT 底下找名稱含「未選用」和天氣字的資料夾，挑一張（優先沒有日期前綴的）"""
    if not weather or not WEATHER_ROOT.exists():
        return None
    folders = sorted(d for d in WEATHER_ROOT.rglob("*")
                     if d.is_dir() and UNUSED_MARK in d.name and weather in d.name)
    candidates = [f for d in folders for f in sorted(d.iterdir())
                  if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES
                  and not f.name.startswith(".trashed")]
    if not candidates:
        return None
    candidates.sort(key=lambda f: bool(DATE_PREFIX_RE.match(f.name)))  # 沒前綴的排前面（穩定排序）
    return candidates[0]


def unique_path(path: Path) -> Path:
    n = 2
    result = path
    while result.exists():
        result = path.with_name(f"{path.stem}_{n}{path.suffix}")
        n += 1
    return result


def process_set(paths: list[Path], *, weather_override: str = "",
                dry_run: bool = False, push: bool = True) -> None:
    log(f"開始處理 {len(paths)} 張照片")
    if weather_override:
        ok, weather = True, WEATHER_FOLDER_WORD.get(weather_override, weather_override)
        log(f"  （測試）跳過 Claude，天氣指定為 {weather}")
    else:
        client = load_client()
        if client is None:
            raise RuntimeError("沒有 Anthropic API key（anthropic_key.txt）")
        ok, weather, _ = analyze(paths, client)
    if not ok:
        return

    weather_photo = find_weather_photo(weather)
    if not weather:
        log("  判斷不出天氣（沒有戶外照片），只傳 3 張")
    elif weather_photo is None:
        log(f"  找不到「{weather}」的未選用照片，只傳 3 張")
    else:
        log(f"  天氣 {weather} → 挑選 {weather_photo.relative_to(WEATHER_ROOT)}")

    out_dir = PICTURES_DIR / roc_today()
    if dry_run:
        log(f"  （dry-run）會存到 {out_dir}，不搬檔、不推播")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    final: list[Path] = []
    for i, p in enumerate(paths, 1):
        dest = unique_path(out_dir / f"{stamp}_{i}{p.suffix.lower()}")
        shutil.copy2(p, dest)
        final.append(dest)
    if weather_photo is not None:
        dest = unique_path(out_dir / weather_photo.name)
        shutil.move(str(weather_photo), dest)  # 從未選用資料夾移除
        final.append(dest)
    log(f"  已存到 {out_dir}：{', '.join(f.name for f in final)}")

    if push:
        push_photos(final)
    if paths[0].parent.parent == INCOMING_DIR:  # LINE 下載的暫存檔已複製到 OneDrive，刪掉
        shutil.rmtree(paths[0].parent, ignore_errors=True)


# ---------------------------------------------------------------- 經 ngrok 提供 + 推播
def prepare_served(paths: list[Path]) -> list[str]:
    """把照片轉成 LINE 規格（原圖 ≤10MB、預覽 ≤1MB）放到隨機資料夾，
    回傳每張的網址前綴（加 .jpg 是原圖、加 _p.jpg 是預覽）"""
    cleanup_served()
    domain = NGROK_DOMAIN_PATH.read_text(encoding="utf-8").strip()
    if not domain:
        raise RuntimeError("ngrok_domain.txt 是空的")
    token = secrets.token_urlsafe(16)
    folder = SERVE_DIR / token
    folder.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(paths, 1):
        img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        big = img.copy()
        big.thumbnail((4000, 4000))
        big.save(folder / f"{i}.jpg", quality=88)
        img.thumbnail((1024, 1024))
        img.save(folder / f"{i}_p.jpg", quality=80)
    return [f"https://{domain}/relay/{token}/{i}" for i in range(1, len(paths) + 1)]


def cleanup_served() -> None:
    if not SERVE_DIR.exists():
        return
    cutoff = time.time() - SERVE_KEEP.total_seconds()
    for d in SERVE_DIR.iterdir():
        if d.is_dir() and d.stat().st_mtime < cutoff:
            shutil.rmtree(d, ignore_errors=True)


def served_file(token: str, name: str) -> Path | None:
    """listener 的 /relay/<token>/<name> 路由用：只允許 serve 資料夾裡的檔案"""
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,64}", token) or not re.fullmatch(r"\d+(_p)?\.jpg", name):
        return None
    path = SERVE_DIR / token / name
    return path if path.is_file() else None


def push_photos(paths: list[Path]) -> None:
    bases = prepare_served(paths)
    messages = [{"type": "image", "originalContentUrl": f"{b}.jpg", "previewImageUrl": f"{b}_p.jpg"}
                for b in bases]
    for start in range(0, len(messages), 5):  # push 一次最多 5 則
        resp = requests.post(
            LINE_PUSH_URL,
            headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
            data=json.dumps({"to": TARGET_GROUP_ID, "messages": messages[start:start + 5]}),
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"推播失敗 {resp.status_code}：{resp.text}")
    log(f"  已推播 {len(messages)} 張到群組 {TARGET_GROUP_ID}")


# ---------------------------------------------------------------- 離線測試
def main():
    parser = argparse.ArgumentParser(description="宜陽巡路隊照片轉傳（離線測試）")
    parser.add_argument("images", nargs=PHOTOS_PER_SET, help=f"{PHOTOS_PER_SET} 張照片")
    parser.add_argument("--dry-run", action="store_true", help="只辨識和挑選，不搬檔、不推播")
    parser.add_argument("--no-push", action="store_true", help="建資料夾、搬天氣照片，但不推播")
    parser.add_argument("--weather", choices=list(WEATHER_FOLDER_WORD), help="跳過 Claude，直接指定天氣")
    args = parser.parse_args()
    process_set([Path(p) for p in args.images], weather_override=args.weather or "",
                dry_run=args.dry_run, push=not args.no_push)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
