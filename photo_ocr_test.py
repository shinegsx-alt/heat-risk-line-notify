"""
照片左上紅字辨識：離線可行性測試（還沒有接 LINE，不影響熱危害功能）

流程（每張照片）：
  1. 裁切上方 1/4（--ratio 可調）
  2. 本機紅色預檢：數裁切區有多少紅色像素，太少就判定「不是要處理的照片」，不呼叫 API
  3. 有紅色才把裁切圖丟給 Claude，只回傳紅色字（JSON）
  4. 結果印在畫面上，裁切圖和紅色遮罩圖存到 photo_test/output/ 方便對照

API key：環境變數 ANTHROPIC_API_KEY，或在本資料夾放 anthropic_key.txt（已加入 .gitignore）。
沒有 key 時只跑步驟 1、2。

用法：
    python photo_ocr_test.py                       # 測 photo_test/samples/ 全部照片
    python photo_ocr_test.py 某張.jpg 另一張.jpg
    python photo_ocr_test.py --model claude-sonnet-5-5   # 預設是 Haiku 5.5
    python photo_ocr_test.py --all                 # 沒紅字的照片也送 Claude 測天氣
    python photo_ocr_test.py --no-api              # 只跑本機裁切和紅色預檢
"""

import argparse
import base64
import io
import os
import sys
from pathlib import Path

from PIL import Image, ImageChops

REPO_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = REPO_DIR / "photo_test" / "samples"
OUTPUT_DIR = REPO_DIR / "photo_test" / "output"
KEY_PATH = REPO_DIR / "anthropic_key.txt"

# 每 100 萬 tokens 的美金價格（輸入, 輸出），用來估每張照片的費用
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
USD_TO_TWD = 32

# 紅色判定（PIL 的 HSV 三個值都是 0~255）：色相接近紅、飽和度和亮度夠高。
# 色相 ±13 度左右，排除橘色反光背心、黃色工程車。
RED_HUE_LOW = 9
RED_HUE_HIGH = 246
RED_MIN_SAT = 120
RED_MIN_VAL = 120
# 紅色像素至少要佔裁切區的比例，才算「有紅字」
RED_MIN_RATIO = 0.003

PROMPT = """這是一張工地照片。有些照片的左上角會疊上紅色的文字浮水印
（例如拍攝時間、經緯度座標、工程名稱）。請做兩件事：

一、只抄出左上角「紅色」的文字：
- 一行一筆，照畫面上的換行，原樣抄寫，不要修正、不要補字
- 黑色、白色或其他顏色的字（例如紙本表格上的印刷字、招牌字）都不要
- 如果沒有紅色文字，has_red_text 回 false，lines 回空陣列

二、判斷拍照當下的天氣：
- is_outdoor：這張照片看得到戶外環境（天空、路面、地面）嗎？只拍紙本表單、
  看不到戶外環境就回 false
- weather：從天空、光線、影子、路面乾濕、雨滴、雨具等線索判斷，
  只能是 晴、多雲、陰、雨 其中之一；is_outdoor 為 false 或看不出來就回 無法判斷
- weather_reason：用一句話說明判斷依據"""

SCHEMA = {
    "type": "object",
    "properties": {
        "has_red_text": {"type": "boolean"},
        "lines": {"type": "array", "items": {"type": "string"}},
        "is_outdoor": {"type": "boolean"},
        "weather": {"type": "string", "enum": ["晴", "多雲", "陰", "雨", "無法判斷"]},
        "weather_reason": {"type": "string"},
    },
    "required": ["has_red_text", "lines", "is_outdoor", "weather", "weather_reason"],
    "additionalProperties": False,
}


def crop_top(img: Image.Image, ratio: float) -> Image.Image:
    w, h = img.size
    return img.crop((0, 0, w, max(1, int(h * ratio))))


