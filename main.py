import os
import json
import time
import yfinance as yf
import pandas as pd
import numpy as np
import telebot
from datetime import datetime

# 1. جلب بيانات الاعتماد من البيئة (Secrets)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 2. القائمة الشاملة لأسهم السوق الرئيسي المفلترة
SYMBOLS = [
    # المصارف المسموحة
    '1120.SR', '1150.SR',
    # الطاقة والبتروكيماويات
    '2010.SR', '2020.SR', '2060.SR', '2030.SR', '2170.SR', '2210.SR', '2222.SR', '2250.SR', '2290.SR', '2310.SR', '2330.SR', '2350.SR', '2380.SR', '2381.SR', '2382.SR',
    # المواد الأساسية والمعادن والأسمنت
    '1201.SR', '1202.SR', '1210.SR', '1211.SR', '1212.SR', '1213.SR', '1214.SR', '1301.SR', '1302.SR', '1303.SR', '1304.SR', '1320.SR', '1321.SR', '1322.SR', '2001.SR', '2090.SR', '2150.SR', '2180.SR', '2200.SR', '2220.SR', '3001.SR', '3002.SR', '3003.SR', '3004.SR', '3005.SR', '3007.SR', '3008.SR', '3010.SR', '3020.SR', '3030.SR', '3040.SR', '3050.SR', '3060.SR', '3080.SR', '3090.SR', '3091.SR',
    # الاتصالات والتقنية
    '7010.SR', '7020.SR', '7030.SR', '7200.SR', '7201.SR', '7202.SR', '7203.SR', '7204.SR',
    # الرعاية الصحية والأدوية
    '2070.SR', '2284.SR', '4003.SR', '4013.SR', '4014.SR', '4015.SR',
    # التجزئة والأغذية والمطاحن والسلع الاستهلاكية
    '1810.SR', '1830.SR', '1831.SR', '1832.SR', '1833.SR', '2050.SR', '2080.SR', '2081.SR', '2082.SR', '2100.SR', '2110.SR', '2130.SR', '2140.SR', '2160.SR', '2190.SR', '2270.SR', '2280.SR', '2281.SR', '2282.SR', '2283.SR', '2320.SR', '4001.SR', '4002.SR', '4004.SR', '4007.SR', '4009.SR', '4012.SR', '4030.SR', '4040.SR', '4050.SR', '4070.SR', '4071.SR', '4080.SR', '4081.SR', '4082.SR', '4160.SR', '4161.SR', '4162.SR', '4163.SR', '4164.SR', '4190.SR', '4191.SR', '4192.SR', '4200.SR', '4240.SR', '6001.SR', '6002.SR', '6010.SR', '6012.SR', '6013.SR', '6014.SR', '6015.SR', '6020.SR', '6040.SR', '6050.SR', '6060.SR', '6070.SR', '6090.SR',
    # النقل والخدمات اللوجستية
    '4031.SR', '4260.SR', '4261.SR', '4262.SR', '4263.SR',
    # إدارة وتطوير العقارات
    '4020.SR', '4100.SR', '4130.SR', '4140.SR', '4150.SR', '4220.SR', '4230.SR', '4250.SR', '4300.SR', '4310.SR', '4320.SR', '4321.SR', '4322.SR', '2083.SR', '2084.SR', '4061.SR', '5110.SR'
]

CACHE_FILE = 'sent_signals.json'
NEWS_MAX_AGE_HOURS = 48  # لا تُرسل خبراً أقدم من هذا حتى عند أول تشغيل


def load_cache():
    """
    شكل الكاش الجديد لكل سهم:
    {
      "1120": {
          "was_bullish": true/false,   # هل كانت الشروط محققة في آخر فحص
          "last_alert_price": 32.5,    # آخر سعر تم التنبيه عنده
          "last_news_id": "abcd123"    # معرّف آخر خبر تم إرساله
      }
    }
    """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # توافق مع الكاش القديم (كان مجرد timestamp رقمي لكل رمز)
                migrated = {}
                for sym, val in data.items():
                    if isinstance(val, dict):
                        migrated[sym] = val
                    else:
                        migrated[sym] = {"was_bullish": True, "last_alert_price": None, "last_news_id": None}
                return migrated
        except Exception:
            return {}
    return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving cache: {e}")


def get_latest_news(ticker):
    """
    يجلب أحدث خبر حقيقي للسهم من yfinance.
    يعيد dict فيه id, title, link, publish_time أو None إن لم يوجد خبر مناسب.
    """
    try:
        news_items = yf.Ticker(ticker).news
        if not news_items:
            return None

        for item in news_items:
            # بعض إصدارات yfinance تضع البيانات مباشرة، وبعضها تحت مفتاح 'content'
            content = item.get('content', item)

            news_id = item.get('id') or content.get('id') or content.get('title')
            title = content.get('title') or content.get('summary')
            link = (
                content.get('canonicalUrl', {}).get('url')
                if isinstance(content.get('canonicalUrl'), dict)
                else content.get('link') or content.get('clickThroughUrl', {}).get('url')
            )
            pub_date = content.get('pubDate') or item.get('providerPublishTime')

            # تطبيع الوقت إلى timestamp
            pub_ts = None
            if isinstance(pub_date, (int, float)):
                pub_ts = float(pub_date)
            elif isinstance(pub_date, str):
                try:
                    pub_ts = datetime.fromisoformat(pub_date.replace('Z', '+00:00')).timestamp()
                except Exception:
                    pub_ts = None

            if not title or not link:
                continue

            if pub_ts and (time.time() - pub_ts) > NEWS_MAX_AGE_HOURS * 3600:
                continue

            return {
                'id': str(news_id) if news_id else title,
                'title': title,
                'link': link,
            }
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")

    return None


