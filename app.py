import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io

st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.title("📈 Swing Trading Filter (No-Error Version)")

# Indicators Logic (Pure Pandas)
def calculate_indicators(df, ema_len, rsi_len):
    # EMA
    df[f'EMA_{ema_len}'] = df['Close'].ewm(span=ema_len, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_len).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_len).mean()
    rs = gain / loss
    df[f'RSI_{rsi_len}'] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # ATR & Volume SMA
    high_low = df['High'] - df['Low']
    high_cp = abs(df['High'] - df['Close'].shift())
    low_cp = abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(14).mean()
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df

@st.cache_data
def get_all_nse_stocks():
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_csv(io.StringIO(r.text))
        return [str(s).strip() + ".NS" for s in df[df['SERIES'] == 'EQ']['SYMBOL'].tolist()]
    except: return []

# Sidebar
ema_len = st.sidebar.number_input("EMA Length", value=50)
rsi_thresh = st.sidebar.number_input("RSI Above", value=60)
vol_mult = st.sidebar.number_input("Vol Multiplier", value=1.5)

if st.sidebar.button("Run Scanner"):
    tickers = get_all_nse_stocks()
    st.info(f"Scanning {len(tickers)} stocks...")
    results = []
    
    progress_bar = st.progress(0)
    for i, ticker in enumerate(tickers[:150]): # Starting with 150 for speed
        progress_bar.progress((i + 1) / 150)
        try:
            df = yf.download(ticker, period="1y", progress=False)
            if len(df) < 50: continue
            
            df = calculate_indicators(df, ema_len, 14)
            latest = df.iloc[-1]
            
            if (latest['Close'] > latest[f'EMA_{ema_len}'] and 
                latest['RSI_14'] > rsi_thresh and 
                latest['MACD'] > latest['Signal'] and latest['MACD'] > 0 and
                latest['Volume'] > (latest['Vol_SMA_20'] * vol_mult)):
                
                risk = 1.5 * latest['ATR']
                results.append({
                    "Symbol": ticker.replace(".NS",""),
                    "Price": round(float(latest['Close']), 2),
                    "RSI": round(float(latest['RSI_14']), 1),
                    "SL": round(float(latest['Close'] - risk), 2),
                    "Target": round(float(latest['Close'] + (2*risk)), 2)
                })
        except: continue

    if results:
        st.success(f"Found {len(results)} stocks!")
        st.table(pd.DataFrame(results))
    else: st.warning("No stocks found.")
