import os
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime

import requests
import yfinance as yf
import pandas as pd
import telebot

# ====================== الإعدادات ======================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

CACHE_FILE = 'sent_signals.json'
NEWS_MAX_AGE_HOURS = 48

# القائمة الشاملة لأسهم السوق الرئيسي
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

# خريطة اختيارية لأسماء الشركات (تحسّن دقة الأخبار)
SYMBOL_NAMES = {
    '2222': 'أرامكو السعودية',
    '1120': 'مصرف الراجحي',
    '2350': 'كيان السعودية',
    '7010': 'إس تي سي',
    # أضف المزيد حسب الحاجة
}

# ====================== الكاش ======================
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                migrated = {}
                for sym, val in data.items():
                    if isinstance(val, dict):
                        migrated[sym] = val
                    else:
                        migrated[sym] = {
                            "was_bullish": True,
                            "last_alert_price": None,
                            "last_news_id": None
                        }
                if "_global_news" not in migrated:
                    migrated["_global_news"] = []
                return migrated
        except Exception:
            return {"_global_news": []}
    return {"_global_news": []}


def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")


# ====================== جلب الأخبار (أرقام + تداول فقط) ======================
def get_latest_news(symbol_code: str):
    """
    يجلب أحدث خبر من مصادر موثوقة فقط (أرقام + تداول).
    بدون أي استعلام عام.
    """
    company_name = SYMBOL_NAMES.get(symbol_code, "")
    
    queries = []
    if company_name:
        queries.append(f'site:argaam.com ("{company_name}" OR {symbol_code}) when:3d')
        queries.append(f'site:saudiexchange.sa ("{company_name}" OR {symbol_code}) when:7d')
    else:
        queries.append(f'site:argaam.com {symbol_code} when:3d')
        queries.append(f'site:saudiexchange.sa {symbol_code} when:7d')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    for query in queries:
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ar&gl=SA&ceid=SA:ar"
            resp = requests.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.findall('.//item')[:5]:
                title = (item.findtext('title') or "").strip()
                link = (item.findtext('link') or "").strip()
                pub_date_str = item.findtext('pubDate')
                source = (item.findtext('source') or "").lower()

                if not title or not link:
                    continue

                # فلترة العمر
                if pub_date_str:
                    try:
                        pub_ts = parsedate_to_datetime(pub_date_str).timestamp()
                        if (time.time() - pub_ts) > NEWS_MAX_AGE_HOURS * 3600:
                            continue
                    except Exception:
                        pass

                # فلترة الصلة
                is_relevant = (
                    symbol_code in title or
                    (company_name and company_name in title)
                )

                is_preferred = any(s in source or s in title.lower() 
                                   for s in ["ارقام", "argaam", "تداول", "saudiexchange"])

                if is_relevant or is_preferred:
                    return {
                        'id': link,
                        'title': title,
                        'link': link,
                        'source': source
                    }

        except Exception as e:
            print(f"News query error ({symbol_code}): {e}")
            continue

    return None


# ====================== تحليل السهم ======================
def safe_float(val):
    if isinstance(val, pd.Series):
        return float(val.iloc[0])
    return float(val)


def analyze_stock(ticker: str):
    try:
        symbol_code = ticker.replace('.SR', '')

        df = yf.download(
            ticker,
            period='120d',
            interval='1d',
            progress=False,
            auto_adjust=True,
            threads=False
        )

        if df.empty or len(df) < 50:
            return None

        # معالجة MultiIndex إن وجدت
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df['Volume'].iloc[-1] == 0 or pd.isna(df['Close'].iloc[-1]):
            return None

        # EMA
        df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()

        # RSI
        delta = df['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))

        df['Vol_SMA'] = df['Volume'].rolling(20).mean()

        last = df.iloc[-1]

        rsi = safe_float(last['RSI'])
        ema9 = safe_float(last['EMA_9'])
        ema21 = safe_float(last['EMA_21'])
        vol = safe_float(last['Volume'])
        vol_sma = safe_float(last['Vol_SMA'])
        close = safe_float(last['Close'])

        if pd.isna(rsi) or pd.isna(vol_sma):
            return None

        # شروط الدخول (كما هي)
        is_bullish = (ema9 > ema21) and (rsi > 55.0) and (vol > vol_sma)

        return {
            'symbol': symbol_code,
            'ticker': ticker,
            'is_bullish': is_bullish,
            'price': round(close, 2),
            'rsi': round(rsi, 1),
            'ema9': round(ema9, 2),
            'ema21': round(ema21, 2),
        }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None


# ====================== البرنامج الرئيسي ======================
def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] بدء فحص أسهم السوق الرئيسي...")
    cache = load_cache()
    signals = []
    global_news = cache.get("_global_news", [])

    for i, symbol in enumerate(SYMBOLS):
        result = analyze_stock(symbol)
        if result is None:
            continue

        symbol_code = result['symbol']
        prev = cache.get(symbol_code, {
            "was_bullish": False,
            "last_alert_price": None,
            "last_news_id": None
        })

        # اكتشاف التحول الجديد فقط
        fresh_crossover = result['is_bullish'] and not prev.get('was_bullish', False)

        # تحديث الحالة دائمًا
        cache[symbol_code] = {
            "was_bullish": result['is_bullish'],
            "last_alert_price": result['price'] if fresh_crossover else prev.get('last_alert_price'),
            "last_news_id": prev.get('last_news_id'),
        }

        if not fresh_crossover:
            continue

        # جلب خبر جديد
        news = get_latest_news(symbol_code)
        
        if news and news['id'] not in global_news and news['id'] != prev.get('last_news_id'):
            cache[symbol_code]['last_news_id'] = news['id']
            global_news.append(news['id'])
            result['news'] = news
        else:
            result['news'] = None

        signals.append(result)

        # تأخير بسيط كل 15 سهم
        if (i + 1) % 15 == 0:
            time.sleep(1.2)

    # حفظ قائمة الأخبار العالمية (آخر 80 خبر)
    cache["_global_news"] = global_news[-80:]

    if signals:
        message = "🚀 *تنبيه فرصة جديدة - السوق السعودي* 🚀\n\n"
        for s in signals:
            message += (
                f"🔹 *السهم:* `{s['symbol']}`\n"
                f"📊 *السعر الحالي:* {s['price']} ريال\n"
                f"📈 *RSI:* {s['rsi']}\n"
                f"☁️ *EMA 9 / 21:* {s['ema9']} / {s['ema21']}\n"
                f"📈 [الشارت المباشر](https://ar.tradingview.com/chart/?symbol=TADAWUL%3A{s['symbol']})\n"
            )
            if s.get('news'):
                safe_title = s['news']['title'].replace('*', '').replace('_', '').replace('[', '').replace(']', '')
                message += f"📰 [{safe_title}]({s['news']['link']})\n"
            else:
                message += f"📰 [بحث عن أخبار السهم](https://sa.investing.com/search/?q={s['symbol']})\n"
            message += "-------------------\n"

        try:
            bot.send_message(
                TELEGRAM_CHAT_ID,
                message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            print(f"تم إرسال {len(signals)} تنبيه جديد.")
        except Exception as e:
            print(f"خطأ في إرسال التلجرام: {e}")
    else:
        print("لا توجد تحولات صعودية جديدة في هذا الفحص.")

    save_cache(cache)


if __name__ == '__main__':
    main()
