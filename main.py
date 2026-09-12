import os
import json
import time
import requests

# ====================================================
# 1. إعدادات فحص التكرار (Redis + JSON)
# ====================================================

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
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"💾 SET {symbol} -> status={r.status_code}")
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


# ====================================================
# 2. منطق التنبيهات وإشارات السوق
# ====================================================

def check_tasi_alert(tasi_change_pct):
    """
    إرسال تنبيه مستقل عند تراجع مؤشر تاسي بنسبة 1.0%- أو أكثر
    """
    if tasi_change_pct <= -1.0:
        if not is_recently_sent("TASI_ALERT"):
            print(f"🚨 تنبيه عاجل: تراجع مؤشر تاسي بنسبة {tasi_change_pct}%!")
            # ضع دالة إرسال الرسالة هنا (Telegram / WhatsApp)
            save_sent("TASI_ALERT")


def should_send_signal(symbol_data, avg_volume_20d):
    """
    اختبار شروط إرسال التنبيهات للأسهم:
    1. رصد السيولة اللحظية (Volume Spike) >= 1.5 ضعف متوسط 20 يوماً.
    2. رصد التغيرات اللحظية للسعر (>= 1.5%) أو الاختراقات السريعة.
    3. اشتراط تأكيد الاتجاه على الفاصل المتوسط لتجنب الإشارات الخاطئة.
    """
    current_volume = symbol_data.get('volume', 0)
    
    # الشروط اللحظية
    is_volume_spike = current_volume >= (avg_volume_20d * 1.5) if avg_volume_20d > 0 else False
    instant_breakout = symbol_data.get('instant_breakout', False)
    instant_price_change = symbol_data.get('price_change_5m', 0) >= 1.5

    # تأكيد الاتجاه على الفاصل المتوسط
    medium_tf_confirmed = symbol_data.get('medium_tf_trend', False)

    # إرسال التنبيه عند تحقق أحد الشروط اللحظية مع شرط التأكيد المتوسط
    if (instant_breakout or instant_price_change or is_volume_spike) and medium_tf_confirmed:
        return True

    return False


def process_market_and_signals(symbols_data_list, tasi_change_pct):
    """
    المحرك الرئيسي لمعالجة جميع أسهم السوق (230+ سهم) ومؤشر تاسي
    """
    # 1. فحص مؤشر تاسي أولاً وإرسال تنبيه مستقل عند التراجع
    check_tasi_alert(tasi_change_pct)

    # 2. المرور على كافة أسهم السوق في القائمة
    for symbol_data in symbols_data_list:
        symbol = symbol_data['symbol']
        avg_volume_20d = symbol_data.get('avg_volume_20d', 0)

        # منع تكرار السهم إذا أُرسل له تنبيه خلال الـ 24 ساعة الماضية
        if is_recently_sent(symbol):
            continue

        # فحص الشروط الفنية لكل سهم
        if should_send_signal(symbol_data, avg_volume_20d):
            print(f"🚀 إرسال تنبيه للسهم: {symbol}")
            # ضع دالة إرسال تنبيه السهم هنا
            save_sent(symbol)
