import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import numpy as np
from datetime import datetime, timedelta

# =========================================================
# PAGE SETUP
# =========================================================

st.set_page_config(
    page_title="Swing Screener Pro",
    page_icon="📈",
    layout="wide"
)

st.title("🚀 Advanced Swing Trading Screener")
st.caption("EMA + RSI + MACD + ATR + Volume + VCP | Historical Date Analysis")


# =========================================================
# INDICATORS
# =========================================================

def add_indicators(df):

    df = df.copy()

    # -------------------------
    # EMA
    # -------------------------
    df["EMA_50"] = df["Close"].ewm(
        span=50,
        adjust=False
    ).mean()

    df["EMA_200"] = df["Close"].ewm(
        span=200,
        adjust=False
    ).mean()

    # -------------------------
    # RSI 14
    # -------------------------
    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    # -------------------------
    # MACD
    # -------------------------
    ema12 = df["Close"].ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = df["Close"].ewm(
        span=26,
        adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26

    df["Signal"] = df["MACD"].ewm(
        span=9,
        adjust=False
    ).mean()

    # -------------------------
    # ATR 14
    # -------------------------
    prev_close = df["Close"].shift(1)

    tr1 = df["High"] - df["Low"]
    tr2 = abs(df["High"] - prev_close)
    tr3 = abs(df["Low"] - prev_close)

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["ATR"] = true_range.rolling(14).mean()

    # -------------------------
    # Volume
    # -------------------------
    df["Vol_Avg"] = df["Volume"].rolling(20).mean()

    df["Vol_Multiplier"] = (
        df["Volume"] / df["Vol_Avg"]
    )

    # -------------------------
    # VCP
    # -------------------------
    df["Range"] = (
        (df["High"] - df["Low"]) /
        df["Close"]
    )

    short_range = df["Range"].rolling(5).mean()
    long_range = df["Range"].rolling(20).mean()

    df["VCP_Check"] = short_range < long_range

    return df


# =========================================================
# LOAD NIFTY 500 STOCKS
# =========================================================

@st.cache_data(ttl=3600)
def get_tickers():

    try:

        url = (
            "https://raw.githubusercontent.com/"
            "anirban-m/indian-stock-tickers/main/nifty500.csv"
        )

        response = requests.get(
            url,
            timeout=15
        )

        response.raise_for_status()

        df_t = pd.read_csv(
            io.StringIO(response.text)
        )

        symbols = (
            df_t["Symbol"]
            .astype(str)
            .str.strip()
            .tolist()
        )

        return [
            symbol + ".NS"
            for symbol in symbols
        ]

    except Exception:

        return [
            "RELIANCE.NS",
            "TCS.NS",
            "INFY.NS",
            "HDFCBANK.NS",
            "SBIN.NS",
            "ICICIBANK.NS"
        ]


# =========================================================
# DOWNLOAD HISTORICAL DATA
# =========================================================

def download_stock_data(symbol, target_date):

    # We need enough historical data for EMA 200.
    # Download 2 years ending AFTER target date.

    start_date = target_date - timedelta(days=800)
    end_date = target_date + timedelta(days=1)

    data = yf.download(
        symbol,
        start=start_date,
        end=end_date,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
        multi_level_index=False
    )

    if data is None or data.empty:
        return None

    # Remove timezone if present
    if hasattr(data.index, "tz") and data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Ensure normal DatetimeIndex
    data.index = pd.to_datetime(data.index)

    # Sometimes Yahoo can return MultiIndex.
    if isinstance(data.columns, pd.MultiIndex):

        data.columns = data.columns.get_level_values(-1)

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    for col in required_columns:

        if col not in data.columns:
            return None

    data = data[required_columns].copy()

    # Keep only data up to analysis date
    target_timestamp = pd.Timestamp(target_date)

    data = data[
        data.index <= target_timestamp
    ]

    if len(data) < 220:
        return None

    return data


# =========================================================
# ANALYZE ONE STOCK
# =========================================================

def analyze_stock(symbol, target_date, rsi_min, vol_min):

    data = download_stock_data(
        symbol,
        target_date
    )

    if data is None:
        return None, "No sufficient historical data"

    df = add_indicators(data)

    # Drop rows where indicators are not ready
    df = df.dropna(
        subset=[
            "EMA_50",
            "EMA_200",
            "RSI",
            "MACD",
            "Signal",
            "ATR",
            "Vol_Avg"
        ]
    )

    if df.empty:
        return None, "Indicators unavailable"

    # IMPORTANT:
    # Last row is now the latest trading day
    # ON OR BEFORE selected Analysis Date.

    latest = df.iloc[-1]

    actual_date = df.index[-1].date()

    close = float(latest["Close"])
    ema50 = float(latest["EMA_50"])
    ema200 = float(latest["EMA_200"])
    rsi = float(latest["RSI"])
    macd = float(latest["MACD"])
    signal = float(latest["Signal"])
    atr = float(latest["ATR"])
    volume = float(latest["Volume"])
    vol_avg = float(latest["Vol_Avg"])

    vol_multiplier = (
        volume / vol_avg
        if vol_avg > 0
        else 0
    )

    vcp = bool(latest["VCP_Check"])

    # =====================================================
    # CONDITIONS
    # =====================================================

    trend_ok = (
        close > ema50
        and
        close > ema200
    )

    momentum_ok = (
        rsi >= rsi_min
        and
        macd > signal
    )

    volume_ok = (
        vol_multiplier >= vol_min
    )

    # =====================================================
    # FINAL SIGNAL
    # =====================================================

    if not (
        trend_ok
        and momentum_ok
        and volume_ok
    ):
        return None, "Conditions not satisfied"

    # =====================================================
    # STOP LOSS / TARGET
    # =====================================================

    # Risk = 1.5 ATR
    risk = 1.5 * atr

    stop_loss = close - risk

    # Reward = 3 ATR
    # Therefore Risk : Reward = 1 : 2
    target = close + (3 * atr)

    if stop_loss <= 0:
        return None, "Invalid Stop Loss"

    # =====================================================
    # RESULT
    # =====================================================

    result = {

        "Symbol":
            symbol.replace(".NS", ""),

        "Analysis Date":
            actual_date.strftime("%Y-%m-%d"),

        "Price":
            round(close, 2),

        "EMA 50":
            round(ema50, 2),

        "EMA 200":
            round(ema200, 2),

        "RSI":
            round(rsi, 1),

        "MACD":
            round(macd, 2),

        "Signal":
            round(signal, 2),

        "Volume":
            f"{vol_multiplier:.1f}x",

        "VCP":
            "✅" if vcp else "❌",

        "Stop