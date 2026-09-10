import os
import json
import time
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import telebot

# 1. جلب بيانات الاعتماد من البيئة (Secrets)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

UPSTASH_REDIS_REST_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_REST_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

SYMBOLS = [
    '1120.SR', '1150.SR', '2010.SR', '2020.SR', '2060.SR', '2030.SR', '2170.SR', '2210.SR', '2222.SR', '2250.SR', '2290.SR', '2310.SR', '2330.SR', '2350.SR', '2380.SR', '2381.SR', '2382.SR',
    '1201.SR', '1202.SR', '1210.SR', '1211.SR', '1212.SR', '1213.SR', '1214.SR', '1301.SR', '1302.SR', '1303.SR', '1304.SR', '1320.SR', '1321.SR', '1322.SR', '2001.SR', '2090.SR', '2150.SR', '2180.SR', '2200.SR', '2220.SR', '3001.SR', '3002.SR', '3003.SR', '3004.SR', '3005.SR', '3007.SR', '3008.SR', '3010.SR', '3020.SR', '3030.SR', '3040.SR', '3050.SR', '3060.SR', '3080.SR', '3090.SR', '3091.SR',
    '7010.SR', '7020.SR', '7030.SR', '7200.SR', '7201.SR', '7202.SR', '7203.SR', '7204.SR',
    '2070.SR', '2284.SR', '4003.SR', '4013.SR', '4014.SR', '4015.SR',
    '1810.SR', '1830.SR', '1831.SR', '1832.SR', '1833.SR', '2050.SR', '2080.SR', '2081.SR', '2082.SR', '2100.SR', '2110.SR', '2130.SR', '2140.SR', '2160.SR', '2190.SR', '2270.SR', '2280.SR', '2281.SR', '2282.SR', '2283.SR', '2320.SR', '4001.SR', '4002.SR', '4004.SR', '4007.SR', '4009.SR', '4012.SR', '4030.SR', '4040.SR', '4050.SR', '4070.SR', '4071.SR', '4080.SR', '4081.SR', '4082.SR', '4160.SR', '4161.SR', '4162.SR', '4163.SR', '4164.SR', '4190.SR', '4191.SR', '4192.SR', '4200.SR', '4240.SR', '6001.SR', '6002.SR', '6010.SR', '6012.SR', '6013.SR', '6014.SR', '6015.SR', '6020.SR', '6040.SR', '6050.SR', '6060.SR', '6070.SR', '6090.SR',
    '4031.SR', '4260.SR', '4261.SR', '4262.SR', '4263.SR', '4020.SR', '4100.SR', '4130.SR', '4140.SR', '4150.SR', '4220.SR', '4230.SR', '4250.SR', '4300.SR', '4310.SR', '4320.SR', '4321.SR', '4322.SR', '2083.SR', '2084.SR', '4061.SR', '5110.SR'
]

# --- آلية التكرار ---
def is_recently_sent(symbol):
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            res = requests.get(url, headers=headers).json()
            return res.get("result") is not None
        except Exception:
            pass
    
    if os.path.exists('sent_signals.json'):
        try:
            with open('sent_signals.json', 'r') as f:
                cache = json.load(f)
                if symbol in cache and (time.time() - cache[symbol]) < 86400:
                    return True
        except Exception:
            pass
    return False

def save_sent(symbol):
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/set/{symbol}/SENT/EX/86400"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            requests.get(url, headers=headers)
        except Exception:
            pass
    
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

# --- دالة فحص الدايفرجنس الإيجابي العادي والمخفي ---
def detect_divergence(closes, rsi):
    try:
        if len(closes) < 15:
            return "غير محدد"

        p1_price, p2_price = closes[-15], closes[-1]
        p1_rsi, p2_rsi = rsi[-15], rsi[-1]

        # دايفرجنس إيجابي عادي (قاع أدنى للسعر مع قاع أعلى للـ RSI)
        if p2_price < p1_price and p2_rsi > p1_rsi:
            return "إيجابي عادي 🟢"
        
        # دايفرجنس إيجابي مخفي (قاع أعلى للسعر مع قاع أدنى للـ RSI)
        if p2_price > p1_price and p2_rsi < p1_rsi:
            return "إيجابي مخفي 🟣"
    except Exception:
        pass
    return "لا يوجد"

