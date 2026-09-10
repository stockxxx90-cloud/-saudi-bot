import os
import json
import time
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import telebot

# 1. جلب بيانات الاعتماد من البيئة
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

UPSTASH_REDIS_REST_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_REST_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ خطأ: يرجى إضافة TELEGRAM_TOKEN و TELEGRAM_CHAT_ID في GitHub Secrets أولاً!")
    exit(0)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

SYMBOLS = [
    '1120.SR', '1150.SR', '2010.SR', '2020.SR', '2060.SR', '2030.SR', '2170.SR', '2210.SR', '2222.SR', '2250.SR', '2290.SR', '2310.SR', '2330.SR', '2350.SR', '2380.SR', '2381.SR', '2382.SR',
    '1201.SR', '1202.SR', '1210.SR', '1211.SR', '1212.SR', '1213.SR', '1214.SR', '1301.SR', '1302.SR', '1303.SR', '1304.SR', '1320.SR', '1321.SR', '1322.SR', '2001.SR', '2090.SR', '2150.SR', '2180.SR', '2200.SR', '2220.SR', '3001.SR', '3002.SR', '3003.SR', '3004.SR', '3005.SR', '3007.SR', '3008.SR', '3010.SR', '3020.SR', '3030.SR', '3040.SR', '3050.SR', '3060.SR', '3080.SR', '3090.SR', '3091.SR',
    '7010.SR', '7020.SR', '7030.SR', '7200.SR', '7201.SR', '7202.SR', '7203.SR', '7204.SR',
    '2070.SR', '2284.SR', '4003.SR', '4013.SR', '4014.SR', '4015.SR',
    '1810.SR', '1830.SR', '1831.SR', '1832.SR', '1833.SR', '2050.SR', '2080.SR', '2081.SR', '2082.SR', '2100.SR', '2110.SR', '2130.SR', '2140.SR', '2160.SR', '2190.SR', '2270.SR', '2280.SR', '2281.SR', '2282.SR', '2283.SR', '2320.SR', '4001.SR', '4002.SR', '4004.SR', '4007.SR', '4009.SR', '4012.SR', '4030.SR', '4040.SR', '4050.SR', '4070.SR', '4071.SR', '4080.SR', '4081.SR', '4082.SR', '4160.SR', '4161.SR', '4162.SR', '4163.SR', '4164.SR', '4190.SR', '4191.SR', '4192.SR', '4200.SR', '4240.SR', '6001.SR', '6002.SR', '6010.SR', '6012.SR', '6013.SR', '6014.SR', '6015.SR', '6020.SR', '6040.SR', '6050.SR', '6060.SR', '6070.SR', '6090.SR',
    '4031.SR', '4260.SR', '4261.SR', '4262.SR', '4263.SR', '4020.SR', '4100.SR', '4130.SR', '4140.SR', '4150.SR', '4220.SR', '4230.SR', '4250.SR', '4300.SR', '4310.SR', '4320.SR', '4321.SR', '4322.SR', '2083.SR', '2084.SR', '4061.SR', '5110.SR'
]

# --- آلية الحظر الدقيقة (منع التكرار خلال 24 ساعة) ---
def is_recently_sent(symbol):
    # 1. فحص القاعدة السحابية Redis
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            res = requests.get(url, headers=headers).json()
            if res.get("result") is not None:
                return True
        except Exception:
            pass
    
    # 2. فحص السجل المحلي
    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
                if symbol in cache and (time.time() - cache[symbol]) < 86400: # 86400 ثانية = 24 ساعة
                    return True
        except Exception:
            pass
    return False

