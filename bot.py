import yfinance as yf
import pandas as pd

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# =========================
# API
# =========================
API_KEY = "YOUR_API_KEY"
SECRET_KEY = "YOUR_SECRET_KEY"

client = TradingClient(API_KEY, SECRET_KEY, paper=True)

# =========================
# SETTINGS
# =========================
SYMBOL = "AAPL"
QTY = 1

# =========================
# GET DATA
# =========================
df = yf.download(
    SYMBOL,
    period="5d",
    interval="15m"
)

# =========================
# EMA
# =========================
df["EMA9"] = df["Close"].ewm(span=9).mean()
df["EMA21"] = df["Close"].ewm(span=21).mean()

last_ema9 = df["EMA9"].iloc[-1]
last_ema21 = df["EMA21"].iloc[-1]

current_price = float(df["Close"].iloc[-1])

print("EMA9:", last_ema9)
print("EMA21:", last_ema21)
print("Current Price:", current_price)

# =========================
# CHECK POSITION
# =========================
positions = client.get_all_positions()

holding = False
position = None

for p in positions:
    if p.symbol == SYMBOL:
        holding = True
        position = p

if holding:

    entry_price = float(position.avg_entry_price)

    stop_price = entry_price * 0.97

    print("Entry:", entry_price)
    print("Stop:", stop_price)
    print("Current:", current_price)
    if current_price < stop_price:
        print("STOP LOSS TRIGGERED")

        order = MarketOrderRequest(
            symbol=SYMBOL,
            qty=QTY,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )

        client.submit_order(order)

        print("SELL ORDER SENT")
# =========================
# BUY
# =========================
if last_ema9 > last_ema21 and not holding:

    print("BUY SIGNAL")

    order = MarketOrderRequest(
        symbol=SYMBOL,
        qty=QTY,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY
    )

    client.submit_order(order)

    print("BUY ORDER SENT")

if holding and current_price < stop_price:

    print("STOP LOSS HIT")

    order = MarketOrderRequest(
        symbol=SYMBOL,
        qty=QTY,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY
    )

    client.submit_order(order)

    print("STOP LOSS SELL SENT")
    
# =========================
# SELL
# =========================
elif last_ema9 < last_ema21 and holding:

    print("SELL SIGNAL")

    order = MarketOrderRequest(
        symbol=SYMBOL,
        qty=QTY,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY
    )

    client.submit_order(order)

    print("SELL ORDER SENT")

else:
    print("NO SIGNAL")