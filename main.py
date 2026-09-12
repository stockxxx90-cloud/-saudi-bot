import os
import json
import time
import requests

# ----------------------------------------------------
# 1. جلب البيئة والمفاتيح من GitHub Secrets / Environment
# ----------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()

def send_telegram_message(message):
    """دالة إرسال الرسائل إلى تليجرام"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ خطأ: لم يتم ضبط TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID في Secrets!")
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
            print("✅ تم الإرسال إلى تليجرام بنجاح!")
            return True
        else:
            print(f"❌ خطأ تليجرام: {res.get('description')}")
            return False
    except Exception as e:
        print(f"⚠️ فشل الاتصال بتليجرام: {e}")
        return False

# ----------------------------------------------------
# 2. إعدادات فحص التكرار (Redis + JSON)
# ----------------------------------------------------
def is_recently_sent(symbol):
    """التحقق من إرسال التنبيه للسهم خلال الـ 24 ساعة الماضية"""
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200 and r.json().get("result") is not None:
                return True
        except Exception as e:
            print(f"⚠️ فشل القراءة من Redis لـ {symbol}: {e}")

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
    """تسجيل السهم كـ أُرسل لمنع التكرار"""
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
    except Exception as e:
        print(f"⚠️ فشل كتابة الملف المحلي: {e}")

# ----------------------------------------------------
# 3. محرك معالجة الشروط ورصد السوق
# ----------------------------------------------------
def process_market_and_signals(symbols_data_list, tasi_change_pct):
    """فحص الأسهم ومؤشر تاسي وتطبيق الشروط"""
    try:
        tasi_change_pct = float(tasi_change_pct)
    except (ValueError, TypeError):
        tasi_change_pct = 0.0

    # 1. تنبيه تاسي عند التراجع 1%- أو أكثر
    if tasi_change_pct <= -1.0:
        if not is_recently_sent("TASI_ALERT"):
            msg = f"🚨 *تنبيه حماية السوق*\n\nتراجع مؤشر تاسي (TASI) بنسبة: *{tasi_change_pct}%*"
            if send_telegram_message(msg):
                save_sent("TASI_ALERT")

    # 2. فحص أسهم السوق
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

        # شروط الفحص اللحظية
        is_vol_spike = curr_vol >= (avg_vol * 1.5) if avg_vol > 0 else False
        is_price_spike = price_chg >= 1.5

        if is_vol_spike or is_price_spike or breakout:
            msg = (
                f"🚀 *تنبيه إشارة إيجابية*\n\n"
                f"📊 السهم: *{symbol}*\n"
                f"📈 التغير اللحظي: *{price_chg}%*\n"
                f"💧 السيولة اللحظية: *{curr_vol}*"
            )
            print(f"🎯 إشارة مكتملة للسهم {symbol}، جاري الإرسال...")
            if send_telegram_message(msg):
                save_sent(symbol)

# ----------------------------------------------------
# 4. نقطة الانطلاق الرئيسية (One-Shot Execution)
# ----------------------------------------------------
def main():
    print("🚀 بدء تنفيذ الفحص لبيانات السوق...")

    # مثال لإدراج البيانات أو استدعاء الدالة الخاصة بك التي تجلب بيانات الأسهم الحية:
    # market_data = fetch_your_live_market_data()
    market_data = [
        {
            'symbol': '1120',
            'volume': 1500000,
            'avg_volume_20d': 800000,
            'price_change_5m': 1.8,
            'instant_breakout': True,
            'medium_tf_trend': True
        }
    ]
    tasi_pct = -0.2

    # تشغيل الفحص لمرة واحدة لإنهاء العمل بنجاح على GitHub Actions
    process_market_and_signals(market_data, tasi_pct)
    print("✅ اكتمل الفحص بنجاح وانتهت الجلسة.")

if __name__ == "__main__":
    main()
