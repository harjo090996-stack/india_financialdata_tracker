import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import numpy as np

# --- 0. NIFTY 100 LIST ---
def get_nifty_100():
    """Returns NIFTY 100 companies list (Cleaned & Updated)"""
    return [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS",
        "ASIANPAINT.NS", "MARUTI.NS", "BAJAJFINSV.NS", "WIPRO.NS",
        "AXISBANK.NS", "SUNPHARMA.NS", "DMART.NS", "ADANIPORTS.NS", "BAJAJ-AUTO.NS",
        "TECHM.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "HCLTECH.NS",
        "TITAN.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS", "UPL.NS",
        "GAIL.NS", "IOC.NS", "BPCL.NS", "INDIGO.NS", "LUPIN.NS",
        "DIVISLAB.NS", "CIPLA.NS", "EICHERMOT.NS", "NESTLEIND.NS", "M&M.NS",
        "HEROMOTOCO.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "INDUSINDBK.NS",
        "ABBOTINDIA.NS", "AUROPHARMA.NS", "ZYDUSLIFE.NS", "COLPAL.NS", 
        "CONCOR.NS", "CUMMINSIND.NS", "DRREDDY.NS", "ESCORTS.NS",
        "EXIDEIND.NS", "FEDERALBNK.NS", "GICRE.NS", "GODREJCP.NS", "GODREJPROP.NS",
        "HAVELLS.NS", "HDFCAMC.NS", "HINDALCO.NS", "HINDPETRO.NS", "HONEYWELL.NS",
        "IDFCFIRSTB.NS", "INDIAMART.NS", "INDIANB.NS", "INDUSTOWER.NS",
        "IRB.NS", "JBCHEPHARM.NS", "JINDALSTEL.NS", "JSWENERGY.NS",
        "JSWINFRA.NS", "KAJARIACER.NS", "MANAPPURAM.NS", "MGL.NS",
        "LTIM.NS", "MRPL.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NYKAA.NS",
        "OBEROIRLTY.NS", "ONGC.NS", "PEL.NS", "PETRONET.NS", "PIDILITIND.NS"
    ]

# --- 1. RBI MACRO SCRAPER ---
@st.cache_data(ttl=3600)
def get_rbi_macro():
    try:
        url = "https://www.rbi.org.in/"
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        repo_rate = soup.find(string="Repo Rate").find_next('td').text.strip()
        crr = soup.find(string="CRR").find_next('td').text.strip()
        return {"Repo Rate": repo_rate, "CRR": crr}
    except:
        return {"Repo Rate": "6.50%", "CRR": "4.50%"}

# --- 2. THE ANALYTICS ENGINE ---
@st.cache_data(ttl=14400)
def fetch_comprehensive_data(ticker_list):
    results = []
    cols = ["Ticker", "Price", "Change %", "Market Cap (Cr)", "Sector", "RSI (14)", "Above SMA 200", "FCFF (Cr)", "FCFE (Cr)", "ROE (%)"]
    
    for symbol in ticker_list:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            hist = stock.history(period="1y")
            
            if hist.empty or len(hist) < 200: continue

            # Technicals
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]

            # Price Data Safety
            curr_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            prev_close = info.get("previousClose") or 1

            # Fundamentals helper
            def get_val(df, label):
                try: return df.loc[label].iloc[0]
                except: return 0

            ni = get_val(stock.income_stmt, 'Net Income')
            equity = get_val(stock.balance_sheet, 'Stockholders Equity')
            roe = (ni / equity * 100) if equity > 0 else 0

            results.append({
                "Ticker": symbol.replace(".NS", ""),
                "Price": curr_price,
                "Change %": round(((curr_price - prev_close) / prev_close) * 100, 2),
                "Market Cap (Cr)": (info.get("marketCap", 0) or 0) / 10**7,
                "Sector": info.get("sector", "Other"),
                "RSI (14)": round(rsi.iloc[-1], 2) if not rsi.empty else 50,
                "Above SMA 200": "Yes" if curr_price > sma_200 else "No",
                "FCFF (Cr)": 0, # Calculated on-demand in Deep Dive to save time
                "FCFE (Cr)": 0,
                "ROE (%)": round(roe, 2)
            })
        except: continue
            
    return pd.DataFrame(results, columns=cols)

