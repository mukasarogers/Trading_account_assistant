import ccxt
import pandas as pd
import requests
import time
from datetime import datetime

# === Telegram Bot Credentials ===
BOT_TOKEN = '8037243338:AAG8W77_zU6hYRhy71biIDD-mIEEv3jeuTU'
CHAT_ID = '7456936221'
CHANNEL_ID = '-1002722618688'

def send_telegram(message):
    for chat_id in [CHAT_ID, CHANNEL_ID]:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
        try:
            requests.post(url, data=payload)
        except Exception as e:
            print(f"Telegram Error: {e}")

# === Technical Indicators ===
def EMA(series, period): return series.ewm(span=period, adjust=False).mean()

def RSI(series, period=14):
    delta = series.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def MACD(series):
    fast = EMA(series, 12)
    slow = EMA(series, 26)
    macd = fast - slow
    signal = EMA(macd, 9)
    return macd, signal

# === Exchange Setup ===
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# === Safe Futures Coins ===
SAFE_COINS = [
    'ETH/USDT', 'BNB/USDT', 'AVAX/USDT', 'LINK/USDT', 'XRP/USDT',
    'NEAR/USDT', 'UNI/USDT', 'AAVE/USDT', 'ADA/USDT', 'DOT/USDT',
    'TRX/USDT', 'SUI/USDT', 'FIL/USDT', 'INJ/USDT', 'OP/USDT', 'SOL/USDT'
]

def get_data(symbol, tf='15m', limit=100):
    try:
        data = exchange.fetch_ohlcv(symbol, tf, limit=limit)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except:
        return None

def is_stable(df, threshold=3.5):
    volatility = ((df['high'] - df['low']) / df['close']) * 100
    return volatility.rolling(5).mean().iloc[-1] < threshold

def detect_signal(df):
    df['ema20'] = EMA(df['close'], 20)
    df['ema50'] = EMA(df['close'], 50)
    df['rsi'] = RSI(df['close'])
    df['macd'], df['signal'] = MACD(df['close'])

    last = df.iloc[-1]
    if last['rsi'] > 55 and last['ema20'] > last['ema50'] and last['macd'] > last['signal']:
        return 'LONG'
    elif last['rsi'] < 45 and last['ema20'] < last['ema50'] and last['macd'] < last['signal']:
        return 'SHORT'
    return None

def format_message(symbol, signal, entry, tp):
    emoji = '🎯' if signal == 'LONG' else '🔻'
    return (
        f"{emoji} <b>{signal} SIGNAL - {symbol}</b>\n"
        f"💰 Entry Price: <b>{entry}</b>\n"
        f"🎯 Take Profit Target: <b>{tp} (2%)</b>\n"
        f"🛑 Stop Loss: <b>Use Margin Call or Manual Risk</b>\n"
        f"📊 Signal Strength: High with indicator alignment\n"
        f"📅 Time: <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
        f"#AISignalBot #SafeFutures"
    )

sent = {}
tracked_signals = []
daily_log = []

def main_loop():
    last_morning = None
    last_summary = None

    while True:
        now = datetime.now()

        # Good morning message
        if now.hour == 8 and (last_morning != now.date()):
            send_telegram("🌞 GOOD MORNING BOSS. TODAY IS ANOTHER NEW DAY TO MAKE MORE MONEY 🤑 💰. GOOD LUCK")
            last_morning = now.date()

        # Daily summary at midnight
        if now.hour == 0 and now.minute < 5 and (last_summary != now.date()):
            summary = "<b>📊 Daily Summary:</b>\n" + "\n".join(daily_log) if daily_log else "📊 No signals sent today."
            send_telegram(summary)
            daily_log.clear()
            last_summary = now.date()

        signals = 0
        for coin in SAFE_COINS:
            if signals >= 2:
                break

            df = get_data(coin)
            if df is None or len(df) < 50: continue
            if not is_stable(df): continue

            signal = detect_signal(df)
            if not signal: continue

            key = f"{coin}_{signal}"
            if key in sent and time.time() - sent[key] < 1800:
                continue

            price = exchange.fetch_ticker(coin)['last']
            tp = round(price * 1.02, 4) if signal == 'LONG' else round(price * 0.98, 4)

            msg = format_message(coin, signal, price, tp)
            send_telegram(msg)

            tracked_signals.append({'symbol': coin, 'side': signal, 'entry': price, 'tp': tp, 'hit': False})
            sent[key] = time.time()
            daily_log.append(f"{coin}: {signal} @ {price}")
            signals += 1

        # === Monitor Signals for TP hit ===
        for t in tracked_signals:
            if t['hit']: continue
            try:
                price = exchange.fetch_ticker(t['symbol'])['last']
                if (t['side'] == 'LONG' and price >= t['tp']) or (t['side'] == 'SHORT' and price <= t['tp']):
                    t['hit'] = True
                    send_telegram(f"[>>> {t['symbol']} HAS HIT ITS TARGET 2% with value : {price} <<<<] CONTINUE TRADING BOSS 🤝")
            except:
                continue

        time.sleep(600)  # Run every 10 minutes

# === Start Bot Message ===
send_telegram("✅ AI Signal Bot is ACTIVE with safe quick-profit strategy! Now tracking signals and TP hits 🚀")
main_loop()