def save_sent(symbol):
    # 1. حفظ في القاعدة السحابية مع وقت انتهاء تلقائي (24 ساعة)
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/set/{symbol}/SENT/EX/86400"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            requests.get(url, headers=headers)
        except Exception:
            pass
    
    # 2. حفظ في السجل المحلي
    cache = {}
    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
        except Exception:
            pass
    cache[symbol] = time.time()
    try:
        with open('sent_signals.json', 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass

# --- فحص الدايفرنجس ---
def detect_divergence(closes, rsi):
    try:
        if len(closes) < 15:
            return ""

        p1_price, p2_price = closes[-15], closes[-1]
        p1_rsi, p2_rsi = rsi[-15], rsi[-1]

        if (p2_price < p1_price and p2_rsi > p1_rsi) or (p2_price > p1_price and p2_rsi < p1_rsi):
            return "✅"
    except Exception:
        pass
    return ""

def analyze_stock(ticker):
    try:
        symbol_code = ticker.replace('.SR', '')

        # التأكد المباشر قبل التحليل: إذا أُرسل السهم سابقاً يتم إغلاق التحليل وتخطيه فوراً
        if is_recently_sent(symbol_code):
            return None

        stock = yf.Ticker(ticker)
        df = stock.history(period='150d', interval='1d')
        if df.empty or len(df) < 50:
            return None

        info = stock.info
        company_name = info.get('shortName', symbol_code)
        sector_name = info.get('sector', 'تداول')

        closes = df['Close'].dropna()
        volumes = df['Volume'].dropna()
        
        if len(closes) < 50:
            return None

        price_change_pct = round(((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]) * 100, 2)
        avg_vol = volumes.iloc[-20:-1].mean()
        vol_change_pct = round(((volumes.iloc[-1] - avg_vol) / avg_vol) * 100, 2) if avg_vol > 0 else 0

        ema8 = closes.ewm(span=8, adjust=False).mean()
        ema21 = closes.ewm(span=21, adjust=False).mean()
        ema34 = closes.ewm(span=34, adjust=False).mean()
        ema50 = closes.ewm(span=50, adjust=False).mean()

        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        c_val = float(closes.iloc[-1])
        rsi_val = float(rsi.iloc[-1])
        e8_val = float(ema8.iloc[-1])
        e21_val = float(ema21.iloc[-1])
        e34_val = float(ema34.iloc[-1])
        e50_val = float(ema50.iloc[-1])

        if (e8_val > e21_val) and (e34_val > e50_val) and (rsi_val > 55.0):
            div_status = detect_divergence(closes.values, rsi.values)
            trend = "صاعد 📈" if e8_val > e21_val and e34_val > e50_val else "تذبذب"

            return {
                'symbol': symbol_code,
                'company': company_name,
                'sector': sector_name,
                'rsi': round(rsi_val, 2),
                'cloud': f"{round(e8_val, 2)} / {round(e21_val, 2)}",
                'trend': trend,
                'vol_change': vol_change_pct,
                'price_change': price_change_pct,
                'divergence': div_status,
                'tv_url': f"https://ar.tradingview.com/chart/?symbol=TADAWUL%3A{symbol_code}"
            }
    except Exception as e:
        print(f"خطأ في معالجة السهم {ticker}: {e}")
    return None

def main():
    print("بدء فحص الأسهم...")
    signals_count = 0

    for symbol in SYMBOLS:
        s = analyze_stock(symbol)
        if s:
            msg = f"**الرمز:** {s['symbol']}\n"
            msg += f"**الشركة:** {s['company']}\n"
            msg += f"**القطاع:** {s['sector']}\n"
            msg += f"**Rsi:** {s['rsi']}\n"
            msg += f"**سحابة المتوسط:** {s['cloud']}\n"
            msg += f"**الاتجاه:** {s['trend']}\n"
            msg += f"**تغير الحجم:** %{s['vol_change']}\n"
            msg += f"**تغير السعر اليومي:** %{s['price_change']}\n"
            msg += f"**الدايفرنجس:** {s['divergence']}\n\n"
            msg += f"📈 [الشارت المباشر]({s['tv_url']})"

            try:
                bot.send_message(TELEGRAM_CHAT_ID, msg, parse_mode='Markdown', disable_web_page_preview=True)
                # تسجيل السهم فوراً للحظر لمدة 24 ساعة
                save_sent(s['symbol'])
                signals_count += 1
                time.sleep(0.5)
            except Exception as e:
                print(f"خطأ في إرسال السهم {s['symbol']}: {e}")

    print(f"تم الانتهاء. إجمالي التنبيهات المرسلة: {signals_count}")

if __name__ == '__main__':
    main()
