import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

st.set_page_config(page_title="Stock Filter Pro", layout="wide")

st.title("🚀 Swing Trading Bot (Nifty 500)")

# --- 1. Robust Indicator Logic ---
def get_indicators(df, ema_len):
    # EMA
    df['EMA'] = df['Close'].ewm(span=ema_len, adjust=False).mean()
    
    # RSI (Wilder's Smoothing - Standard)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # Volume SMA
    df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
    
    # ATR
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    return df

# --- 2. Reliable Ticker List ---
@st.cache_data
def load_tickers():
    try:
        url = "https://raw.githubusercontent.com/anirban-m/indian-stock-tickers/main/nifty500.csv"
        r = requests.get(url)
        df = pd.read_csv(io.StringIO(r.text))
        return [str(s).strip() + ".NS" for s in df['Symbol'].tolist()]
    except:
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]

# --- Sidebar ---
st.sidebar.header("Settings")
target_date = st.sidebar.date_input("Select Analysis Date", datetime.now())
ema_p = st.sidebar.slider("EMA Period", 20, 200, 50)
rsi_p = st.sidebar.slider("Min RSI", 40, 80, 55) # Thoda kam rakha hai default
vol_p = st.sidebar.slider("Min Vol Multiplier", 1.0, 5.0, 1.2) # 1.2x is more realistic

if st.sidebar.button("Start Scanning"):
    tickers = load_tickers()
    # End date: next day of selected to include selected date's candle
    end_dt = target_date + timedelta(days=1)
    
    st.info(f"Scanning Nifty 500 stocks for date: {target_date}...")
    
    results = []
    progress_bar = st.progress(0)
    
    # Scanning first 200 for speed, you can increase to len(tickers)
    total_to_scan = 200 
    
    for i, ticker in enumerate(tickers[:total_to_scan]):
        progress_bar.progress((i + 1) / total_to_scan)
        try:
            # Download more data (period="2y") to ensure indicators are accurate
            df = yf.download(ticker, end=end_dt, period="2y", progress=False)
            
            # Handle Yahoo Finance Multi-index issue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if len(df) < 100: continue

            df = get_indicators(df, ema_p)
            l = df.iloc[-1] # Latest row
            
            # --- THE FILTER LOGIC ---
            c1 = l['Close'] > l['EMA']
            c2 = l['RSI'] > rsi_p
            c3 = l['MACD'] > l['Signal']
            c4 = l['Volume'] > (l['Vol_Avg'] * vol_p)

            if c1 and c2 and c3 and c4:
                results.append({
                    "Symbol": ticker.replace(".NS",""),
                    "Date": df.index[-1].strftime('%Y-%m-%d'),
                    "Price": round(float(l['Close']), 2),
                    "RSI": round(float(l['RSI']), 1),
                    "Vol_Spike": f"{round(float(l['Volume']/l['Vol_Avg']), 1)}x",
                    "SL": round(float(l['Close'] - (1.5 * l['ATR'])), 2),
                    "Target": round(float(latest['Close'] + (3 * l['ATR'])), 2)
                })
        except:
            continue

    if results:
        st.success(f"Found {len(results)} stocks!")
        st.dataframe(pd.DataFrame(results))
    else:
        st.error("No stocks found for this specific combination.")
        st.write("💡 **Tip:** RSI ko 50 karke aur Vol Multiplier ko 1.0 karke check karein, shayad criteria bahut tight hai.")
