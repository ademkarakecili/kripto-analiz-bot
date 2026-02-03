import os
import asyncio
import requests
import pandas as pd
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import threading

# Ayarlar
TOKEN = "8387569713:AAF02_URGPDalPW7KWZVhT0EVqFXArs95-A"

# ===================== BINANCE VERI CEKME =====================
def get_24h(symbol):
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        r = requests.get(url, params={"symbol": symbol}, timeout=10)
        if r.status_code != 200: return None
        data = r.json()
        return {
            "price": float(data["lastPrice"]),
            "change": float(data["priceChangePercent"]),
            "volume": float(data["quoteVolume"])
        }
    except: return None

def get_klines(symbol):
    try:
        url = "https://api.binance.com/api/v3/klines"
        r = requests.get(url, params={"symbol": symbol, "interval": "15m", "limit": 100}, timeout=10)
        if r.status_code != 200: return None
        df = pd.DataFrame(r.json(), columns=["ot","open","high","low","close","vol","ct","qav","tr","tb","tq","ig"])
        df["close"] = df["close"].astype(float)
        return df
    except: return None

# ===================== ANALIZ MOTORU =====================
def build_analysis(symbol):
    p24 = get_24h(symbol)
    df = get_klines(symbol)
    
    if p24 is None or df is None:
        return f"❌ {symbol} için Binance verisi alınamadı. (Sembolü doğru girdiğinizden emin olun: BTC, ETH vb.)"

    # Basit Göstergeler
    current_price = p24['price']
    ema50 = df["close"].ewm(span=50).mean().iloc[-1]
    trend = "YÜKSELİŞ 📈" if current_price > ema50 else "DÜŞÜŞ 📉"

    return f"""
📊 {symbol} ANALİZ RAPORU
════════════════════
💰 Fiyat: ${current_price:,.2f}
📈 24s Değişim: %{p24['change']:.2f}
📉 Trend (EMA50): {trend}
📦 Hacim: ${p24['volume']/1e6:.2f}M
════════════════════
⚠️ Yatırım tavsiyesi değildir.
"""

# ===================== TELEGRAM HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot aktif! Analiz için bir coin yazın (Örn: BTC)")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    symbol = text + "USDT"
    await update.message.reply_text(f"🔍 {symbol} inceleniyor...")
    
    result = build_analysis(symbol)
    await update.message.reply_text(result)

# ===================== WEB SERVER (KEEP ALIVE) =====================
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# ===================== ANA CALISTIRICI =====================
if __name__ == '__main__':
    # Flask'ı ayrı bir thread'de başlatıyoruz (Botu etkilemez)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Telegram botu ana thread'de başlatıyoruz (Hata almamak için)
    print("🚀 Bot başlatılıyor...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()

