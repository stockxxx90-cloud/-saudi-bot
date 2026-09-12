import os
import json
import time
import requests

# ----------------------------------------------------
# 1. الإعدادات الرئيسية (ضع بياناتك هنا)
# ----------------------------------------------------
TELEGRAM_BOT_TOKEN = "ضع_التوكن_هنا"
TELEGRAM_CHAT_ID = "ضع_الـID_هنا"

UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

# ----------------------------------------------------
# 2. دالة الإرسال عبر تليجرام
# ----------------------------------------------------
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or "ضع_التوكن" in TELEGRAM_BOT_TOKEN:
        print("⚠️ لم يتم ضبط TELEGRAM_BOT_TOKEN!")
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
            print(f"✅ تم الإرسال لتليجرام بنجاح!")
            return True
        else:
            print(f"❌ رفض تليجرام الرسالة: {res.get('description')}")
            return False
    except Exception as e:
        print(f"⚠️ فشل الاتصال بتليجرام: {e}")
        return False

# ----------------------------------------------------
# 3. إعدادات فحص التكرار (Redis + JSON)
# ----------------------------------------------------
def is_recently_sent(symbol):
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200 and r.json().get("result") is not None:
                return True
        except Exception:
            pass

    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
                if symbol in cache and (time.time() - float(cache[symbol])) < 86400:
                    return True
        except Exception:
            pass

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
            requests.post(url, headers=headers, json=payload, timeout=5)
        except Exception:
            pass

    cache = {}
    current_time = time.time()
    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
        except Exception:
            pass

    cache = {k: v for k, v in cache.items() if (current_time - float(v)) < 86400}
    cache[symbol] = current_time

    try:
        with open('sent_signals.json', 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass

# ----------------------------------------------------
# 4. محرك معالجة الشروط
# ----------------------------------------------------
def process_market_and_signals(symbols_data_list, tasi_change_pct):
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

        try:
            avg_vol = float(symbol_data.get('avg_volume_20d', 0) or 0)
            curr_vol = float(symbol_data.get('volume', 0) or 0)
            price_chg = float(symbol_data.get('price_change_5m', 0) or 0)
        except (ValueError, TypeError):
            continue

        breakout = bool(symbol_data.get('instant_breakout', False))
        medium_tf = bool(symbol_data.get('medium_tf_trend', True))

        if is_recently_sent(symbol) or not medium_tf:
            continue

        is_vol_spike = curr_vol >= (avg_vol * 1.5) if avg_vol > 0 else False
        is_price_spike = price_chg >= 1.5

        if is_vol_spike or is_price_spike or breakout:
            msg = (
                f"🚀 *تنبيه إشارة إيجابية*\n\n"
                f"📊 السهم: *{symbol}*\n"
                f"📈 التغير اللحظي: *{price_chg}%*\n"
                f"💧 السيولة اللحظية: *{curr_vol}*"
            )
            print(f"🎯 إشارات مكتملة لـ {symbol}.. جاري الإرسال.")
            if send_telegram_message(msg):
                save_sent(symbol)

# ----------------------------------------------------
# 5. المشغل والمراقب الآلي (Main Loop)
# ----------------------------------------------------
def main():
    print("🚀 تم بدء تشغيل محرك الرصد والتنبيهات...")
    
    # رسالة تجريبية أولية للتأكد من ربط تليجرام فور تشغيل السكربت
    send_telegram_message("🤖 *بدء تشغيل بوت رصد الأسهم وتاسي بنجاح!*")

    while True:
        try:
            print("\n🔄 جاري فحص بيانات السوق الآن...")
            
            # --- أضف كود جلب البيانات الخاص بك هنا ---
            # مثال لبيانات تجريبية تحاكي تحقق الشروط لتأكيد الإرسال:
            market_data = [
                {
                    'symbol': '1120',  # الراجحي مثلاً
                    'volume': 1500000,
                    'avg_volume_20d': 800000, # تحقق شرط 1.5x للسيولة
                    'price_change_5m': 1.8,   # تحقق شرط 1.5%+
                    'instant_breakout': True,
                    'medium_tf_trend': True
                }
            ]
            tasi_pct = -0.2 # نسبة تاسي
            # ---------------------------------------

            # تشغيل الفحص
            process_market_and_signals(market_data, tasi_pct)

        except Exception as e:
            print(f"⚠️ خطأ غير متوقع في حلقة الفحص: {e}")

        # الانتظار لمدة 60 ثانية قبل الفحص التالي
        time.sleep(60)

if __name__ == "__main__":
    main()
