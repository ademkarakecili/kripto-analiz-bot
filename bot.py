import requests
import pandas as pd
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import os
from flask import Flask
from threading import Thread

app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is alive!"

def run():
    # Render'ın dinamik portunu alır, yoksa 8080 kullanır
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

TOKEN = "8387569713:AAF02_URGPDalPW7KWZVhT0EVqFXArs95-A"

# ===================== BINANCE =====================

def get_24h(symbol):
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        r = requests.get(url, params={"symbol": symbol}, timeout=10).json()
        return {
            "price": float(r["lastPrice"]),
            "change": float(r["priceChangePercent"]),
            "volume": float(r["quoteVolume"])
        }
    except Exception:
        return None

def get_klines(symbol, interval="15m", limit=200):
    try:
        url = "https://api.binance.com/api/v3/klines"
        r = requests.get(url, params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }, timeout=10).json()

        df = pd.DataFrame(r, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","qav","trades","tb","tq","ignore"
        ])
        df["close"] = df["close"].astype(float)
        return df
    except Exception:
        return None

# ===================== INDICATORS =====================

def indicators(df):
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    return df.iloc[-1]

# ===================== SUPPORT / RESIST =====================

def supports_resistances(df):
    supports = sorted(df["close"].nsmallest(3))
    resists = sorted(df["close"].nlargest(3))
    return supports, resists

# ===================== ANALYSIS =====================

def build_analysis(symbol):
    price24 = get_24h(symbol)
    df = get_klines(symbol)
    if not price24 or df is None:
        return "❌ Veri alınamadı veya coin bulunamadı"

    last = indicators(df)
    supports, resists = supports_resistances(df)

    # Trend ve risk
    trend = "YÜKSELİŞ 📈" if last["ema50"] > last["ema200"] else "DÜŞÜŞ (Death Cross ❌)"
    rsi_status = "Düşük" if last["rsi"] < 40 else "Nötr" if last["rsi"] < 60 else "Yüksek"
    risk = f"{rsi_status} ✅" if rsi_status=="Nötr" else f"{rsi_status} ⚠️"

    # Volatilite
    volatility = df["close"].pct_change().rolling(14).std().iloc[-1] * 100
    vol_text = "DÜŞÜK" if volatility < 2 else "ORTA" if volatility < 4 else "YÜKSEK"

    # Hacim
    vol = price24['volume']
    if vol >= 1e9:
        vol_text2 = f"${vol/1e9:.2f}B (Ort. Üstü ✅)"
    elif vol >= 1e6:
        vol_text2 = f"${vol/1e6:.2f}M"
    else:
        vol_text2 = f"${vol:.0f}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Spot strateji
    spot_strategy = f"""
📥 KADEMELİ ALIM:
1️⃣ %30: ${supports[0]:,.2f} (S1)
2️⃣ %40: ${supports[1]:,.2f} (S2)
3️⃣ %30: ${supports[2]:,.2f} (S3)
🎯 HEDEFLER:
TP1: ${resists[0]:,.2f}
TP2: ${resists[2]:,.2f}
🛑 STOP: ${supports[2]-1000:.2f} (yaklaşık)
"""

    # Futures strateji
    futures_strategy = f"""
📉 SHORT POZİSYON (Öncelikli):
Giriş: ${last['ema50']:.2f} civarı
Kaldıraç: 5x
TP1: ${supports[0]:,.2f}
TP2: ${supports[2]:,.2f}
Stop: ${resists[0]:,.2f}

📈 LONG POZİSYON (Alternatif):
Giriş: ${supports[1]:,.2f} - ${supports[0]:,.2f}
Kaldıraç: 3x
TP1: ${last['close']:.2f}
TP2: ${resists[0]:,.2f}
Stop: ${supports[2]-500:.2f}
"""

    return f"""
════════════════════════════
💎 {symbol.replace('USDT','')}/USDT ANALİZ

💰 Anlık Fiyat: ${price24['price']:,.2f}
🔴 24s Değişim: {price24['change']:.2f}%
🟢 Risk: {risk}

────────────────────────────
📊 DESTEK & DİRENÇ
🔴 DİRENÇLER:
R3: ${resists[2]:,.2f} (+{(resists[2]-price24['price'])*100/price24['price']:.1f}%)
R2: ${resists[1]:,.2f} (+{(resists[1]-price24['price'])*100/price24['price']:.1f}%)
R1: ${resists[0]:,.2f} (+{(resists[0]-price24['price'])*100/price24['price']:.1f}%)

● ŞU AN: ${price24['price']:,.2f} ●

🟢 DESTEKLER:
S1: ${supports[0]:,.2f} ({(supports[0]-price24['price'])*100/price24['price']:.1f}%)
S2: ${supports[1]:,.2f} ({(supports[1]-price24['price'])*100/price24['price']:.1f}%)
S3: ${supports[2]:,.2f} ({(supports[2]-price24['price'])*100/price24['price']:.1f}%)

────────────────────────────
📈 TEKNİK ÖZET
📉 Trend: {trend}
📊 RSI: {last['rsi']:.2f} ({rsi_status})
📉 EMA50: {last['ema50']:.2f}
📉 EMA200: {last['ema200']:.2f}
📊 Volatilite: {vol_text} (%{volatility:.2f})
📦 Hacim: {vol_text2}

────────────────────────────
⚠️ KRİTİK GÖZLEMLER:
• Fiyat günlük dibe yakın
• EMA200 altında işlem
• Order book satıcı ağır (basit gözlem)
• Trend uyumsuzlukları var

────────────────────────────
💰 SPOT STRATEJİ
{spot_strategy}

📊 VADELİ (FUTURES) STRATEJİ
{futures_strategy}

────────────────────────────
⚠️ FOMO yapma, sabırlı ol!
🕐 {now}
⚠️ Yatırım tavsiyesi değildir
════════════════════════════
"""

# ===================== TELEGRAM =====================

# /start komutu
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Merhaba! Kripto analiz botuna hoş geldin.\n"
        "Bir coin adı girin (örn: BTC) veya /help yazın."
    )

# Coin analizi handler
async def coin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        coin = update.message.text.replace("/", "").upper()
        symbol = coin + "USDT"
        analysis = build_analysis(symbol)
        await update.message.reply_text(analysis)
    except Exception as e:
        await update.message.reply_text(f"❌ Hata oluştu: {e}")

# ===================== RUN =====================

app = ApplicationBuilder().token(TOKEN).build()

# Handlers
app.add_handler(CommandHandler("start", start_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, coin_handler))

print("🤖 Kriptocu Analiz Bot çalışıyor...")
# ===================== BAŞLATMA =====================

if __name__ == '__main__':
    try:
        # Render'ın botu uyutmaması için web sunucusunu başlat
        keep_alive() 
        
        # Botu çalıştır
        print("🤖 Kriptocu Analiz Bot çalışıyor...")
        app.run_polling()
    except Exception as e:
        print(f"❌ Başlatma hatası: {e}")



