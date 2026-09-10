import os
import yfinance as yf
import pandas as pd
import telebot

# 1. جلب بيانات الاعتماد من البيئة (Secrets)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 2. قائمة أسهم تجريبية
SYMBOLS = ['1120.SR', '2222.SR', '7010.SR']

def main():
    print("بدء إرسال رسالة الاختبار إلى التلجرام...")
    
    message = "🧪 **رسالة اختبار - بوت السوق السعودي** 🧪\n\n"
    message += "إذا وصلتك هذه الرسالة، فهذا يعني أن ربط التلجرام يعمل بنجاح 100%! ✅\n\n"
    message += "📊 **أسعار بعض الأسهم الحالية:**\n"

    for ticker in SYMBOLS:
        try:
            df = yf.download(ticker, period='5d', interval='1d', progress=False)
            if not df.empty:
                last_price = round(float(df['Close'].iloc[-1]), 2)
                symbol_name = ticker.replace('.SR', '')
                message += f"🔹 **السهم {symbol_name}:** {last_price} ريال\n"
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    # إرسال الرسالة إلى التلجرام
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        print("تم إرسال رسالة الاختبار بنجاح إلى التلجرام!")
    except Exception as e:
        print(f"فشل إرسال الرسالة إلى التلجرام. السبب: {e}")

if __name__ == '__main__':
    main()
