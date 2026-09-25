import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import redis
import requests


# ============================================================
# Configuration
# ============================================================

CWA_API_URL = (
    "https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0033-003"
)

COUNTY_NAME = "桃園市"

REDIS_KEY = os.getenv(
    "REDIS_KEY",
    "weather:alert:taoyuan",
)

CWA_API_KEY = os.getenv("CWA_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")


# ============================================================
# Validation
# ============================================================

def validate_environment():
    required = {
        "CWA_API_KEY": CWA_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "REDIS_URL": REDIS_URL,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "缺少必要的 GitHub Secrets: "
            + ", ".join(missing)
        )


# ============================================================
# CWA API
# ============================================================

def fetch_cwa_alert():
    """
    取得中央氣象署桃園市氣象特報。

    API:
    W-C0033-003
    """

    headers = {
        "Authorization": CWA_API_KEY,
        "Accept": "application/json",
        "User-Agent": "github-actions-taoyuan-weather-alert",
    }

    params = {
        "format": "JSON",
        "CountyName": COUNTY_NAME,
        "expires": "true",
    }

    response = requests.get(
        CWA_API_URL,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# Find CWA records.info
# ============================================================

def find_info(obj):
    """
    遞迴尋找 CWA 回傳資料中的 info。

    對應原本 n8n Normalize Alert：
    findInfo(item.json)
    """

    if not isinstance(obj, dict):
        return None

    info = obj.get("info")

    if isinstance(info, list) and len(info) > 0:
        return info[0]

    for value in obj.values():

        if isinstance(value, dict):
            result = find_info(value)

            if result:
                return result

        elif isinstance(value, list):

            for item in value:

                if isinstance(item, dict):
                    result = find_info(item)

                    if result:
                        return result

    return None


# ============================================================
# Normalize CWA alert
# ============================================================

def normalize_alert(data):
    info = find_info(data)

    if not info:
        return {
            "valid": False,
            "error": "找不到中央氣象署 records.info 資料",
        }

    areas = info.get("area", [])

    if not isinstance(areas, list):
        areas = []

    area_desc = "、".join(
        str(area.get("areaDesc"))
        for area in areas
        if isinstance(area, dict)
        and area.get("areaDesc")
    )

    headline = info.get("headline") or ""
    description = info.get("description") or ""
    effective = info.get("effective") or ""
    onset = info.get("onset") or ""
    expires = info.get("expires") or ""
    sender_name = info.get("senderName") or "中央氣象署"
    web = info.get("web") or ""

    # --------------------------------------------------------
    # 確認是否為桃園市
    # --------------------------------------------------------

    is_taoyuan = any(
        COUNTY_NAME in str(area.get("areaDesc", ""))
        for area in areas
        if isinstance(area, dict)
    )

    if not is_taoyuan:
        return {
            "valid": False,
            "error": "資料不是桃園市",
        }

    # --------------------------------------------------------
    # 判斷狀態
    # --------------------------------------------------------

    is_resolved = "解除" in headline

    status = (
        "resolved"
        if is_resolved
        else "active"
    )

    # --------------------------------------------------------
    # Fingerprint
    # --------------------------------------------------------

    fingerprint_source = "|".join([
        area_desc,
        headline,
        description,
        effective,
        onset,
        expires,
    ])

    fingerprint = hashlib.sha256(
        fingerprint_source.encode("utf-8")
    ).hexdigest()

    # --------------------------------------------------------
    # Telegram message
    # --------------------------------------------------------

    message = (
        "🌧️ 桃園市氣象警報通知\n"
        "\n"
        f"📍 地區：{area_desc or COUNTY_NAME}\n"
        f"📢 發布單位：{sender_name}\n"
        "\n"
        f"⚠️ {headline or '氣象特報'}\n"
        "\n"
        f"📝 {description or '未提供詳細說明'}\n"
        "\n"
        f"🕐 發布時間：{effective or '未提供'}\n"
        f"⏰ 結束時間：{expires or '未提供'}\n"
        "\n"
        "🔗 詳細資訊：\n"
        f"{web or '無'}"
    )

    return {
        "valid": True,
        "areaDesc": area_desc,
        "senderName": sender_name,
        "headline": headline,
        "description": description,
        "web": web,
        "effective": effective,
        "onset": onset,
        "expires": expires,
        "status": status,
        "isResolved": is_resolved,
        "fingerprint": fingerprint,
        "message": message,
    }


# ============================================================
# Redis
# ============================================================

def get_redis():
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def get_previous_state(r):
    raw = r.get(REDIS_KEY)

    if not raw:
        return None

    try:
        return json.loads(raw)

    except json.JSONDecodeError:
        print("WARNING: Redis 中的 state 不是有效 JSON")
        return None


# ============================================================
# Compare State
# ============================================================

def compare_state(current, previous):
    """
    對應 n8n Compare Alert State。
    """

    has_previous_state = previous is not None

    fingerprint_changed = (
        previous is None
        or previous.get("fingerprint")
        != current["fingerprint"]
    )

    # --------------------------------------------------------
    # 第一次執行
    #
    # active:
    #   通知
    #
    # resolved:
    #   不通知，只建立狀態
    # --------------------------------------------------------

    if has_previous_state:
        should_notify = fingerprint_changed

    else:
        should_notify = (
            current["status"] == "active"
        )

    now = datetime.now(timezone.utc).isoformat()

    state = {
        "version": 1,
        "area": current["areaDesc"],
        "senderName": current["senderName"],
        "headline": current["headline"],
        "description": current["description"],
        "web": current["web"],
        "effective": current["effective"],
        "onset": current["onset"],
        "expires": current["expires"],
        "status": current["status"],
        "fingerprint": current["fingerprint"],
        "firstSeenAt": (
            previous.get("firstSeenAt")
            if previous
            else now
        ),
        "lastCheckedAt": now,
        "lastNotifiedAt": (
            now
            if should_notify
            else (
                previous.get("lastNotifiedAt")
                if previous
                else None
            )
        ),
    }

    return {
        **current,
        "hasPreviousState": has_previous_state,
        "fingerprintChanged": fingerprint_changed,
        "shouldNotify": should_notify,
        "previousState": previous,
        "state": state,
    }


# ============================================================
# Telegram
# ============================================================

def send_telegram(message):
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=20,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API 回傳失敗: {result}"
        )

    return result


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)
    print("桃園氣象特報監控")
    print("=" * 60)

    validate_environment()

    # --------------------------------------------------------
    # 1. CWA
    # --------------------------------------------------------

    print("[1/5] 取得中央氣象署資料...")

    cwa_data = fetch_cwa_alert()

    # --------------------------------------------------------
    # 2. Normalize
    # --------------------------------------------------------

    print("[2/5] 正規化氣象特報...")

    current = normalize_alert(cwa_data)

    if not current.get("valid"):
        print(
            f"沒有有效的桃園市特報: "
            f"{current.get('error')}"
        )

        # 注意：
        # API 沒資料時，不修改 Redis。
        return

    print(
        f"地區: {current['areaDesc']}"
    )

    print(
        f"標題: {current['headline']}"
    )

    print(
        f"狀態: {current['status']}"
    )

    print(
        f"Fingerprint: "
        f"{current['fingerprint']}"
    )

    # --------------------------------------------------------
    # 3. Redis
    # --------------------------------------------------------

    print("[3/5] 讀取 Redis 狀態...")

    r = get_redis()

    # 測試 Redis connection
    r.ping()

    previous = get_previous_state(r)

    if previous:
        print(
            "Redis 已存在舊狀態"
        )

        print(
            f"舊 Fingerprint: "
            f"{previous.get('fingerprint')}"
        )

    else:
        print(
            "Redis 沒有舊狀態"
        )

    # --------------------------------------------------------
    # 4. Compare
    # --------------------------------------------------------

    print("[4/5] 比較特報狀態...")

    result = compare_state(
        current,
        previous,
    )

    print(
        f"Fingerprint Changed: "
        f"{result['fingerprintChanged']}"
    )

    print(
        f"Should Notify: "
        f"{result['shouldNotify']}"
    )

    # --------------------------------------------------------
    # 5. Notification
    # --------------------------------------------------------

    if result["shouldNotify"]:

        print("[5/5] 特報有變化，發送 Telegram...")

        send_telegram(
            result["message"]
        )

        print(
            "Telegram 發送成功"
        )

    else:

        print(
            "[5/5] 特報沒有變化，不發送 Telegram"
        )

    # --------------------------------------------------------
    # Save Redis
    #
    # 無論有沒有通知，都要更新 lastCheckedAt。
    # --------------------------------------------------------

    r.set(
        REDIS_KEY,
        json.dumps(
            result["state"],
            ensure_ascii=False,
        ),
    )

    print(
        f"Redis 狀態已更新: {REDIS_KEY}"
    )

    print("=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        raise
