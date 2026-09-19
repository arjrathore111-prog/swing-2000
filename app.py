import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

st.set_page_config(page_title="Advanced Swing Screener", layout="wide")

st.title("🏆 Pro Swing Trading Bot (Advanced Logic)")
st.markdown("Trend: EMA 50/200 | Momentum: RSI 60 & MACD | Volume: 1.5x Spike")

# --- 1. Advanced Indicator Logic ---
def apply_advanced_strategy(df, ema_val):
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
    
    # VCP Logic (Volatility Tightening)
    df['Daily_Range'] = (df['High'] - df['Low']) / df['Close']
    df['Volat_5d'] = df['Daily_Range'].rolling(window=5).mean()
    df['Volat_20d'] = df['Daily_Range'].rolling(window=20).mean()
    
    return df

# --- 2. Pattern Detection ---
def check_patterns(df):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    # Engulfing
    engulfing = (curr['Close'] > curr['Open']) and (prev['Close'] < prev['Open']) and \
                (curr['Close'] > prev['Open']) and (curr['Open'] < prev['Close'])
    # Marubozu
    body = abs(curr['Close'] - curr['Open'])
    total = curr['High'] - curr['Low']
    marubozu = (curr['Close'] > curr['Open']) and (total > 0) and (body / total > 0.85)
    
    if engulfing: return "Bullish Engulfing"
    if marubozu: return "Bullish Marubozu"
    return "Neutral"

# --- 3. Reliable Ticker Loader ---
@st.cache_data
def get_nifty_500():
    try:
        url = "https://raw.githubusercontent.com/anirban-m/indian-stock-tickers/main/nifty500.csv"
        r = requests.get(url)
        df = pd.read_csv(io.StringIO(r.text))
        return [str(s).strip() + ".NS" for s in df['Symbol'].tolist()]
    except:
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "SBIN.NS"]

# --- Sidebar ---
st.sidebar.header("Strategy Settings")
target_date = st.sidebar.date_input("Select Date", datetime.now())
vol_mult = st.sidebar.slider("Volume Multiplier", 1.0, 3.0, 1.5)
rsi_min = st.sidebar.slider("Min RSI", 40, 70, 60)

if st.sidebar.button("Start Advanced Scan"):
    tickers = get_nifty_500()
    end_dt = target_date + timedelta(days=1)
    
    results = []
    st.info(f"Scanning Nifty 500 stocks for {target_date}...")
    pb = st.progress(0)
    
    for i, ticker in enumerate(tickers[:300]): # Scanning 300 for stability
        pb.progress((i + 1) / 300)
        try:
            df = yf.download(ticker, end=end_dt, period="2y", progress=False)
            
            # Multi-index fix
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            if len(df) < 200: continue
            
            df = apply_advanced_strategy(df, 50)
            l = df.iloc[-1]
            
            # --- CRITERIA CHECKS ---
            uptrend = (l['Close'] > l['EMA_50']) and (l['Close'] > l['EMA_200'])
            momentum = (l['RSI'] > rsi_min) and (l['MACD'] > l['Signal']) and (l['MACD'] > 0)
            volume = (l['Volume'] > (l['Vol_SMA_20'] * vol_mult))
            vcp = l['Volat_5d'] < l['Volat_20d']
            
            if uptrend and momentum and volume:
                pattern = check_patterns(df)
                sl_dist = 1.5 * l['ATR']
                
                results.append({
                    "Stock": ticker.replace(".NS",""),
                    "Price": round(float(l['Close']), 2),
                    "RSI": round(float(l['RSI']), 1),
                    "Vol_Spike": f"{round(float(l['Volume']/l['Vol_SMA_20']), 1)}x",
                    "Pattern": pattern,
                    "VCP_Tight": "✅" if vcp else "❌",
                    "SL": round(float(l['Close'] - sl_dist), 2),
                    "Target": round(float(l['Close'] + (3 * l['ATR'])), 2)
                })
        except:
            continue

    if results:
        st.success(f"Found {len(results)} Pro Setups!")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("No stocks matched all criteria. Try lowering RSI to 50 or Volume to 1.2x.")
