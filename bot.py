import yfinance as yf
import pandas as pd
import requests
import time
import os
from datetime import datetime
import pytz

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

load_dotenv()

# =========================
# API KEYS
# =========================
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN", "")
LINE_USER_ID       = os.getenv("LINE_USER_ID", "")

def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

ALPACA_PAPER_TRADING = env_bool("ALPACA_PAPER_TRADING", True)
client: TradingClient | None = None

def get_trading_client() -> TradingClient:
    global client
    if client is None:
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set when ENABLE_ORDER_EXECUTION is true")
        client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER_TRADING)
    return client

# =========================
# SETTINGS
# =========================
ENABLE_ORDER_EXECUTION = env_bool("ENABLE_ORDER_EXECUTION", False)
RUN_CONTINUOUSLY = env_bool("RUN_CONTINUOUSLY", True)
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "900"))
MAX_TEST_ORDER_NOTIONAL = float(os.getenv("MAX_TEST_ORDER_NOTIONAL", "100.0"))

def us_stock(symbol: str, theme: str) -> dict:
    return {
        "symbol": symbol,
        "market": "US",
        "broker_symbol": symbol,
        "theme": theme,
    }

WATCHLIST = [
    # AI mega-cap platforms
    us_stock("NVDA", "AI chips/platform"),
    us_stock("MSFT", "AI cloud/software"),
    us_stock("GOOGL", "AI cloud/search"),
    us_stock("GOOG", "AI cloud/search"),
    us_stock("AMZN", "AI cloud/ecommerce"),
    us_stock("META", "AI apps/infrastructure"),
    us_stock("AAPL", "AI devices"),
    us_stock("AVGO", "AI networking/custom chips"),
    us_stock("ORCL", "AI cloud/database"),
    us_stock("TSLA", "AI autonomy/robotics"),

    # Semiconductors, memory, and chip infrastructure
    us_stock("AMD", "AI accelerators"),
    us_stock("INTC", "AI chips/foundry"),
    us_stock("QCOM", "edge AI chips"),
    us_stock("MRVL", "AI networking chips"),
    us_stock("MU", "AI memory"),
    us_stock("ARM", "chip IP"),
    us_stock("TXN", "embedded AI hardware"),
    us_stock("ADI", "edge/industrial AI chips"),
    us_stock("ON", "sensors/auto AI chips"),
    us_stock("MCHP", "embedded AI chips"),
    us_stock("MPWR", "AI power chips"),
    us_stock("LSCC", "FPGA/edge AI"),
    us_stock("ALAB", "AI data-center connectivity"),
    us_stock("COHR", "AI data-center optics"),
    us_stock("LITE", "AI data-center optics"),
    us_stock("AEHR", "chip testing"),
    us_stock("AMBA", "edge AI vision chips"),

    # AI servers, data centers, networking, and power
    us_stock("SMCI", "AI servers"),
    us_stock("DELL", "AI servers"),
    us_stock("HPE", "AI servers/networking"),
    us_stock("ANET", "AI data-center networking"),
    us_stock("CSCO", "AI networking"),
    us_stock("VRT", "AI data-center power/cooling"),
    us_stock("ETN", "AI data-center power"),
    us_stock("PWR", "AI data-center infrastructure"),
    us_stock("FIX", "AI data-center services"),
    us_stock("EQIX", "AI data centers"),
    us_stock("DLR", "AI data centers"),

    # Enterprise AI software and data platforms
    us_stock("PLTR", "enterprise AI"),
    us_stock("CRM", "enterprise AI software"),
    us_stock("NOW", "workflow AI"),
    us_stock("ADBE", "creative AI"),
    us_stock("SNOW", "AI data cloud"),
    us_stock("MDB", "AI database"),
    us_stock("DDOG", "AI observability"),
    us_stock("NET", "AI edge/cloud"),
    us_stock("APP", "AI advertising"),
    us_stock("TEAM", "collaboration AI"),
    us_stock("WDAY", "enterprise AI"),
    us_stock("INTU", "finance AI"),
    us_stock("SHOP", "commerce AI"),
    us_stock("UBER", "AI marketplace/autonomy"),
    us_stock("RBLX", "AI content/platform"),
    us_stock("DUOL", "education AI"),

    # Cybersecurity AI
    us_stock("CRWD", "AI cybersecurity"),
    us_stock("PANW", "AI cybersecurity"),
    us_stock("ZS", "AI cybersecurity"),
    us_stock("S", "AI cybersecurity"),
    us_stock("OKTA", "identity AI"),
    us_stock("TENB", "AI cybersecurity"),

    # Automation, robotics, autonomy, and sensing
    us_stock("ISRG", "robotics"),
    us_stock("TER", "robotics/testing"),
    us_stock("ROK", "industrial AI"),
    us_stock("SYM", "warehouse robotics"),
    us_stock("MBLY", "autonomous driving"),
    us_stock("OUST", "lidar/autonomy"),
    us_stock("LAZR", "lidar/autonomy"),
    us_stock("SERV", "robotics"),

    # Pure-play and smaller AI-related names
    us_stock("AI", "pure-play enterprise AI"),
    us_stock("SOUN", "voice AI"),
    us_stock("BBAI", "decision intelligence"),
    us_stock("PATH", "automation AI"),
    us_stock("RXRX", "AI drug discovery"),
    us_stock("EXAI", "AI drug discovery"),
    us_stock("UPST", "AI lending"),
    us_stock("IONQ", "quantum/AI compute"),
    us_stock("RGTI", "quantum/AI compute"),
    us_stock("QBTS", "quantum/AI compute"),
]

