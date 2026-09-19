import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

st.set_page_config(page_title="Pro Swing Screener", layout="wide")

st.title("🏆 Advanced Swing Trading Screener")
st.markdown("Strategy: EMA 50/200 + RSI 60 + MACD > 0 + Volume Spike + VCP")

# --- 1. Advanced Indicator Logic ---
def apply_advanced_strategy(df):
    # EMAs
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # Volume & ATR
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    
    # VCP Logic (Volatility Contraction - Check if range is tightening)
    df['Daily_Range'] = (df['High'] - df['Low']) / df['Close']
    df['Volat_5d'] = df['Daily_Range'].rolling(window=5).mean()
    df['Volat_20d'] = df['Daily_Range'].rolling(window=20).mean()
    
    return df

# --- 2. Candlestick Pattern Detection ---
def check_patterns(df):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Bullish Engulfing
    engulfing = (curr['Close'] > curr['Open']) and (prev['Close'] < prev['Open']) and \
                (curr['Close'] > prev['Open']) and (curr['Open'] < prev['Close'])
    
    # Bullish Marubozu (Body is 90% of total candle height)
    body_size = abs(curr['Close'] - curr['Open'])
    total_size = curr['High'] - curr['Low']
    marubozu = (curr['Close'] > curr['Open']) and (total_size > 0) and (body_size / total_size > 0.85)
    
    return "Engulfing" if engulfing else ("Marubozu" if marubozu else "None")

# --- 3. Reliable Ticker Loader ---
@st.cache_data
def get_nifty_500():
    try:
        url = "https://raw.githubusercontent.com/anirban-m/indian-stock-tickers/main/nifty500.csv"
        df = pd.read_csv(io.StringIO(requests.get(url).text))
        return [str(s).strip() + ".NS" for s in df['Symbol'].tolist()]
    except:
        return ["RELIANCE.NS", "TCS.NS", "SBIN.NS", "INFY.NS"]

# --- Sidebar Inputs ---
st.sidebar.header("Strategy Parameters")
target_date = st.sidebar.date_input("Analysis Date", datetime.now())
vol_threshold = st.sidebar.slider("Volume Multiplier (Smart Money)", 1.0, 3.0, 1.5)
rsi_threshold = st.sidebar.slider("RSI Power Zone", 50, 70, 60)

if st.sidebar.button("Run Full Strategy Scan"):
    tickers = get_nifty_500()
    end_dt = target_date + timedelta(days=1)
    
    results = []
    st.info(f"Scanning Nifty 500 with Deep Logic for {target_date}...")
    pb = st.progress(0)
    
    for i, ticker in enumerate(tickers[:300]): # Scanning 300 for mobile stability
        pb.progress((i + 1) / 300)
        try:
            df = yf.download(ticker, end=end_dt, period="2y", progress=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if len(df) < 200: continue
            
            df = apply_advanced_strategy(df)
            l = df.iloc[-1]
            
            # --- APPLYING YOUR CRITERIA ---
            # 1. Trend: Price > EMA 50 AND EMA 200
            uptrend = l['Close'] > l['EMA_50'] and l['Close'] > l['EMA_200']
            
            # 2. Momentum: RSI > 60 AND MACD > Signal AND MACD > 0
            momentum = l['RSI'] > rsi_threshold and l['MACD'] > l['Signal'] and l['MACD'] > 0
            
            # 3. Volume: Current Vol > 1.5x Avg
            volume_spike = l['Volume'] > (l['Vol_SMA_20'] * vol_threshold)
            
            # 4. VCP (Volatility Contraction): 5d volatility < 20d volatility
            vcp_setup = l['Volat_5d'] < l['Volat_20d']
            
            # 5. Candlestick Patterns
            pattern = check_patterns(df)
            
            if uptrend and momentum and volume_spike:
                # Calculate SL and Target (1:2 Risk Reward)
                sl_dist = 1.5 * l['ATR']
                sl = l['Close'] - sl_dist
                target = l['Close'] + (3 * l['ATR']) # approx 1:2
                
                results.append({
                    "Stock": ticker.replace(".NS",""),
                    "Price": round(float(l['Close']), 2),
                    "RSI": round(float(l['RSI']), 1),
                    "Pattern": pattern,
                    "VCP_Tight": "✅" if vcp_