def red_ratio(img: Image.Image) -> tuple[float, Image.Image]:
    """回傳紅色像素比例，以及紅色遮罩圖（紅色像素顯示白色）"""
    h, s, v = img.convert("HSV").split()
    hue_ok = h.point(lambda x: 255 if (x <= RED_HUE_LOW or x >= RED_HUE_HIGH) else 0)
    sat_ok = s.point(lambda x: 255 if x >= RED_MIN_SAT else 0)
    val_ok = v.point(lambda x: 255 if x >= RED_MIN_VAL else 0)
    mask =ImageChops.multiply(ImageChops.multiply(hue_ok, sat_ok), val_ok)
    count = mask.histogram()[255]
    return count / (img.width * img.height), mask


def load_client():
    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key and KEY_PATH.exists():
        key = KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def ask_claude(client, model: str, img: Image.Image) -> dict:
    """送整張照片（判斷天氣要看到天空和地面），長邊超過 1600 就先縮小"""
    import json

    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")

    params = dict(
        model=model,
        max_tokens=4000,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    if model in ("claude-opus-5-5", "claude-sonnet-5-5"):
        # 安全分類器誤擋時，伺服器自動改用建議的備援模型重跑
        response = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
        )
    else:
        response = client.messages.create(**params)

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude 拒絕處理：{getattr(response, 'stop_details', None)}")
    text = next((b.text for b in response.content if b.type == "text"), "")
    result = json.loads(text)

    u = response.usage
    price_in, price_out = PRICES.get(model, (0, 0))
    usd = (u.input_tokens * price_in + u.output_tokens * price_out) / 1_000_000
    result["_twd"] = usd * USD_TO_TWD
    result["_usage"] = f"輸入 {u.input_tokens} / 輸出 {u.output_tokens} tokens，NT${usd * USD_TO_TWD:.4f}"
    return result


def main():
    parser = argparse.ArgumentParser(description="照片左上紅字辨識（離線測試）")
    parser.add_argument("images", nargs="*", help="照片路徑；不給就測 photo_test/samples/ 全部")
    parser.add_argument("--model", default="claude-haiku-5-5", help="Claude 模型 ID")
    parser.add_argument("--ratio", type=float, default=0.25, help="裁切上方多少比例（預設 0.25）")
    parser.add_argument("--no-api", action="store_true", help="只跑本機裁切和紅色預檢，不呼叫 Claude")
    parser.add_argument("--all", action="store_true", help="沒有紅字的照片也送 Claude（測天氣判斷用）")
    args = parser.parse_args()

    paths = [Path(p) for p in args.images] or sorted(
        p for p in SAMPLES_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = None if args.no_api else load_client()
    if not args.no_api and client is None:
        print("找不到 API key（ANTHROPIC_API_KEY 或 anthropic_key.txt），這次只跑本機預檢\n")

    total_twd = 0.0
    for path in paths:
        print(f"=== {path.name} ===")
        img = Image.open(path)
        crop = crop_top(img, args.ratio)
        ratio, mask = red_ratio(crop)
        crop.convert("RGB").save(OUTPUT_DIR / f"{path.stem}_crop.jpg", quality=90)
        mask.save(OUTPUT_DIR / f"{path.stem}_redmask.png")
        print(f"原圖 {img.width}x{img.height}，裁切 {crop.width}x{crop.height}，紅色像素 {ratio:.2%}")

        if ratio < RED_MIN_RATIO:
            print("→ 本機預檢：沒有紅字，不是要處理的照片")
            if not args.all:
                print()
                continue
            print("  （--all：仍送 Claude 測天氣判斷）")
        if client is None:
            print("→ 應送 Claude 辨識（沒有 API key，這次略過）\n")
            continue

        try:
            result = ask_claude(client, args.model, img)
        except Exception as e:
            print(f"→ Claude 呼叫失敗：{e}\n")
            continue
        total_twd += result["_twd"]
        if result.get("has_red_text"):
            print("→ 紅字內容：")
            for line in result.get("lines", []):
                print(f"   {line}")
        else:
            print("→ Claude 判定沒有紅字")
        place = "戶外" if result.get("is_outdoor") else "室內／看不到戶外"
        print(f"→ 天氣：{result.get('weather')}（{place}）")
        print(f"   依據：{result.get('weather_reason')}")
        print(f"   （{args.model}，{result['_usage']}）\n")

    if client is not None:
        print(f"合計費用：NT${total_twd:.4f}（匯率以 1 美元 = {USD_TO_TWD} 台幣估算）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
