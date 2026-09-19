import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import requests
import io
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="Stock Screener Pro", layout="wide")

st.title("📈 Time-Machine Screener Pro")
st.markdown("Ye filter NSE Cash stocks ko scan karta hai.")

# Sidebar - Inputs
st.sidebar.header("Filter Settings")
ema_len = st.sidebar.number_input("EMA Length", value=50)
rsi_len = st.sidebar.number_input("RSI Length", value=14)
rsi_thresh = st.sidebar.number_input("RSI Threshold (>)", value=60)
vol_mult = st.sidebar.number_input("Volume Multiplier (x)", value=1.5)
target_date = st.sidebar.text_input("Target Date (YYYY-MM-DD)", help="Khali chhodne par aaj ka data lega")

# Function to get NSE stocks
@st.cache_data # Isse baar-baar download nahi hoga
def get_all_nse_stocks():
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers)
        df = pd.read_csv(io.StringIO(r.text))
        df_eq = df[df['SERIES'] == 'EQ']
        return [str(s).strip() + ".NS" for s in df_eq['SYMBOL'].tolist()]
    except:
        return []

if st.sidebar.button("Run Scanner"):
    tickers = get_all_nse_stocks()
    
    if not tickers:
        st.error("NSE stocks fetch nahi ho paye. Check Internet.")
    else:
        st.info(f"Total {len(tickers)} stocks scan ho rahe hain... Kripya wait karein.")
        
        selected_stocks = []
        progress_text = st.empty()
        bar = st.progress(0)
        
        # Performance ke liye hum ise chunks me scan kar sakte hain
        # Yahan main aapke original logic ko apply kar raha hu
        for i, ticker in enumerate(tickers):
            # Progress bar update
            if i % 20 == 0:
                bar.progress((i + 1) / len(tickers))
                progress_text.text(f"Scanning: {ticker} ({i}/{len(tickers)})")

            try:
                df = yf.download(ticker, period="1y", progress=False)
                if target_date:
                    df = df.loc[:target_date]
                
                if df.empty or len(df) < max(ema_len, rsi_len) + 20:
                    continue

                # Indicators
                df.ta.ema(length=ema_len, append=True)
                df.ta.rsi(length=rsi_len, append=True)
                df.ta.macd(append=True)
                df.ta.atr(length=14, append=True)
                df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()

                latest = df.iloc[-1]
                close = float(latest['Close'])
                ema_v = float(latest[f'EMA_{ema_len}'])
                rsi_v = float(latest[f'RSI_{rsi_len}'])
                macd_v = float(latest['MACD_12_26_9'])
                macd_s = float(latest['MACDs_12_26_9'])
                vol_c = float(latest['Volume'])
                vol_a = float(latest['Vol_SMA_20'])

                # Screening Logic
                if (close > ema_v and rsi_v > rsi_thresh and 
                    macd_v > macd_s and macd_v > 0 and 
                    vol_c > (vol_a * vol_mult)):
                    
                    atr_v = float(latest['ATRr_14'])
                    risk = 1.5 * atr_v
                    
                    selected_stocks.append({
                        "Symbol": ticker.replace(".NS", ""),
                        "Price": round(close, 2),
                        "RSI": round(rsi_v, 1),
                        "Vol_Spike": f"{round(vol_c/vol_a, 1)}x",
                        "SL": round(close - risk, 2),
                        "Target": round(close + (2 * risk), 2)
                    })
            except:
                continue

        # Results Display
        if selected_stocks:
            st.success(f"Dhunliya! {len(selected_stocks)} stocks mile.")
            res_df = pd.DataFrame(selected_stocks)
            st.table(res_df)
            
            # Watchlist Download
            tv_list = ",".join(["NSE:" + s['Symbol'] for s in selected_stocks])
            st.download_button("Download TradingView Watchlist", tv_list, file_name="watchlist.txt")
        else:
            st.warning("Koi stock match nahi hua.")