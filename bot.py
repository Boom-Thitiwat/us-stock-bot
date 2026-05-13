import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import pytz

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
SYMBOLS        = ["AAPL", "NVDA", "AMD", "TSLA", "PLTR"]
RISK_PER_TRADE = 0.01   # เสี่ยง 1% ของ portfolio ต่อ 1 trade
ATR_STOP_MULT  = 1.5    # Stop Loss = 1.5x ATR จาก entry
TAKE_PROFIT_RR = 2.0    # Take Profit = 2x risk (R:R = 1:2)

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
# INDICATORS
# =========================
def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl  = df["High"] - df["Low"]
    hc  = (df["High"] - df["Close"].shift()).abs()
    lc  = (df["Low"]  - df["Close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# =========================
# MARKET HOURS CHECK
# =========================
def is_market_open() -> bool:
    now = datetime.now(pytz.timezone("America/New_York"))
    if now.weekday() >= 5:
        return False
    # หลีกเลี่ยง 30 นาทีแรกและ 30 นาทีสุดท้ายของตลาด (volatile/spread กว้าง)
    trade_start = now.replace(hour=10, minute=0,  second=0, microsecond=0)
    trade_end   = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return trade_start <= now <= trade_end

# =========================
# POSITION SIZING
# Risk-based: คำนวณ qty จาก % equity ที่ยอมเสีย
# =========================
def calc_qty(equity: float, entry: float, stop: float) -> int:
    risk_amount    = equity * RISK_PER_TRADE
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return 1
    return max(int(risk_amount / risk_per_share), 1)

# =========================
# MAIN BOT
# =========================
if not is_market_open():
    msg = "Market closed or outside trading window (10:00–15:30 ET)"
    print(msg)
    send_line(msg)
    exit()

account = client.get_account()
equity  = float(account.equity)
print(f"Account Equity: ${equity:,.2f}")

for SYMBOL in SYMBOLS:
    try:
        # ---- GET DATA ----
        # 15m: signal timeframe | 1h: trend filter timeframe
        df15 = flatten(yf.download(SYMBOL, period="5d",  interval="15m", progress=False))
        df1h = flatten(yf.download(SYMBOL, period="30d", interval="1h",  progress=False))

        if df15.empty or df1h.empty:
            print(f"[{SYMBOL}] No data, skipping")
            continue

        # ---- INDICATORS (15m) ----
        df15["EMA9"]   = df15["Close"].ewm(span=9).mean()
        df15["EMA21"]  = df15["Close"].ewm(span=21).mean()
        df15["RSI"]    = calc_rsi(df15["Close"])
        df15["ATR"]    = calc_atr(df15)
        df15["VolAvg"] = df15["Volume"].rolling(20).mean()

        # ---- TREND FILTER (1h) ----
        # ซื้อเฉพาะตอน uptrend: ราคา > EMA50 บน 1h
        df1h["EMA50"] = df1h["Close"].ewm(span=50).mean()

        last = df15.iloc[-1]
        prev = df15.iloc[-2]

        current_price  = float(last["Close"])
        last_ema9      = float(last["EMA9"])
        last_ema21     = float(last["EMA21"])
        prev_ema9      = float(prev["EMA9"])
        prev_ema21     = float(prev["EMA21"])
        last_rsi       = float(last["RSI"])
        last_atr       = float(last["ATR"])
        last_vol       = float(last["Volume"])
        avg_vol        = float(last["VolAvg"])
        trend_close    = float(df1h["Close"].iloc[-1])
        trend_ema50    = float(df1h["EMA50"].iloc[-1])

        # ---- SIGNAL: ต้องเป็น crossover จริง ไม่ใช่แค่ EMA9 > EMA21 ----
        cross_up   = (prev_ema9 <= prev_ema21) and (last_ema9 > last_ema21)
        cross_down = (prev_ema9 >= prev_ema21) and (last_ema9 < last_ema21)

        # ---- FILTERS ----
        uptrend     = trend_close > trend_ema50          # 1h trend เป็น up
        vol_confirm = last_vol > (avg_vol * 1.2)         # volume สูงกว่าเฉลี่ย 20%
        rsi_ok_buy  = 45 < last_rsi < 70                 # ไม่ overbought
        rsi_ok_sell = last_rsi > 50

        print(
            f"[{SYMBOL}] Price:{current_price:.2f} | EMA9:{last_ema9:.2f} | EMA21:{last_ema21:.2f} | "
            f"RSI:{last_rsi:.1f} | ATR:{last_atr:.2f} | Uptrend:{uptrend} | VolOK:{vol_confirm}"
        )

        # ---- CHECK OPEN POSITION ----
        positions = client.get_all_positions()
        holding   = False
        position  = None
        for p in positions:
            if p.symbol == SYMBOL:
                holding  = True
                position = p
                break

        # ---- STOP LOSS & TAKE PROFIT ----
        if holding:
            entry_price = float(position.avg_entry_price)
            stop_price  = entry_price - (last_atr * ATR_STOP_MULT)
            tp_price    = entry_price + (entry_price - stop_price) * TAKE_PROFIT_RR
            qty_held    = int(float(position.qty))

            if current_price <= stop_price:
                client.submit_order(MarketOrderRequest(
                    symbol=SYMBOL, qty=qty_held,
                    side=OrderSide.SELL, time_in_force=TimeInForce.DAY
                ))
                pnl = ((current_price / entry_price) - 1) * 100
                msg = (
                    f"🔴 [{SYMBOL}] STOP LOSS\n"
                    f"Entry : {entry_price:.2f}\n"
                    f"Stop  : {stop_price:.2f}\n"
                    f"Price : {current_price:.2f}\n"
                    f"P&L   : {pnl:.2f}%"
                )
                print(msg); send_line(msg)
                continue

            if current_price >= tp_price:
                client.submit_order(MarketOrderRequest(
                    symbol=SYMBOL, qty=qty_held,
                    side=OrderSide.SELL, time_in_force=TimeInForce.DAY
                ))
                pnl = ((current_price / entry_price) - 1) * 100
                msg = (
                    f"✅ [{SYMBOL}] TAKE PROFIT\n"
                    f"Entry : {entry_price:.2f}\n"
                    f"TP    : {tp_price:.2f}\n"
                    f"Price : {current_price:.2f}\n"
                    f"P&L   : +{pnl:.2f}%"
                )
                print(msg); send_line(msg)
                continue

        # ---- BUY SIGNAL ----
        # เงื่อนไข: EMA crossover ขึ้น + uptrend (1h) + volume พุ่ง + RSI ไม่ overbought
        if cross_up and uptrend and vol_confirm and rsi_ok_buy and not holding:
            stop_price = current_price - (last_atr * ATR_STOP_MULT)
            tp_price   = current_price + (current_price - stop_price) * TAKE_PROFIT_RR
            qty        = calc_qty(equity, current_price, stop_price)

            client.submit_order(MarketOrderRequest(
                symbol=SYMBOL, qty=qty,
                side=OrderSide.BUY, time_in_force=TimeInForce.DAY
            ))
            msg = (
                f"🟢 [{SYMBOL}] BUY\n"
                f"Price : {current_price:.2f} | Qty: {qty}\n"
                f"Stop  : {stop_price:.2f} ({ATR_STOP_MULT}x ATR)\n"
                f"TP    : {tp_price:.2f} (R:R 1:{TAKE_PROFIT_RR})\n"
                f"RSI   : {last_rsi:.1f} | Uptrend: {uptrend}"
            )
            print(msg); send_line(msg)

        # ---- SELL SIGNAL ----
        # EMA crossover ลง หรือ trend เปลี่ยนเป็น downtrend
        elif (cross_down or not uptrend) and holding:
            client.submit_order(MarketOrderRequest(
                symbol=SYMBOL, qty=int(float(position.qty)),
                side=OrderSide.SELL, time_in_force=TimeInForce.DAY
            ))
            reason = "EMA Cross Down" if cross_down else "Trend Break (price < EMA50)"
            msg = (
                f"🟡 [{SYMBOL}] SELL SIGNAL\n"
                f"Price  : {current_price:.2f}\n"
                f"Reason : {reason}"
            )
            print(msg); send_line(msg)

        else:
            print(f"[{SYMBOL}] NO SIGNAL")

    except Exception as e:
        error_msg = f"[{SYMBOL}] ERROR: {e}"
        print(error_msg)
        send_line(error_msg)