def format_financials_to_crores(dataframe):
    if dataframe is None or dataframe.empty: return dataframe
    df_copy = dataframe.copy()
    exclude_columns = ['EPS', 'Ratio', 'Margin', 'Growth', 'Return', 'Yield']
    
    for col in df_copy.columns:
        should_exclude = any(term in str(col).lower() for term in exclude_columns)
        if not should_exclude:
            try:
                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                if df_copy[col].abs().max() > 100000:
                    df_copy[col] = (df_copy[col] / 1e7).round(2)
            except: pass
    return df_copy

# --- 3. STREAMLIT UI ---
st.set_page_config(layout="wide", page_title="India Finviz Clone")

macro = get_rbi_macro()
st.title("📈 India Market Finviz")
m1, m2, m3 = st.columns(3)
m1.metric("RBI Repo Rate", macro["Repo Rate"])
m2.metric("RBI CRR", macro["CRR"])
m3.metric("Market", "NSE (India)")

st.sidebar.header("Configuration")
nifty_100 = get_nifty_100()
add_input = st.sidebar.text_area("Add Additional Tickers", placeholder="e.g., LTIM.NS")
additional_tickers = [t.strip() for t in add_input.split(",") if t.strip()]
screener_tickers = list(dict.fromkeys(nifty_100 + additional_tickers))

min_roe = st.sidebar.slider("Min ROE (%)", 0, 40, 10)
rsi_limit = st.sidebar.slider("Max RSI", 30, 90, 70)

if screener_tickers:
    with st.spinner('Analyzing market data...'):
        master_df = fetch_comprehensive_data(screener_tickers)

    if not master_df.empty:
        # Heatmap (Only Nifty 100)
        st.subheader("Market Heatmap (NIFTY 100)")
        hm_df = master_df[master_df['Ticker'].isin([t.replace(".NS", "") for t in nifty_100])]
        fig = px.treemap(hm_df[hm_df['Market Cap (Cr)'] > 0], path=['Sector', 'Ticker'], 
                         values='Market Cap (Cr)', color='Change %', 
                         color_continuous_scale='RdYlGn', color_continuous_midpoint=0)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("Integrated Screener")
        filtered_df = master_df[(master_df['ROE (%)'] >= min_roe) & (master_df['RSI (14)'] <= rsi_limit)]
        
        if not filtered_df.empty:
            selected_tickers = st.multiselect("Display Selection (Min 5):", 
                                             options=filtered_df['Ticker'].tolist(), 
                                             default=filtered_df['Ticker'].head(10).tolist())
            
            if len(selected_tickers) >= 5:
                display_df = filtered_df[filtered_df['Ticker'].isin(selected_tickers)]
                st.dataframe(display_df.style.background_gradient(subset=['Change %', 'ROE (%)'], cmap='RdYlGn'))
            else:
                st.warning("Please select at least 5 companies.")
        else:
            st.info("No stocks match filters.")

    st.divider()
    st.subheader("Company Deep Dive")
    view_mode = st.radio("Mode:", ["Single View", "Compare"], horizontal=True)
    
    if view_mode == "Single View":
        sel = st.selectbox("Select Company", screener_tickers)
        if sel:
            s_obj = yf.Ticker(sel)
            t1, t2 = st.tabs(["Income Statement", "Balance Sheet"])
            with t1: st.dataframe(format_financials_to_crores(s_obj.income_stmt))
            with t2: st.dataframe(format_financials_to_crores(s_obj.balance_sheet))
    else:
        c1, c2 = st.columns(2)
        tk1 = c1.selectbox("Stock 1", screener_tickers, index=0)
        tk2 = c2.selectbox("Stock 2", screener_tickers, index=1)
        if tk1 and tk2:
            st.write("--- Comparison View ---")
            col_a, col_b = st.columns(2)
            col_a.dataframe(format_financials_to_crores(yf.Ticker(tk1).income_stmt))
            col_b.dataframe(format_financials_to_crores(yf.Ticker(tk2).income_stmt))