def analyze_stock(ticker):
    try:
        symbol_code = ticker.replace('.SR', '')

        if is_recently_sent(symbol_code):
            return None

        # تنظيف وتحميل البيانات لتجنب أخطاء MultiIndex
        df = yf.download(ticker, period='150d', interval='1d', progress=False)
        if df.empty or len(df) < 50:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, level=1, axis=1)

        closes = df['Close'].dropna()
        if len(closes) < 50:
            return None

        # حساب المتوسطات المتحركة EMA Clouds
        ema8 = closes.ewm(span=8, adjust=False).mean()
        ema21 = closes.ewm(span=21, adjust=False).mean()
        ema34 = closes.ewm(span=34, adjust=False).mean()
        ema50 = closes.ewm(span=50, adjust=False).mean()

        # حساب RSI
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # القيم الأخيرة
        c_val = float(closes.iloc[-1])
        rsi_val = float(rsi.iloc[-1])
        e8_val = float(ema8.iloc[-1])
        e21_val = float(ema21.iloc[-1])
        e34_val = float(ema34.iloc[-1])
        e50_val = float(ema50.iloc[-1])

        # الشروط:
        # 1. سحابة (8-21) صاعدة
        # 2. سحابة (34-50) صاعدة
        # 3. RSI أكبر من 55
        if (e8_val > e21_val) and (e34_val > e50_val) and (rsi_val > 55.0):
            div_status = detect_divergence(closes.values, rsi.values)

            # الأهداف الأربعة
            t1 = round(c_val * 1.02, 2)
            t2 = round(c_val * 1.04, 2)
            t3 = round(c_val * 1.06, 2)
            t4 = round(c_val * 1.08, 2)

            # وقف الخسارة
            stop_near = round(e21_val, 2)
            stop_bloody = round(e50_val, 2)

            return {
                'symbol': symbol_code,
                'entry': round(c_val, 2),
                'rsi': round(rsi_val, 2),
                'mid_cloud': f"{round(e8_val, 2)} / {round(e21_val, 2)}",
                'long_cloud': f"{round(e34_val, 2)} / {round(e50_val, 2)}",
                'divergence': div_status,
                't1': t1, 't2': t2, 't3': t3, 't4': t4,
                'stop_near': stop_near,
                'stop_bloody': stop_bloody,
                'investing_url': f"https://sa.investing.com/search/?q={symbol_code}",
                'tv_url': f"https://ar.tradingview.com/chart/?symbol=TADAWUL%3A{symbol_code}"
            }
    except Exception as e:
        print(f"خطأ في معالجة {ticker}: {e}")
    return None

def main():
    print("بدء فحص الأسهم...")
    signals = []

    for symbol in SYMBOLS:
        res = analyze_stock(symbol)
        if res:
            signals.append(res)

    if signals:
        message = "🎯 **تنبيه فرصة جديدة (سحابات EMA والدايفرجنس)** 🎯\n\n"
        for s in signals:
            message += f"🔹 **السهم:** `{s['symbol']}`\n"
            message += f"📍 **نقطة الدخول:** {s['entry']} ريال\n"
            message += f"📈 **RSI:** {s['rsi']}\n"
            message += f"☁️ **سحابة المتوسط (8-21):** {s['mid_cloud']}\n"
            message += f"☁️ **سحابة الاتجاه (34-50):** {s['long_cloud']}\n"
            message += f"🔄 **الدايفرجنس:** {s['divergence']}\n"
            message += "-------------------\n"
            message += f"🎯 **الهدف 1 (2%+):** {s['t1']} ريال\n"
            message += f"🎯 **الهدف 2 (4%+):** {s['t2']} ريال\n"
            message += f"🎯 **الهدف 3 (6%+):** {s['t3']} ريال\n"
            message += f"🎯 **الهدف 4 (8%+):** {s['t4']} ريال\n"
            message += "-------------------\n"
            message += f"🛑 **وقف الخسارة القريب (EMA 21):** {s['stop_near']} ريال\n"
            message += f"🩸 **الوقف الدموي (EMA 50):** {s['stop_bloody']} ريال\n"
            message += "-------------------\n"
            message += f"📈 [الشارت المباشر (TradingView)]({s['tv_url']})\n"
            message += f"📰 [أخبار وإفصاحات السهم (Investing.com)]({s['investing_url']})\n"
            message += "===================\n"

            save_sent(s['symbol'])

        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown', disable_web_page_preview=True)
        print(f"تم إرسال {len(signals)} تنبيه بنجاح.")
    else:
        print("لا توجد فرصة مطابقة حالياً.")

if __name__ == '__main__':
    main()
