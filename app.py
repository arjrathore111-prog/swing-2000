import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

# Page Setup
st.set_page_config(page_title="Swing Screener Pro", layout="wide")
st.title("🚀 Advanced Swing Trading Filter")

# --- Function: Indicator Calculation ---
def add_indicators(df):
    # EMA 50 & 200
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # ATR & Volume
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    df['Vol_Avg'] = df['Volume'].rolling(20).mean()
    
    # Volatility for VCP
    df['Range'] = (df['High'] - df['Low']) / df['Close']
    df['VCP_Check'] = df['Range'].rolling(5).mean() < df['Range'].rolling(20).mean()
    
    return df

# --- Function: Load Tickers ---
@st.cache_data
def get_tickers():
    try:
        url = "https://raw.githubusercontent.com/anirban-m/indian-stock-tickers/main/nifty500.csv"
        res = requests.get(url).text
        df_t = pd.read_csv(io.StringIO(res))
        return [str(s).strip() + ".NS" for s in df_t['Symbol'].tolist()]
    except:
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS"]

# --- Sidebar Inputs ---
st.sidebar.header("Scan Settings")
target_date = st.sidebar.date_input("Analysis Date", datetime.now() - timedelta(days=1))
rsi_min = st.sidebar.slider("Min RSI", 40, 70, 55)
vol_min = st.sidebar.slider("Min Vol Multiplier", 1.0, 3.0, 1.2)
num_stocks = st.sidebar.number_input("Stocks to Scan", value=100)

if st.sidebar.button("Start Advanced Scan"):
    all_symbols = get_tickers()
    selected_symbols = all_symbols[:num_stocks]
    
    end_date = target_date + timedelta(days=1)
    results = []
    
    st.info(f"Scanning {len(selected_symbols)} stocks for {target_date}...")
    prog = st.progress(0)
    status = st.empty()
    
    for i, sym in enumerate(selected_symbols):
        prog.progress((i + 1) / len(selected_symbols))
        status.text(f"Processing: {sym}")
        
        try:
            # Download Data
            data = yf.download(sym, end=end_date, period="2y", progress=False)
            
            # Handle New Yahoo Finance Multi-Index
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            if data.empty or len(data) < 200:
                continue
                
            df = add_indicators(data)
            l = df.iloc[-1] # Latest Data Row
            
            # --- THE LOGIC ---
            # 1. Trend: Close > EMA 50 & 200
            trend_ok = (l['Close'] > l['EMA_50']) and (l['Close'] > l['EMA_200'])
            
            # 2. Momentum: RSI > User Input & MACD Bullish
            momentum_ok = (l['RSI'] > rsi_min) and (l['MACD'] > l['Signal'])
            
            # 3. Volume: Vol > User Input * Avg
            vol_ok = l['Volume'] > (l['Vol_Avg'] * vol_min)
            
            if trend_ok and momentum_ok and vol_ok:
                sl = l['Close'] - (1.5 * l['ATR'])
                tgt = l['Close'] + (3.0 * l['ATR'])
                
                results.append({
                    "Symbol": sym.replace(".NS",""),
                    "Price": round(float(l['Close']), 2),
                    "RSI": round(float(l['RSI']), 1),
                    "Vol_Spike": f"{round(float(l['Volume']/l['Vol_Avg']), 1)}x",
                    "VCP": "✅" if l['VCP_Check'] else "❌",
                    "StopLoss": round(float(sl), 2),
                    "Target": round(float(tgt), 2)
                })
        except Exception as e:
            continue
            
    status.empty()
    
    if results:
        st.success(f"Found {len(results)} Stocks!")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("No stocks found. Suggestions:")
        st.write("1. Analysis Date ko pichle Friday par set karein.")
        st.write("2. RSI ko 50 aur Vol Multiplier ko 1.0 karke try karein.")