def analyze_stock(ticker):
    try:
        symbol_code = ticker.replace('.SR', '')

        df = yf.download(ticker, period='100d', interval='1d', progress=False)

        if df.empty or len(df) < 50:
            return None

        last_vol = float(df['Volume'].iloc[-1].iloc[0]) if isinstance(df['Volume'].iloc[-1], pd.Series) else float(df['Volume'].iloc[-1])
        if last_vol == 0:
            return None

        # حساب EMA
        df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()

        # حساب RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))

        df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()

        last = df.iloc[-1]

        rsi_val = float(last['RSI'].iloc[0]) if isinstance(last['RSI'], pd.Series) else float(last['RSI'])
        ema9_val = float(last['EMA_9'].iloc[0]) if isinstance(last['EMA_9'], pd.Series) else float(last['EMA_9'])
        ema21_val = float(last['EMA_21'].iloc[0]) if isinstance(last['EMA_21'], pd.Series) else float(last['EMA_21'])
        vol_val = float(last['Volume'].iloc[0]) if isinstance(last['Volume'], pd.Series) else float(last['Volume'])
        vol_sma_val = float(last['Vol_SMA'].iloc[0]) if isinstance(last['Vol_SMA'], pd.Series) else float(last['Vol_SMA'])
        close_price = float(last['Close'].iloc[0]) if isinstance(last['Close'], pd.Series) else float(last['Close'])

        # شروط الدخول
        ema_bullish = ema9_val > ema21_val
        rsi_bullish = rsi_val > 55.0
        volume_bullish = vol_val > vol_sma_val

        is_bullish = ema_bullish and rsi_bullish and volume_bullish

        return {
            'symbol': symbol_code,
            'ticker': ticker,
            'is_bullish': is_bullish,
            'price': round(close_price, 2),
            'rsi': round(rsi_val, 2),
            'ema9': round(ema9_val, 2),
            'ema21': round(ema21_val, 2),
        }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
    return None


def main():
    print("بدء فحص كامل أسهم السوق الرئيسي المفلترة...")
    cache = load_cache()
    signals = []

    for symbol in SYMBOLS:
        result = analyze_stock(symbol)
        if result is None:
            continue

        symbol_code = result['symbol']
        prev = cache.get(symbol_code, {"was_bullish": False, "last_alert_price": None, "last_news_id": None})

        # === منع التكرار: نرسل فقط عند حدوث تحوّل جديد (من غير محقق إلى محقق) ===
        fresh_crossover = result['is_bullish'] and not prev.get('was_bullish', False)

        # تحديث حالة السهم دائماً (سواء صعودي أو لا) حتى نكتشف التحوّل القادم بشكل صحيح
        cache[symbol_code] = {
            "was_bullish": result['is_bullish'],
            "last_alert_price": result['price'] if fresh_crossover else prev.get('last_alert_price'),
            "last_news_id": prev.get('last_news_id'),
        }

        if not fresh_crossover:
            continue

        # === جلب خبر حقيقي حديث للسهم (إن وجد) ===
        news = get_latest_news(result['ticker'])
        news_is_new = news and news['id'] != prev.get('last_news_id')
        if news:
            cache[symbol_code]['last_news_id'] = news['id']

        result['news'] = news if news_is_new else None
        signals.append(result)

    if signals:
        message = "🚀 **تنبيه فرصة جديدة - السوق السعودي** 🚀\n\n"
        for s in signals:
            message += f"🔹 **السهم:** `{s['symbol']}`\n"
            message += f"📊 **السعر الحالي:** {s['price']} ريال\n"
            message += f"📈 **RSI:** {s['rsi']}\n"
            message += f"☁️ **EMA 9 / 21:** {s['ema9']} / {s['ema21']}\n"
            message += f"📈 [الشارت المباشر (TradingView)](https://ar.tradingview.com/chart/?symbol=TADAWUL%3A{s['symbol']})\n"
            if s.get('news'):
                message += f"📰 [{s['news']['title']}]({s['news']['link']})\n"
            else:
                message += f"📰 [بحث عن أخبار السهم](https://sa.investing.com/search/?q={s['symbol']})\n"
            message += "-------------------\n"

        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown', disable_web_page_preview=True)
        print(f"تم إرسال {len(signals)} تنبيه جديد إلى التلجرام.")
    else:
        print("لا توجد تحولات صعودية جديدة في هذا الفحص.")

    save_cache(cache)


if __name__ == '__main__':
    main()
