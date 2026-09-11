def is_recently_sent(symbol):
    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{UPSTASH_REDIS_REST_URL}/get/{symbol}"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            r = requests.get(url, headers=headers, timeout=10)
            print(f"🔎 GET {symbol} -> status={r.status_code} body={r.text}")
            res = r.json()
            if res.get("result") is not None:
                return True
        except Exception as e:
            print(f"⚠️ فشل GET من Redis لـ {symbol}: {e}")
            return True  # fail-safe: امنع الإرسال عند الشك بدل السماح به

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
            url = f"{UPSTASH_REDIS_REST_URL}/set/{symbol}/SENT/EX/86400"
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            r = requests.get(url, headers=headers, timeout=10)
            print(f"💾 SET {symbol} -> status={r.status_code} body={r.text}")
        except Exception as e:
            print(f"⚠️ فشل الحفظ في Redis لـ {symbol}: {e}")

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
    except Exception as e:
        print(f"⚠️ فشل كتابة الملف المحلي: {e}")
