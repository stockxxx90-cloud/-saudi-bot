import os
import json
import time
import requests

# ----------------------------------------------------
# 1. إعدادات تليجرام و Redis
# ----------------------------------------------------
TELEGRAM_BOT_TOKEN = "ضع_التوكن_هنا"
TELEGRAM_CHAT_ID = "ضع_الـID_هنا"

# جلب بيانات Redis من المتغيرات إن وجدت، وإلا استخدام قيم فارغة
UPSTASH_REDIS_REST_URL = globals().get('UPSTASH_REDIS_REST_URL', os.getenv('UPSTASH_REDIS_REST_URL', ''))
UPSTASH_REDIS_REST_TOKEN = globals().get('UPSTASH_REDIS_REST_TOKEN', os.getenv('UPSTASH_REDIS_REST_TOKEN', ''))


def send_telegram_message(message):
    """دالة إرسال الرسائل عبر تليجرام مع التحقق المباشر من النتيجة"""
    if not TELEGRAM_BOT_TOKEN or "ضع_التوكن" in TELEGRAM_BOT_TOKEN:
        print("⚠️ [خطأ]: لم يتم تعيين TELEGRAM_BOT_TOKEN في الكود.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if r.status_code == 200 and res.get("ok"):
            print("✅ تم الإرسال بنجاح إلى تليجرام!")
            return True
        else:
            print(f"❌ رد تليجرام برفض الرسالة: {res.get('description')}")
            return False
    except Exception as e:
        print(f"⚠️ فشل الاتصال بخوادم تليجرام: {e}")
        return False


# ----------------------------------------------------
# 2. إعدادات فحص التكرار (مُصححة ومضمونة)
# ----------------------------------------------------

def is_recently_sent(symbol):
    # 1. الفحص عبر Redis (إذا كان مفعلاً ومكتمل البيانات)
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                res = r.json()
                if res.get("result") is not None:
                    return True
        except Exception as e:
            print(f"⚠️ فشل القراءة من Redis لـ {symbol}: {e}")

    # 2. الفحص عبر الملف المحلي
    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
                if symbol in cache and (time.time() - float(cache[symbol])) < 86400:
                    return True
        except Exception as e:
            print(f"⚠️ فشل قراءة الملف المحلي: {e}")

    return False


def save_sent(symbol):
    # 1. الحفظ في Redis
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
            print(f"⚠️ فشل الحفظ في Redis: {e}")

    # 2. الحفظ في الملف المحلي
    cache = {}
    current_time = time.time()
    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
        except Exception:
            pass

    # تنظيف السجلات القديمة
    cache = {k: v for k, v in cache.items() if (current_time - float(v)) < 86400}
    cache[symbol] = current_time

    try:
        with open('sent_signals.json', 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"⚠️ فشل كتابة الملف المحلي: {e}")


# ----------------------------------------------------
# 3. محرك الفحص المصحح (مع أمان البيانات)
# ----------------------------------------------------

def process_market_and_signals(symbols_data_list, tasi_change_pct):
    # تحويل نسبة تاسي لأرقام بأمان
    try:
        tasi_change_pct = float(tasi_change_pct)
    except (ValueError, TypeError):
        tasi_change_pct = 0.0

    # 1. فحص مؤشر تاسي
    if tasi_change_pct <= -1.0:
        if not is_recently_sent("TASI_ALERT"):
            msg = f"🚨 *تنبيه حماية السوق*\n\nتراجع مؤشر تاسي (TASI) بنسبة: *{tasi_change_pct}%*"
            if send_telegram_message(msg):
                save_sent("TASI_ALERT")

    # 2. فحص قائمة الأسهم
    for symbol_data in symbols_data_list:
        if not isinstance(symbol_data, dict):
            continue

        symbol = str(symbol_data.get('symbol', ''))
        if not symbol:
            continue

        # معالجة تحويل البيانات لأرقام تجنباً لأخطاء المقارنة
        try:
            avg_vol = float(symbol_data.get('avg_volume_20d', 0) or 0)
            curr_vol = float(symbol_data.get('volume', 0) or 0)
            price_chg = float(symbol_data.get('price_change_5m', 0) or 0)
        except (ValueError, TypeError):
            continue

        breakout = bool(symbol_data.get('instant_breakout', False))
        medium_tf = bool(symbol_data.get('medium_tf_trend', True))

        # فحص الحظر السابقي خلال 24 ساعة
        if is_recently_sent(symbol):
            continue

        # فحص شرط الفاصل المتوسط
        if not medium_tf:
            continue

        # فحص الشروط اللحظية
        is_vol_spike = curr_vol >= (avg_vol * 1.5) if avg_vol > 0 else False
        is_price_spike = price_chg >= 1.5

        if is_vol_spike or is_price_spike or breakout:
            msg = (
                f"🚀 *تنبيه إشارة إيجابية*\n\n"
                f"📊 السهم: *{symbol}*\n"
                f"📈 التغير اللحظي: *{price_chg}%*\n"
                f"💧 السيولة اللحظية: *{curr_vol}*"
            )
            print(f"🎯 تحققت الشروط للسهم {symbol}، جاري الإرسال...")
            if send_telegram_message(msg):
                save_sent(symbol)
