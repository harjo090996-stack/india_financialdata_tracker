import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import numpy as np

# --- 1. RBI MACRO SCRAPER ---
def get_rbi_macro():
    """Scrapes latest Policy Rates from RBI's main data page"""
    try:
        url = "https://www.rbi.org.in/"
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        # Updated to 'string' to avoid DeprecationWarning
        repo_rate = soup.find(string="Repo Rate").find_next('td').text.strip()
        crr = soup.find(string="CRR").find_next('td').text.strip()
        return {"Repo Rate": repo_rate, "CRR": crr}
    except:
        return {"Repo Rate": "6.50%", "CRR": "4.50%"}

# --- 2. THE ANALYTICS ENGINE ---
def fetch_comprehensive_data(ticker_list):
    results = []
    # Explicitly define columns to prevent KeyError if data is missing
    cols = ["Ticker", "Price", "Change %", "Market Cap (Cr)", "Sector", "RSI (14)", "Above SMA 200", "FCFF (Cr)", "FCFE (Cr)", "ROE (%)"]
    
    for symbol in ticker_list:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            hist = stock.history(period="1y")
            
            if hist.empty: continue

            # Technicals
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]

            # Fundamentals helper
            def get_val(df, label):
                try: return df.loc[label].iloc[0]
                except: return 0

            is_stmt = stock.income_stmt
            bs_stmt = stock.balance_sheet
            cf_stmt = stock.cashflow
            
            ni = get_val(is_stmt, 'Net Income')
            dep = get_val(cf_stmt, 'Depreciation And Amortization')
            capex = abs(get_val(cf_stmt, 'Capital Expenditure'))
            wc_change = get_val(cf_stmt, 'Change In Working Capital')
            int_exp = get_val(is_stmt, 'Interest Expense')
            tax_prov = get_val(is_stmt, 'Tax Provision')
            pretax = get_val(is_stmt, 'Pretax Income')
            net_debt = get_val(cf_stmt, 'Net Issuance Payments Of Debt')
            equity = get_val(bs_stmt, 'Stockholders Equity')

            tax_rate = tax_prov / pretax if pretax > 0 else 0.25
            fcff = ni + dep + (int_exp * (1 - tax_rate)) - capex - wc_change
            fcfe = fcff - (int_exp * (1 - tax_rate)) + net_debt
            roe = (ni / equity * 100) if equity > 0 else 0

            results.append({
                "Ticker": symbol.replace(".NS", ""),
                "Price": info.get("currentPrice", 0),
                "Change %": round(((info.get("currentPrice", 0) - info.get("previousClose", 1)) / info.get("previousClose", 1)) * 100, 2),
                "Market Cap (Cr)": info.get("marketCap", 0) / 10**7,
                "Sector": info.get("sector", "Other"),
                "RSI (14)": round(rsi.iloc[-1], 2) if not rsi.empty else 50,
                "Above SMA 200": "Yes" if info.get("currentPrice", 0) > sma_200 else "No",
                "FCFF (Cr)": round(fcff / 10**7, 2),
                "FCFE (Cr)": round(fcfe / 10**7, 2),
                "ROE (%)": round(roe, 2)
            })
        except Exception:
            continue
            
    return pd.DataFrame(results, columns=cols)

# --- 3. STREAMLIT UI ---
st.set_page_config(layout="wide", page_title="India Finviz Clone")

macro = get_rbi_macro()
st.title("📈 India Market Finviz")
m1, m2, m3 = st.columns(3)
m1.metric("RBI Repo Rate", macro["Repo Rate"])
m2.metric("RBI CRR", macro["CRR"])
m3.metric("Market", "NSE (India)")

st.sidebar.header("Configuration")
ticker_input = st.sidebar.text_area("Tickers (NSE)", "RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS")
tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]

min_roe = st.sidebar.slider("Min ROE (%)", 0, 40, 10)
rsi_limit = st.sidebar.slider("Max RSI", 30, 90, 70)

if tickers:
    with st.spinner('Analyzing...'):
        df = fetch_comprehensive_data(tickers)

    if not df.empty:
        st.subheader("Market Heatmap")
        fig = px.treemap(df, path=['Sector', 'Ticker'], values='Market Cap (Cr)',
                         color='Change %', color_continuous_scale='RdYlGn', color_continuous_midpoint=0)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("Integrated Screener")
        # Filtering with safety checks
        filtered_df = df[(df['ROE (%)'] >= min_roe) & (df['RSI (14)'] <= rsi_limit)]
        if not filtered_df.empty:
            st.dataframe(filtered_df.style.background_gradient(subset=['Change %', 'ROE (%)'], cmap='RdYlGn'))
        else:
            st.info("No stocks match the current filters.")
    else:
        st.warning("Could not retrieve data. Please check ticker symbols.")

    st.divider()
    selected_stock = st.selectbox("Company Deep Dive", tickers)
    if selected_stock:
        s_obj = yf.Ticker(selected_stock)
        t1, t2 = st.tabs(["Income Statement", "Balance Sheet"])
        with t1: st.dataframe(s_obj.income_stmt)
        with t2: st.dataframe(s_obj.balance_sheet)