RISK_PER_TRADE = 0.01
ATR_STOP_MULT  = 1.5
TAKE_PROFIT_RR = 2.0

# Daily breakout setup, similar to the chart examples:
# EMA 12/26/50/200 + resistance breakout + volume + RSI + MACD.
DATA_PERIOD          = "1y"
DATA_INTERVAL        = "1d"
BASE_LOOKBACK        = 60
BASE_EXCLUDE_BARS    = 3
MIN_DAILY_BARS       = BASE_LOOKBACK + BASE_EXCLUDE_BARS + 20
BREAKOUT_BUFFER      = 0.005
VOLUME_CONFIRM_MULT  = 1.2
RSI_BUY_MIN          = 55
RSI_BUY_MAX          = 78
RSI_EXIT_LEVEL       = 48

MARKET_PROFILES = {
    "US": {"timezone": "America/New_York", "trade_start": (10, 0), "trade_end": (15, 30), "weekend": {5, 6}},
    "JP": {"timezone": "Asia/Tokyo", "trade_start": (9, 0), "trade_end": (15, 30), "weekend": {5, 6}},
    "HK": {"timezone": "Asia/Hong_Kong", "trade_start": (9, 30), "trade_end": (16, 0), "weekend": {5, 6}},
    "EU": {"timezone": "Europe/Amsterdam", "trade_start": (9, 0), "trade_end": (17, 30), "weekend": {5, 6}},
    "UK": {"timezone": "Europe/London", "trade_start": (8, 0), "trade_end": (16, 30), "weekend": {5, 6}},
    "TH": {"timezone": "Asia/Bangkok", "trade_start": (10, 0), "trade_end": (16, 30), "weekend": {5, 6}},
    "CRYPTO": {"timezone": "UTC", "trade_start": (0, 0), "trade_end": (23, 59), "weekend": set()},
}

# =========================
# LINE MESSAGING API
# =========================
def send_line(message: str):
    if not LINE_CHANNEL_TOKEN or not LINE_USER_ID:
        print("LINE skipped: LINE_CHANNEL_TOKEN or LINE_USER_ID is not set")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}],
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"LINE Error: {resp.status_code} - {resp.text}")

# =========================
# INDICATORS
# =========================
def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def calc_macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def add_chart_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for period in (12, 26, 50, 200):
        df[f"EMA{period}"] = df["Close"].ewm(span=period, adjust=False).mean()

    df["RSI"] = calc_rsi(df["Close"])
    df["RSI_MA"] = df["RSI"].rolling(14).mean()
    df["MACD"], df["MACD_SIGNAL"], df["MACD_HIST"] = calc_macd(df["Close"])
    df["ATR"] = calc_atr(df)
    df["VolAvg20"] = df["Volume"].rolling(20).mean()

    df["Resistance"] = df["High"].shift(BASE_EXCLUDE_BARS).rolling(BASE_LOOKBACK).max()
    df["Support"] = df["Low"].shift(BASE_EXCLUDE_BARS).rolling(BASE_LOOKBACK).min()
    return df

