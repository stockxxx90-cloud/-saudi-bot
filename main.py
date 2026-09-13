import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf

# جلب بيانات الاعتماد من GitHub Secrets
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# قائمة جميع أسهم وصناديق السوق السعودي مقسمة حسب القطاعات
RAW_STOCKS = [
    # قطاع الطاقة
    "2030", "2222", "2380", "2381", "2382", "4030",
    
    # قطاع المواد الأساسية
    "1201", "1202", "1210", "1211", "1301", "1304", "1320", "1321", "1322", "1323", "1324",
    "2001", "2010", "2020", "2060", "2090", "2150", "2170", "2180", "2200", "2210", "2220",
    "2223", "2240", "2250", "2290", "2300", "2310", "2330", "2350", "2360", "3002", "3003",
    "3004", "3005", "3007", "3008", "3010", "3020", "3030", "3040", "3050", "3060", "3080",
    "3090", "3091", "3092", "4143",
    
    # قطاع السلع الرأسمالية
    "1212", "1214", "1302", "1303", "2040", "2110", "2160", "2320", "2370", "4110", "4140",
    "4141", "4142", "4144", "4145", "4146", "4147", "4148",
    
    # قطاع الخدمات التجارية والمهنية
    "1831", "1832", "1833", "1834", "1835", "4270", "6004",
    
    # قطاع النقل
    "2190", "4031", "4040", "4260", "4261", "4262", "4263", "4264", "4265",
    
    # قطاع السلع طويلة الأجل
    "1213", "2130", "2340", "4011", "4012",
    
    # قطاع الخدمات الاستهلاكية
    "1810", "1820", "1830", "4090", "4170", "4250", "4290", "4291", "4292", "6002", "6012",
    "6013", "6014", "6015", "6016", "6017", "6018", "6019", "6022",
    
    # قطاع الإعلام والترفيه
    "4070", "4071", "4072", "4210",
    
    # قطاع تجزئة وتوزيع السلع الكمالية
    "4003", "4008", "4050", "4051", "4180", "4190", "4191", "4192", "4193", "4194", "4200", "4240",
    
    # قطاع تجزئة وتوزيع السلع الاستهلاكية
    "4001", "4006", "4061", "4160", "4161", "4162", "4163", "4164",
    
    # قطاع إنتاج الأغذية
    "2050", "2100", "2140", "2270", "2280", "2281", "2282", "2283", "2284", "2285", "2286",
    "2287", "2288", "4080", "6001", "6010", "6020", "6040", "6050", "6060", "6070", "6090",
    
    # قطاع المنتجات المنزلية والشخصية
    "4165",
    
    # قطاع الرعاية الصحية والأدوية
    "2230", "2070", "4002", "4004", "4005", "4007", "4009", "4013", "4014", "4015", "4016",
    "4017", "4018", "4019", "4021",
    
    # قطاع البنوك
    "1010", "1020", "1030", "1050", "1060", "1080", "1120", "1140", "1150", "1180",
    
    # قطاع الخدمات المالية
    "1111", "1182", "1183", "2120", "4081", "4082", "4083", "4084", "4130", "4280",
    
    # قطاع التأمين
    "8010", "8012", "8020", "8030", "8040", "8050", "8060", "8070", "8100", "8120", "8150",
    "8160", "8170", "8180", "8190", "8200", "8210", "8230", "8240", "8250", "8260", "8280",
    "8300", "8310", "8311", "8313",
    
    # قطاع التطبيقات وخدمات التقنية
    "7200", "7201", "7202", "7203", "7204", "7205", "7211",
    
    # قطاع الاتصالات
    "7010", "7020", "7030", "7040",
    
    # قطاع المرافق العامة
    "2080", "2081", "2082", "2083", "2084", "5110",
    
    # الصناديق العقارية المتداولة (REITs)
    "4330", "4331", "4332", "4333", "4334", "4335", "4336", "4337", "4338", "4339", "4340",
    "4342", "4344", "4345", "4346", "4347", "4348", "4349"
]

