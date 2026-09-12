import os
import json
import time
import requests

# ----------------------------------------------------
# 1. بيانات تليجرام (تأكد من وضع القيم الخاصة بك)
# ----------------------------------------------------
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(f"⚠️ لم يتم وضع التوكن الخاص بتليجرام! الرسالة: {message}")
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
            print("✅ تم إرسال الرسالة بنجاح إلى تليجرام!")
        else:
            print(f"❌ خطأ من تليجرام: {r.text}")
    except Exception as e:
        print(f"⚠️ فشل الاتصال بتليجرام: {e}")


# ----------------------------------------------------
# 2. فحص التكرار (سجل الحظر)
# ----------------------------------------------------

def is_recently_sent(symbol):
    # فحص ملف JSON المحلي
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
# 3. دالة الفحص المحدثة مع طباعة أسباب التجاهل
# ----------------------------------------------------

def process_market_and_signals(symbols_data_list, tasi_change_pct):
    # 1. فحص تاسي
    if tasi_change_pct <= -1.0:
        if not is_recently_sent("TASI_ALERT"):
            send_telegram_message(f"🚨 *تنبيه مؤشر تاسي*\nتراجع المؤشر بنسبة: {tasi_change_pct}%")
            save_sent("TASI_ALERT")
        else:
            print("ℹ️ تم إرسال تنبيه تاسي سابقاً خلال 24 ساعة.")

    # 2. فحص الأسهم
    for symbol_data in symbols_data_list:
        symbol = symbol_data.get('symbol')
        avg_vol = symbol_data.get('avg_volume_20d', 0)
        curr_vol = symbol_data.get('volume', 0)
        price_chg = symbol_data.get('price_change_5m', 0)
        breakout = symbol_data.get('instant_breakout', False)
        medium_tf = symbol_data.get('medium_tf_trend', False)

        # فحص الحظر السابقي
        if is_recently_sent(symbol):
            print(f"⏭️ {symbol}: تم تجاهله لأنه أُرسل مؤخراً خلال 24 ساعة.")
            continue

        # فحص شرط التأكيد
        if not medium_tf:
            print(f"⛔ {symbol}: لم يرسل لأن الفاصل المتوسط غير مؤكد (medium_tf_trend = False).")
            continue

        # فحص الأسباب اللحظية
        is_vol_spike = curr_vol >= (avg_vol * 1.5) if avg_vol > 0 else False
        is_price_spike = price_chg >= 1.5

        if is_vol_spike or is_price_check or breakout:
            msg = f"🚀 *تنبيه إشارة إيجابية*\n\nالسهم: *{symbol}*\nالسيولة اللحظية: *{curr_vol}*\nالتغير اللحظي: *{price_chg}%*"
            send_telegram_message(msg)
            save_sent(symbol)
        else:
            print(f"ℹ️ {symbol}: تحقق شرط الاتجاه ولكن لم تتحقق أي إشارة لحظية (سيولة 1.5x أو اختراق أو تغير 1.5%+).")


# ----------------------------------------------------
# 4. تجربة سريعة (إرسال رسالة تجريبية الآن)
# ----------------------------------------------------
# للتأكد من أن تليجرام يعمل لديك، شغل السطر التالي مباشرة:
# send_telegram_message("اختبار ربط البوت بنجاح! 🎯")
