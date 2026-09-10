import os
import yfinance as yf
import pandas as pd
import numpy as np
import telebot

# 1. جلب بيانات الاعتماد من البيئة (Secrets)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 2. قائمة بالأسهم السعودية (رموز تداول مع ملحق .SR)
# يمكنك إضافة أو تعديل الرموز حسب رغبتك
SYMBOLS = [
    '1120.SR', '1150.SR', '1180.SR', '2010.SR', '2222.SR', 
    '2380.SR', '7010.SR', '7020.SR', '4190.SR', '1211.SR'
]

def analyze_stock(ticker):
    try:
        # تحميل بيانات آخر 100 يوم
        df = yf.download(ticker, period='100d', interval='1d', progress=False)
        if len(df) < 50:
            return None

        # حساب المتوسطات المتحركة (EMA Cloud)
        df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()

        # حساب مؤشر القوة النسبية (RSI 14)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # حساب متوسط السيولة/الحجم (SMA Volume)
        df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()

        # القراءات الأخيرة
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # الشروط:
        # 1. تقاطع صاعد أو تداول أعلى المتوسطات (EMA Cloud)
        ema_bullish = last['EMA_9'] > last['EMA_21']
        
        # 2. مؤشر القوة النسبية أعلى من 55
        rsi_bullish = last['RSI'] > 55

        # 3. حجم التداول أعلى من المتوسط (شرط السيولة)
        volume_bullish = last['Volume'] > last['Vol_SMA']

        if ema_bullish and rsi_bullish and volume_bullish:
            return {
                'symbol': ticker.replace('.SR', ''),
                'price': round(float(last['Close']), 2),
                'rsi': round(float(last['RSI']), 2),
                'ema9': round(float(last['EMA_9']), 2),
                'ema21': round(float(last['EMA_21']), 2)
            }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
    return None

def main():
    print("بدء فحص السوق السعودي...")
    signals = []
    
    for symbol in SYMBOLS:
        result = analyze_stock(symbol)
        if result:
            signals.append(result)

    if signals:
        message = "🚀 **تنبيه فرصة - السوق السعودي** 🚀\n\n"
        for s in signals:
            message += f"🔹 **السهم:** `{s['symbol']}`\n"
            message += f"📊 **السعر الحالي:** {s['price']}\n"
            message += f"📈 **RSI:** {s['rsi']}\n"
            message += f"☁️ **EMA 9 / 21:** {s['ema9']} / {s['ema21']}\n"
            message += "-------------------\n"
        
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        print(f"تم إرسال {len(signals)} تنبيه إلى التلجرام.")
    else:
        print("لا توجد أسهم تطابق الشروط حالياً.")

if __name__ == '__main__':
    main()
