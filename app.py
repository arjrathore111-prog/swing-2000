import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

st.set_page_config(page_title="Nifty 500 Date Screener", layout="wide")

st.title("📊 Nifty 500 Swing Filter (with Date Selection)")
st.markdown("Date select karein aur us din ke setup dekhein (Backtesting ke liye bhi useful hai).")

# 1. Indicators Calculation (Safe Version)
def calculate_indicators(df, ema_len):
    df[f'EMA_{ema_len}'] = df['Close'].ewm(span=ema_len, adjust=False).mean()
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    # ATR & Volume
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df

# 2. Get Nifty 500 Tickers
@st.cache_data
def get_nifty_500_tickers():
    try:
        url = "https://raw.githubusercontent.com/anirban-m/indian-stock-tickers/main/nifty500.csv"
        s = requests.get(url).content
        df = pd.read_csv(io.StringIO(s.decode('utf-8')))
        return [str(sym).strip() + ".NS" for sym in df['Symbol'].tolist()]
    except:
        return ["RELIANCE.NS", "TCS.NS", "SBIN.NS"]

# Sidebar settings
st.sidebar.header("Filter Settings")
# --- NAYA DATE OPTION ---
selected_date = st.sidebar.date_input("Kis Date tak scan karna hai?", datetime.now())
ema_val = st.sidebar.number_input("EMA Period", value=50)
rsi_limit = st.sidebar.number_input("RSI Minimum", value=60)
vol_mult = st.sidebar.number_input("Volume Spike (x)", value=1.5)

if st.sidebar.button("Run Time-Machine Scan"):
    tickers = get_nifty_500_tickers()
    
    # Yahoo finance needs next day for 'end' to include selected date
    end_date_str = (selected_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    st.info(f"Scanning Stocks up to: {selected_date}")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers[:300]): # Limit to 300 for mobile speed
        progress_bar.progress((i + 1) / 300)
        if i % 10 == 0:
            status_text.text(f"Checking: {ticker}")
            
        try:
            # Hum 2 saal ka data mangte hain taaki indicator sahi bane
            df = yf.download(ticker, end=end_date_str, period="2y", progress=False)
            
            if len(df) < 50: continue
            
            df = calculate_indicators(df, ema_val)
            latest = df.iloc[-1]
            actual_trading_date = df.index[-1].strftime('%Y-%m-%d')
            
            # Logic: Price > EMA, RSI > Limit, MACD bullish, Vol high
            if (latest['Close'] > latest[f'EMA_{ema_val}'] and 
                latest['RSI_14'] > rsi_limit and 
                latest['MACD'] > latest['Signal'] and
                latest['Volume'] > (latest['Vol_SMA_20'] * vol_mult)):
                
                risk = 1.5 * latest['ATR']
                results.append({
                    "Symbol": ticker.replace(".NS",""),
                    "Trade_Date": actual_trading_date,
                    "Price": round(float(latest['Close']), 2),
                    "RSI": round(float(latest['RSI_14']), 1),
                    "Vol": f"{round(float(latest['Volume']/latest['Vol_SMA_20']), 1)}x",
                    "SL": round(float(latest['Close'] - risk), 2),
                    "Target": round(float(latest['Close'] + (2*risk)), 2)
                })
        except:
            continue

    status_text.empty()
    
    if results:
        st.success(f"Success! {len(results)} Stocks match huye.")
        res_df = pd.DataFrame(results)
        # Table dikhayega
        st.dataframe(res_df, use_container_width=True)
    else:
        st.warning(f"{selected_date} par koi stock match nahi hua. Criteria kam karke try karein.")
