import yfinance as yf
import pandas as pd
import requests

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# =========================
# API KEYS
# =========================
ALPACA_API_KEY    = "PKEA24CVWXPWTQKYZJWQO7TY7N"
ALPACA_SECRET_KEY = "5sb6HPNAbxyNQZESDckfs56ByW7fUXp3fAorga8jiRaL"

LINE_CHANNEL_TOKEN = "FXjn2paEtU7hCyOAqeZEM/xImy8DZyADUfxiBNN0Gin+AtzmitBbXCq15ebhw2sY55SeId4TYEir6dSSolFGEpLFenklgDQbFvHZZaiP7CNayZaIOLmz8CJzWXw5tVTOZOBg2XjYHeQ8I1X0kWnJwAdB04t89/1O/w1cDnyilFU="
LINE_USER_ID       = "U055a806a92f65f59a244daec80c171c6"

client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

# =========================
# SETTINGS
# =========================
SYMBOLS = ["AAPL", "NVDA", "AMD", "TSLA", "PLTR"]
QTY = 1

# =========================
# LINE MESSAGING API
# =========================
def send_line(message: str):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"LINE Error: {resp.status_code} — {resp.text}")

# =========================
# MAIN BOT
# =========================
for SYMBOL in SYMBOLS:
    try:
        # GET DATA
        df = yf.download(SYMBOL, period="5d", interval="15m", progress=False)

        if df.empty:
            print(f"[{SYMBOL}] No data, skipping")
            continue

        # Flatten MultiIndex columns (yfinance >= 0.2)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # EMA
        df["EMA9"]  = df["Close"].ewm(span=9).mean()
        df["EMA21"] = df["Close"].ewm(span=21).mean()

        last_ema9    = float(df["EMA9"].iloc[-1])
        last_ema21   = float(df["EMA21"].iloc[-1])
        current_price = float(df["Close"].iloc[-1])

        print(f"[{SYMBOL}] EMA9: {last_ema9:.2f} | EMA21: {last_ema21:.2f} | Price: {current_price:.2f}")

        # CHECK POSITION
        positions = client.get_all_positions()
        holding  = False
        position = None

        for p in positions:
            if p.symbol == SYMBOL:
                holding  = True
                position = p
                break

        # STOP LOSS CHECK
        if holding:
            entry_price = float(position.avg_entry_price)
            stop_price  = entry_price * 0.97

            if current_price < stop_price:
                order = MarketOrderRequest(
                    symbol=SYMBOL,
                    qty=QTY,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
                client.submit_order(order)

                msg = (
                    f"[{SYMBOL}] STOP LOSS TRIGGERED\n"
                    f"Entry : {entry_price:.2f}\n"
                    f"Stop  : {stop_price:.2f}\n"
                    f"Price : {current_price:.2f}"
                )
                print(msg)
                send_line(msg)
                continue  # ข้าม BUY/SELL signal ของ symbol นี้

        # BUY / SELL SIGNAL
        if last_ema9 > last_ema21 and not holding:
            order = MarketOrderRequest(
                symbol=SYMBOL,
                qty=QTY,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            client.submit_order(order)

            msg = (
                f"[{SYMBOL}] BUY SIGNAL\n"
                f"EMA9  : {last_ema9:.2f} > EMA21: {last_ema21:.2f}\n"
                f"Price : {current_price:.2f}"
            )
            print(msg)
            send_line(msg)

        elif last_ema9 < last_ema21 and holding:
            order = MarketOrderRequest(
                symbol=SYMBOL,
                qty=QTY,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            client.submit_order(order)

            msg = (
                f"[{SYMBOL}] SELL SIGNAL\n"
                f"EMA9  : {last_ema9:.2f} < EMA21: {last_ema21:.2f}\n"
                f"Price : {current_price:.2f}"
            )
            print(msg)
            send_line(msg)

        else:
            print(f"[{SYMBOL}] NO SIGNAL")

    except Exception as e:
        error_msg = f"[{SYMBOL}] ERROR: {e}"
        print(error_msg)
        send_line(error_msg)
