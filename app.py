import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup

# --- 0. CORRECTED NIFTY 100 LIST ---
def get_nifty_100():
    # Cleaned list (removed delisted/merged, fixed typos)
    return [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS",
        "ASIANPAINT.NS", "MARUTI.NS", "BAJAJFINSV.NS", "WIPRO.NS",
        "AXISBANK.NS", "SUNPHARMA.NS", "DMART.NS", "ADANIPORTS.NS", "BAJAJ-AUTO.NS",
        "TECHM.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "HCLTECH.NS",
        "TITAN.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS", "TATAMOTORS.NS",
        "TATASTEEL.NS", "INDUSINDBK.NS", "NESTLEIND.NS", "M&M.NS", "LTIM.NS",
        "ZYDUSLIFE.NS", "DRREDDY.NS", "ULTRACEMCO.NS", "BPCL.NS", "ONGC.NS"
    ] # Shortened for example speed; add the rest carefully

# --- 1. CACHED DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_screener_data(ticker_list):
    results = []
    # We only fetch info and history here (faster)
    for symbol in ticker_list:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # Fundamentals (Using yf.info is faster than full statements for 100 stocks)
            # Note: ROE is usually available in .info for major NSE stocks
            results.append({
                "Ticker": symbol.replace(".NS", ""),
                "Price": info.get("currentPrice") or info.get("regularMarketPrice", 0),
                "Change %": round(((info.get("currentPrice", 0) - info.get("previousClose", 1)) / info.get("previousClose", 1)) * 100, 2),
                "Market Cap (Cr)": (info.get("marketCap") or 0) / 10**7,
                "Sector": info.get("sector", "Other"),
                "ROE (%)": (info.get("returnOnEquity") or 0) * 100,
                "P/E": info.get("forwardPE", 0),
                "FullSymbol": symbol # Keep for Deep Dive
            })
        except: continue
    return pd.DataFrame(results)

def format_to_crores(df):
    if df is None or df.empty: return df
    return df.apply(lambda x: (pd.to_numeric(x, errors='coerce') / 1e7).round(2) if x.name not in ['Year', 'Quarter'] else x)

# --- 2. UI SETUP ---
st.set_page_config(layout="wide", page_title="India Finviz Clone")
st.title("📈 India Market Finviz")

# Sidebar
nifty_100 = get_nifty_100()
min_roe = st.sidebar.slider("Min ROE (%)", 0, 40, 10)

# Main Data Fetch
with st.spinner('Loading Market Data...'):
    master_df = fetch_screener_data(nifty_100)

if not master_df.empty:
    # 1. HEATMAP (Always shows Nifty 100)
    st.subheader("Market Heatmap (NIFTY 100)")
    # Filter out 0 market cap to prevent Plotly errors
    hm_df = master_df[master_df['Market Cap (Cr)'] > 0]
    fig = px.treemap(hm_df, path=['Sector', 'Ticker'], values='Market Cap (Cr)',
                     color='Change %', color_continuous_scale='RdYlGn', color_continuous_midpoint=0)
    st.plotly_chart(fig, use_container_width=True)

    # 2. SCREENER
    st.divider()
    st.subheader("Integrated Screener")
    filtered_df = master_df[master_df['ROE (%)'] >= min_roe]
    st.dataframe(filtered_df.style.background_gradient(subset=['Change %', 'ROE (%)'], cmap='RdYlGn'))

    # 3. DEEP DIVE (Heavy data fetched ONLY for selected stock)
    st.divider()
    st.subheader("Company Deep Dive")
    selected_ticker = st.selectbox("Select Company for Full Financials", master_df['FullSymbol'].tolist())
    
    if selected_ticker:
        s = yf.Ticker(selected_ticker)
        with st.spinner(f'Fetching full statements for {selected_ticker}...'):
            t1, t2 = st.tabs(["Income Statement", "Balance Sheet"])
            with t1: st.dataframe(format_to_crores(s.income_stmt))
            with t2: st.dataframe(format_to_crores(s.balance_sheet))
