import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io

st.set_page_config(page_title="Nifty 500 Screener", layout="wide")

st.title("📊 Nifty 500 Swing Trading Filter")
st.markdown("Ye app Nifty 500 stocks ko scan karke Best Swing setups dhundti hai.")

# 1. Indicators Calculation (Pure Pandas - Very Fast)
def calculate_indicators(df, ema_len):
    # EMA
    df[f'EMA_{ema_len}'] = df['Close'].ewm(span=ema_len, adjust=False).mean()
    # RSI (14)
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
    # ATR (For SL/Target)
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    # Volume SMA
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df

# 2. Get Nifty 500 Tickers (Reliable Source)
@st.cache_data
def get_nifty_500_tickers():
    try:
        # Nifty 500 list from a stable source
        url = "https://raw.githubusercontent.com/anirban-m/indian-stock-tickers/main/nifty500.csv"
        s = requests.get(url).content
        df = pd.read_csv(io.StringIO(s.decode('utf-8')))
        # Yahoo Finance needs .NS at the end
        tickers = [str(sym).strip() + ".NS" for sym in df['Symbol'].tolist()]
        return tickers
    except:
        # Fallback agar URL kaam na kare
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]

# Sidebar Settings
st.sidebar.header("Filter Criteria")
ema_val = st.sidebar.number_input("EMA Period", value=50)
rsi_limit = st.sidebar.number_input("RSI Minimum", value=60)
vol_mult = st.sidebar.number_input("Volume Spike (x)", value=1.5)
scan_limit = st.sidebar.slider("Kitne stocks scan karein?", 50, 500, 500)

if st.sidebar.button("Nifty 500 Scan Karein"):
    tickers = get_nifty_500_tickers()
    tickers = tickers[:scan_limit] # User jitna chahe
    
    st.info(f"Scanning {len(tickers)} stocks... Isme 3-5 minute lag sakte hain.")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers):
        # Progress update
        progress_bar.progress((i + 1) / len(tickers))
        if i % 10 == 0:
            status_text.text(f"Checking: {ticker} ({i}/{len(tickers)})")
            
        try:
            # Download data
            df = yf.download(ticker, period="1y", progress=False)
            if len(df) < 50: continue
            
            df = calculate_indicators(df, ema_val)
            latest = df.iloc[-1]
            
            # Logic: Price > EMA and RSI > Limit and MACD Cross and High Volume
            if (latest['Close'] > latest[f'EMA_{ema_val}'] and 
                latest['RSI_14'] > rsi_limit and 
                latest['MACD'] > latest['Signal'] and
                latest['Volume'] > (latest['Vol_SMA_20'] * vol_mult)):
                
                risk = 1.5 * latest['ATR']
                results.append({
                    "Symbol": ticker.replace(".NS",""),
                    "Price": round(float(latest['Close']), 2),
                    "RSI": round(float(latest['RSI_14']), 1),
                    "Vol_Spike": f"{round(float(latest['Volume']/latest['Vol_SMA_20']), 1)}x",
                    "StopLoss": round(float(latest['Close'] - risk), 2),
                    "Target": round(float(latest['Close'] + (2*risk)), 2)
                })
        except:
            continue

    status_text.empty()
    
    if results:
        st.success(f"Dhunliya! {len(results)} Setup mile hain.")
        final_df = pd.DataFrame(results)
        st.dataframe(final_df, use_container_width=True)
        
        # TradingView Watchlist format mein download
        tv_watchlist = ",".join(["NSE:" + r['Symbol'] for r in results])
        st.download_button("Download TradingView Watchlist", tv_watchlist, "watchlist.txt")
    else:
        st.warning("Abhi koi stock criteria match nahi kar raha. RSI ya Volume thoda kam karke dekhein.")