def analyze_chart_setup(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(last["Close"])
    resistance = float(last["Resistance"])
    support = float(last["Support"])
    atr = float(last["ATR"])
    avg_vol = float(last["VolAvg20"])

    ema12 = float(last["EMA12"])
    ema26 = float(last["EMA26"])
    ema50 = float(last["EMA50"])
    ema200 = float(last["EMA200"])

    ema_bull = price > ema12 > ema26 > ema50 > ema200
    above_long_trend = price > ema50 and ema50 > ema200
    just_broke_out = (
        pd.notna(resistance)
        and price > resistance * (1 + BREAKOUT_BUFFER)
        and float(prev["Close"]) <= resistance * (1 + BREAKOUT_BUFFER)
    )
    breakout_continuation = (
        pd.notna(resistance)
        and price > resistance * (1 + BREAKOUT_BUFFER)
        and price > ema12
        and float(last["Low"]) >= ema26 * 0.98
    )
    pullback_bounce = (
        price > ema12
        and float(last["Low"]) <= ema26 * 1.02
        and float(prev["Close"]) > float(prev["EMA50"])
    )
    near_resistance = pd.notna(resistance) and price >= resistance * 0.97

    vol_confirm = pd.notna(avg_vol) and float(last["Volume"]) > avg_vol * VOLUME_CONFIRM_MULT
    rsi_buy_zone = RSI_BUY_MIN <= float(last["RSI"]) <= RSI_BUY_MAX
    rsi_strength = float(last["RSI"]) > float(last["RSI_MA"]) or float(last["RSI"]) >= 60
    macd_confirm = float(last["MACD"]) > float(last["MACD_SIGNAL"]) and float(last["MACD_HIST"]) > 0

    buy_signal = (
        (just_broke_out or breakout_continuation or pullback_bounce)
        and (ema_bull or above_long_trend)
        and vol_confirm
        and rsi_buy_zone
        and rsi_strength
        and macd_confirm
    )
    sell_signal = (
        price < ema26
        or float(last["RSI"]) < RSI_EXIT_LEVEL
        or float(last["MACD"]) < float(last["MACD_SIGNAL"])
        or (pd.notna(support) and price < support)
    )

    if just_broke_out:
        setup = "Fresh resistance breakout"
    elif breakout_continuation:
        setup = "Breakout continuation"
    elif pullback_bounce:
        setup = "EMA pullback bounce"
    elif near_resistance and above_long_trend:
        setup = "Watch near resistance"
    else:
        setup = "No setup"

    stop_from_support = support * 0.99 if pd.notna(support) else price - atr * ATR_STOP_MULT
    stop_from_atr = price - atr * ATR_STOP_MULT
    stop_price = max(stop_from_support, stop_from_atr)
    if stop_price >= price:
        stop_price = stop_from_atr

    return {
        "last": last,
        "price": price,
        "resistance": resistance,
        "support": support,
        "atr": atr,
        "avg_vol": avg_vol,
        "setup": setup,
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
        "ema_bull": ema_bull,
        "above_long_trend": above_long_trend,
        "just_broke_out": just_broke_out,
        "breakout_continuation": breakout_continuation,
        "pullback_bounce": pullback_bounce,
        "vol_confirm": vol_confirm,
        "rsi_buy_zone": rsi_buy_zone,
        "rsi_strength": rsi_strength,
        "macd_confirm": macd_confirm,
        "stop_price": stop_price,
    }

# =========================
# MARKET HOURS CHECK
# =========================
def is_market_open(market: str) -> bool:
    profile = MARKET_PROFILES.get(market, MARKET_PROFILES["US"])
    now = datetime.now(pytz.timezone(profile["timezone"]))
    if now.weekday() in profile["weekend"]:
        return False

    start_hour, start_minute = profile["trade_start"]
    end_hour, end_minute = profile["trade_end"]
    trade_start = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    trade_end = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    return trade_start <= now <= trade_end

def market_time_label(market: str) -> str:
    profile = MARKET_PROFILES.get(market, MARKET_PROFILES["US"])
    now = datetime.now(pytz.timezone(profile["timezone"]))
    return now.strftime("%Y-%m-%d %H:%M %Z")

# =========================
# POSITION SIZING
# =========================
def calc_qty(equity: float, entry: float, stop: float) -> int:
    risk_amount = equity * RISK_PER_TRADE
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return 1
    return max(int(risk_amount / risk_per_share), 1)

def can_submit_order(symbol_info: dict) -> bool:
    return (
        ENABLE_ORDER_EXECUTION
        and symbol_info.get("broker_symbol") is not None
        and is_market_open(symbol_info["market"])
    )

def submit_market_order(symbol_info: dict, side: OrderSide, qty: int | None = None, notional: float | None = None) -> bool:
    if not can_submit_order(symbol_info):
        return False

    order_kwargs = {
        "symbol": symbol_info["broker_symbol"],
        "side": side,
        "time_in_force": TimeInForce.DAY,
    }
    if notional is not None:
        order_kwargs["notional"] = round(notional, 2)
    else:
        order_kwargs["qty"] = qty

    get_trading_client().submit_order(MarketOrderRequest(**order_kwargs))
    return True

# =========================
# MAIN BOT
# =========================
def run_scan_cycle():
    cycle_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n===== Scan cycle started: {cycle_time} =====")

    if ENABLE_ORDER_EXECUTION:
        trading_client = get_trading_client()
        account = trading_client.get_account()
        equity = float(account.equity)
        positions = {p.symbol: p for p in trading_client.get_all_positions()}
        print(f"Account Equity: ${equity:,.2f}")
        print(
            f"Order execution enabled | Alpaca paper trading: {ALPACA_PAPER_TRADING} | "
            f"Max test buy notional: ${MAX_TEST_ORDER_NOTIONAL:.2f}"
        )
    else:
        equity = 10000.0
        positions = {}
        print("Global scan/test mode: order execution is disabled")

    for symbol_info in WATCHLIST:
        SYMBOL = symbol_info["symbol"]
        MARKET = symbol_info["market"]
        BROKER_SYMBOL = symbol_info.get("broker_symbol")
        THEME = symbol_info.get("theme", "general")
        market_open = is_market_open(MARKET)

        try:
            df = flatten(yf.download(SYMBOL, period=DATA_PERIOD, interval=DATA_INTERVAL, progress=False))

            if df.empty or len(df) < MIN_DAILY_BARS:
                print(f"[{SYMBOL}] Not enough daily data, skipping")
                continue

            df = add_chart_indicators(df).dropna()
            if len(df) < 2:
                print(f"[{SYMBOL}] Not enough indicator data, skipping")
                continue

            analysis = analyze_chart_setup(df)
            last = analysis["last"]

            current_price = analysis["price"]
            last_rsi = float(last["RSI"])
            last_atr = analysis["atr"]
            last_vol = float(last["Volume"])
            avg_vol = analysis["avg_vol"]

            print(
                f"[{SYMBOL}/{MARKET}] {THEME} | {analysis['setup']} | MarketOpen:{market_open} | "
                f"LocalTime:{market_time_label(MARKET)} | Price:{current_price:.2f} | "
                f"Res:{analysis['resistance']:.2f} | Sup:{analysis['support']:.2f} | "
                f"EMA12/26/50/200:{last['EMA12']:.2f}/{last['EMA26']:.2f}/{last['EMA50']:.2f}/{last['EMA200']:.2f} | "
                f"RSI:{last_rsi:.1f} | MACD:{last['MACD']:.2f}/{last['MACD_SIGNAL']:.2f} | "
                f"Vol:{last_vol:,.0f}/{avg_vol:,.0f} | VolOK:{analysis['vol_confirm']}"
            )

            position = positions.get(BROKER_SYMBOL) if BROKER_SYMBOL else None
            holding = position is not None

            if holding:
                entry_price = float(position.avg_entry_price)
                trailing_stop = max(entry_price - (last_atr * ATR_STOP_MULT), analysis["stop_price"])
                risk_per_share = last_atr * ATR_STOP_MULT
                tp_price = entry_price + risk_per_share * TAKE_PROFIT_RR
                qty_held = int(float(position.qty))

                if current_price <= trailing_stop:
                    order_sent = submit_market_order(symbol_info, OrderSide.SELL, qty=qty_held)
                    pnl = ((current_price / entry_price) - 1) * 100
                    msg = (
                        f"[{SYMBOL}] STOP LOSS\n"
                        f"Order : {'SENT' if order_sent else 'SCAN ONLY'}\n"
                        f"Entry : {entry_price:.2f}\n"
                        f"Stop  : {trailing_stop:.2f}\n"
                        f"Price : {current_price:.2f}\n"
                        f"P&L   : {pnl:.2f}%"
                    )
                    print(msg)
                    send_line(msg)
                    continue

                if current_price >= tp_price:
                    order_sent = submit_market_order(symbol_info, OrderSide.SELL, qty=qty_held)
                    pnl = ((current_price / entry_price) - 1) * 100
                    msg = (
                        f"[{SYMBOL}] TAKE PROFIT\n"
                        f"Order : {'SENT' if order_sent else 'SCAN ONLY'}\n"
                        f"Entry : {entry_price:.2f}\n"
                        f"TP    : {tp_price:.2f}\n"
                        f"Price : {current_price:.2f}\n"
                        f"P&L   : +{pnl:.2f}%"
                    )
                    print(msg)
                    send_line(msg)
                    continue

            if analysis["buy_signal"] and not holding:
                stop_price = analysis["stop_price"]
                tp_price = current_price + (current_price - stop_price) * TAKE_PROFIT_RR
                risk_qty = calc_qty(equity, current_price, stop_price)
                order_notional = min(risk_qty * current_price, MAX_TEST_ORDER_NOTIONAL)

                order_sent = submit_market_order(symbol_info, OrderSide.BUY, notional=order_notional)
                msg = (
                    f"[{SYMBOL}] BUY\n"
                    f"Market: {MARKET} | Theme: {THEME} | LocalTime: {market_time_label(MARKET)}\n"
                    f"Order : {'SENT' if order_sent else 'SCAN ONLY'}\n"
                    f"Setup : {analysis['setup']}\n"
                    f"Price : {current_price:.2f} | RiskQty: {risk_qty} | OrderNotional: ${order_notional:.2f}\n"
                    f"Res   : {analysis['resistance']:.2f} | Sup: {analysis['support']:.2f}\n"
                    f"Stop  : {stop_price:.2f}\n"
                    f"TP    : {tp_price:.2f} (R:R 1:{TAKE_PROFIT_RR})\n"
                    f"RSI   : {last_rsi:.1f} | MACD: {last['MACD']:.2f}/{last['MACD_SIGNAL']:.2f}\n"
                    f"Vol   : {last_vol:,.0f} / Avg20 {avg_vol:,.0f}"
                )
                print(msg)
                send_line(msg)

            elif analysis["sell_signal"] and holding:
                order_sent = submit_market_order(symbol_info, OrderSide.SELL, qty=int(float(position.qty)))
                msg = (
                    f"[{SYMBOL}] SELL SIGNAL\n"
                    f"Market : {MARKET} | Order: {'SENT' if order_sent else 'SCAN ONLY'}\n"
                    f"Price  : {current_price:.2f}\n"
                    f"Reason : Momentum/EMA support failed\n"
                    f"EMA26  : {last['EMA26']:.2f} | RSI: {last_rsi:.1f} | "
                    f"MACD: {last['MACD']:.2f}/{last['MACD_SIGNAL']:.2f}"
                )
                print(msg)
                send_line(msg)

            else:
                print(f"[{SYMBOL}] NO TRADE")

        except Exception as e:
            error_msg = f"[{SYMBOL}] ERROR: {e}"
            print(error_msg)
            send_line(error_msg)

    print("===== Scan cycle finished =====")

def main():
    if not RUN_CONTINUOUSLY:
        run_scan_cycle()
        return

    print(f"Auto trading loop started. Scan interval: {SCAN_INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")
    while True:
        run_scan_cycle()
        print(f"Sleeping {SCAN_INTERVAL_SECONDS} seconds before next scan...\n")
        time.sleep(SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Auto trading loop stopped by user.")
