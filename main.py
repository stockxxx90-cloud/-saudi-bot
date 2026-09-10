import os
import yfinance as yf
import pandas as pd
import numpy as np
import telebot

# 1. جلب بيانات الاعتماد من البيئة (Secrets)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 2. قائمة أسهم السوق السعودي (يمكنك إضافة أي أسهم أخرى بالصيغة: XXXX.SR)
SYMBOLS = [
    '1120.SR', '1150.SR', '1180.SR', '2010.SR', '2222.SR', 
    '2380.SR', '7010.SR', '7020.SR', '4190.SR', '1211.SR',
    '2082.SR', '4030.SR', '1831.SR', '1010.SR', '1183.SR'
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

        # حساب متوسط السيولة/الحجم (SMA Volume 20)
        df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()

        # القراءات الأخيرة
        last = df.iloc[-1]

        # الشروط الشاملة:
        # 1. تقاطع صاعد/سعر أعلى المتوسطات (EMA 9 > EMA 21)
        ema_bullish = bool(last['EMA_9'].iloc[0] > last['EMA_21'].iloc[0]) if isinstance(last['EMA_9'], pd.Series) else bool(last['EMA_9'] > last['EMA_21'])
        
        # 2. مؤشر القوة النسبية أعلى من 55
        rsi_val = float(last['RSI'].iloc[0]) if isinstance(last['RSI'], pd.Series) else float(last['RSI'])
        rsi_bullish = rsi_val > 55

        # 3. حجم التداول أعلى من المتوسط (فلترة السيولة)
        vol_val = float(last['Volume'].iloc[0]) if isinstance(last['Volume'], pd.Series) else float(last['Volume'])
        vol_sma_val = float(last['Vol_SMA'].iloc[0]) if isinstance(last['Vol_SMA'], pd.Series) else float(last['Vol_SMA'])
        volume_bullish = vol_val > vol_sma_val

        if ema_bullish and rsi_bullish and volume_bullish:
            close_price = float(last['Close'].iloc[0]) if isinstance(last['Close'], pd.Series) else float(last['Close'])
            ema9_val = float(last['EMA_9'].iloc[0]) if isinstance(last['EMA_9'], pd.Series) else float(last['EMA_9'])
            ema21_val = float(last['EMA_21'].iloc[0]) if isinstance(last['EMA_21'], pd.Series) else float(last['EMA_21'])

            return {
                'symbol': ticker.replace('.SR', ''),
                'price': round(close_price, 2),
                'rsi': round(rsi_val, 2),
                'ema9': round(ema9_val, 2),
                'ema21': round(ema21_val, 2)
            }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
    return None

def main():
    print("بدء فحص أسهم السوق السعودي وفق الاستراتيجية...")
    signals = []
    
    for symbol in SYMBOLS:
        result = analyze_stock(symbol)
        if result:
            signals.append(result)

    if signals:
        message = "🚀 **تنبيه فرصة - السوق السعودي** 🚀\n\n"
        for s in signals:
            message += f"🔹 **السهم:** `{s['symbol']}`\n"
            message += f"📊 **السعر الحالي:** {s['price']} ريال\n"
            message += f"📈 **RSI:** {s['rsi']}\n"
            message += f"☁️ **EMA 9 / 21:** {s['ema9']} / {s['ema21']}\n"
            message += "-------------------\n"
        
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        print(f"تم إرسال {len(signals)} تنبيه إلى التلجرام.")
    else:
        print("لا توجد أسهم تطابق شروط الاستراتيجية حالياً.")

if __name__ == '__main__':
    main()