# إضافة امتداد السوق السعودي لتتعرف عليه مكتبة yfinance
SAUDI_STOCKS = [f"{code}.SR" for code in RAW_STOCKS]

def calculate_rsi(series, period=14):
    """حساب مؤشر القوة النسبية RSI"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Secrets غير معرفة!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": text, 
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"❌ خطأ في إرسال التليجرام: {e}")

def scan_saudi_market():
    print(f"🚀 بدء المسح المتقدم لـ {len(SAUDI_STOCKS)} سهم/صندوق في السوق السعودي...")

    found_opportunities = 0

    for ticker in SAUDI_STOCKS:
        try:
            stock = yf.Ticker(ticker)
            symbol_clean = ticker.replace(".SR", "")
            
            # 1. جلب بيانات فريم 4 ساعات لشرط RSI
            df_4h = stock.history(period="1mo", interval="1h")
            if df_4h.empty or len(df_4h) < 20:
                continue
            
            # إعادة تجميع البيانات إلى فريم 4 ساعات
            df_4h_resampled = df_4h.resample('4h').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

            df_4h_resampled['RSI'] = calculate_rsi(df_4h_resampled['Close'], period=14)
            
            if df_4h_resampled['RSI'].empty:
                continue
                
            rsi_4h = round(df_4h_resampled['RSI'].iloc[-1], 2)

            # شرط RSI 4H > 54
            if pd.isna(rsi_4h) or rsi_4h <= 54:
                continue

            # 2. جلب بيانات فريم 15 دقيقة للتنفيذ والـ FVG
            df_15m = stock.history(period="5d", interval="15m")
            if df_15m.empty or len(df_15m) < 5:
                continue

            latest_price = round(df_15m['Close'].iloc[-1], 2)
            prev_high = df_15m['High'].iloc[-3]
            current_low = df_15m['Low'].iloc[-1]
            
            # شرط FVG
            has_fvg = current_low >= (prev_high * 0.997)

            # حساب CVD
            vol_delta = np.where(df_15m['Close'] >= df_15m['Open'], df_15m['Volume'], -df_15m['Volume'])
            cvd_val = vol_delta.cumsum()[-1]
            cvd_status = "نعم (CVD > 0)" if cvd_val > 0 else "لا (CVD < 0)"

            if has_fvg:
                found_opportunities += 1
                stop_loss = round(df_15m['Low'].iloc[-5:].min(), 2)
                target1 = round(latest_price * 1.02, 2)
                target_max = round(latest_price * 1.05, 2)
                
                # رابط التداول على TradingView للسوق السعودي
                tv_url = f"https://www.tradingview.com/chart/?symbol=TADAWUL:{symbol_clean}"
                
                msg = f"""
⚡ **تنبيه سكنر السوق السعودي [L3-MBO + 4H RSI Filter]**

📌 **رمز السهم:** `{symbol_clean}`
📈 **رابط الشارت:** [فتح الشارت على TradingView]({tv_url})
💵 **السعر الحالي:** `{latest_price}` ر.س

📊 **مصفوفة المؤشرات والسلوك:**
• FVG / CHOCH: `إشارة تجميع / FVG نشط`
• مؤشر RSI (فاصل 4 ساعات): `{rsi_4h}` 🟢 *(تجاوز 54)*
• خط CVD فوق الصفر: `{cvd_status}`

🎯 **الأهداف المتوقعة:**
• هدف أول: `{target1}` ر.س
• 🟢 قد يصل إلى: `{target_max}` ر.س

⛔ **وقف الخسارة:**
• وقف خسارة أولي: `{stop_loss}` ر.س
"""
                send_telegram(msg)
                print(f"✅ تم إرسال تنبيه للسهم {symbol_clean} (RSI 4H: {rsi_4h})")
        except Exception as e:
            print(f"❌ خطأ في فحص {ticker}: {e}")

    if found_opportunities == 0:
        print("ℹ️ لا توجد أسهم تطابق شرط RSI 4H > 54 مع FVG حالياً في السوق السعودي.")

if __name__ == "__main__":
    scan_saudi_market()
