import os
import json
import time
import requests

# ----------------------------------------------------
# 1. إعدادات تليجرام (أدخل بياناتك هنا)
# ----------------------------------------------------
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(f"⚠️ [تنبيه لم يرسل]: لم تقم بوضع BOT TOKEN. الرسالة: {message}")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"✅ تم إرسال الرسالة بنجاح عبر تليجرام!")
            return True
        else:
            print(f"❌ خطأ من تليجرام: status={r.status_code} body={r.text}")
            return False
    except Exception as e:
        print(f"⚠️ فشل الاتصال بتليجرام: {e}")
        return False

# ----------------------------------------------------
# 2. إعدادات فحص التكرار (Redis + JSON)
# ----------------------------------------------------

def is_recently_sent(symbol):
    # الفحص من Redis
    if 'UPSTASH_REDIS_REST_URL' in globals() and 'UPSTASH_REDIS_REST_TOKEN' in globals():
        if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
            try:
                url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
                headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
                r = requests.get(url, headers=headers, timeout=5)
                res = r.json()
                if res.get("result") is not None:
                    return True
            except Exception as e:
                print(f"⚠️ فشل GET من Redis لـ {symbol}: {e}")

    # الفحص من الملف المحلي (Fallback)
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
    # الحفظ في Redis
    if 'UPSTASH_REDIS_REST_URL' in globals() and 'UPSTASH_REDIS_REST_TOKEN' in globals():
        if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
            try:
                url = f"{UPSTASH_REDIS_REST_URL}/pipeline"
                headers = {
                    "Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = [["SET", symbol, "SENT", "EX", 86400]]
                requests.post(url, headers=headers, json=payload, timeout=5)
            except Exception as e:
                print(f"⚠️ فشل الحفظ في Redis لـ {symbol}: {e}")

    # الحفظ في الملف المحلي
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
# 3. منطق الشروط ومعالجة الإشارات مع طباعة التفاصيل
# ----------------------------------------------------

def process_market_and_signals(symbols_data_list, tasi_change_pct):
    # 1. فحص تاسي
    if tasi_change_pct <= -1.0:
        if not is_recently_sent("TASI_ALERT"):
            msg = f"🚨 *تنبيه حماية السوق*\n\nتراجع مؤشر تاسي (TASI) بنسبة: *{tasi_change_pct}%*"
            if send_telegram_message(msg):
                save_sent("TASI_ALERT")
        else:
            print("ℹ️ تم إرسال تنبيه تاسي سابقاً خلال 24 ساعة.")

    # 2. فحص قائمة الأسهم
    for symbol_data in symbols_data_list:
        symbol = symbol_data.get('symbol')
        avg_vol = symbol_data.get('avg_volume_20d', 0)
        curr_vol = symbol_data.get('volume', 0)
        price_chg = symbol_data.get('price_change_5m', 0)
        breakout = symbol_data.get('instant_breakout', False)
        
        # إذا لم يُحدد الاتجاه المتوسط في البيانات، افترضه True تجنباً للتعطيل
        medium_tf = symbol_data.get('medium_tf_trend', True)

        # 1. فحص التكرار خلال 24 ساعة
        if is_recently_sent(symbol):
            print(f"⏭️ {symbol}: تم التجاوز لأنه أُرسل سابقاً خلال 24 ساعة.")
            continue

        # 2. فحص التأكيد المتوسط
        if not medium_tf:
            print(f"⛔ {symbol}: لم يرسل لأن الفاصل المتوسط غير مؤكد (medium_tf_trend = False).")
            continue

        # 3. فحص الشروط اللحظية
        is_vol_spike = curr_vol >= (avg_vol * 1.5) if avg_vol > 0 else False
        is_price_spike = price_chg >= 1.5

        if is_vol_spike or is_price_spike or breakout:
            msg = f"🚀 *تنبيه إشارة إيجابية*\n\nالسهم: *{symbol}*\nالسيولة اللحظية: *{curr_vol}*\nالتغير اللحظي: *{price_chg}%*"
            print(f"🎯 تحققت الشروط للسهم {symbol}، جاري الإرسال...")
            if send_telegram_message(msg):
                save_sent(symbol)
        else:
            print(f"ℹ️ {symbol}: لم تتحقق أي إشارة لحظية (سيولة 1.5x أو اختراق أو ارتفاع 1.5%+).")
