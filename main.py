import os
import json
import time
import requests

# ----------------------------------------------------
# 1. إعدادات بوت تليجرام (استبدل القيم الخاصة بك)
# ----------------------------------------------------
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

def send_telegram_message(message):
    """دالة إرسال الرسائل إلى تليجرام"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(f"📡 [محاكاة إرسال]: {message}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ تم إرسال الرسالة بنجاح عبر تليجرام.")
        else:
            print(f"❌ فشل إرسال تليجرام: {r.text}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء الإرسال لتليجرام: {e}")

# ----------------------------------------------------
# 2. إعدادات فحص التكرار (Redis + JSON)
# ----------------------------------------------------

def is_recently_sent(symbol):
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            r = requests.get(url, headers=headers, timeout=10)
            res = r.json()
            if res.get("result") is not None:
                return True
        except Exception as e:
            print(f"⚠️ فشل GET من Redis لـ {symbol}: {e}")

    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
                if symbol in cache and (time.time() - cache[symbol]) < 86400:
                    return True
        except Exception as e:
            print(f"⚠️ فشل قراءة الملف المحلي: {e}")
            
    return False


def save_sent(symbol):
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/pipeline"
            headers = {
                "Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = [["SET", symbol, "SENT", "EX", 86400]]
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ فشل الحفظ في Redis لـ {symbol}: {e}")

    cache = {}
    current_time = time.time()
    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
        except Exception:
            pass
            
    cache = {k: v for k, v in cache.items() if (current_time - v) < 86400}
    cache[symbol] = current_time
    
    try:
        with open('sent_signals.json', 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"⚠️ فشل كتابة الملف المحلي: {e}")

# ----------------------------------------------------
# 3. منطق الشروط ومعالجة الإشارات
# ----------------------------------------------------

def check_tasi_alert(tasi_change_pct):
    if tasi_change_pct <= -1.0:
        if not is_recently_sent("TASI_ALERT"):
            msg = f"🚨 *تنبيه حماية السوق*\n\nتراجع مؤشر تاسي (TASI) بنسبة: *{tasi_change_pct}%*"
            send_telegram_message(msg)
            save_sent("TASI_ALERT")


def should_send_signal(symbol_data, avg_volume_20d):
    current_volume = symbol_data.get('volume', 0)
    
    is_volume_spike = current_volume >= (avg_volume_20d * 1.5) if avg_volume_20d > 0 else False
    instant_breakout = symbol_data.get('instant_breakout', False)
    instant_price_change = symbol_data.get('price_change_5m', 0) >= 1.5
    medium_tf_confirmed = symbol_data.get('medium_tf_trend', False)

    if (instant_breakout or instant_price_change or is_volume_spike) and medium_tf_confirmed:
        return True

    return False


def process_market_and_signals(symbols_data_list, tasi_change_pct):
    check_tasi_alert(tasi_change_pct)

    for symbol_data in symbols_data_list:
        symbol = symbol_data['symbol']
        avg_volume_20d = symbol_data.get('avg_volume_20d', 0)

        if is_recently_sent(symbol):
            continue

        if should_send_signal(symbol_data, avg_volume_20d):
            msg = f"🚀 *تنبيه إشارة إيجابية*\n\nالسهم: *{symbol}*\nالسيولة: *{symbol_data.get('volume', 0)}*\nالتغير اللحظي: *{symbol_data.get('price_change_5m', 0)}%*"
            send_telegram_message(msg)
            save_sent(symbol)
