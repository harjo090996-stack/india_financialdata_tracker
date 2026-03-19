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
        # Targeting the specific table class or text on RBI homepage
        repo_rate = soup.find(text="Repo Rate").find_next('td').text.strip()
        crr = soup.find(text="CRR").find_next('td').text.strip()
        return {"Repo Rate": repo_rate, "CRR": crr}
    except:
        # Fallback for 2026 current estimates if scraping fails
        return {"Repo Rate": "6.50%", "CRR": "4.50%"}

# --- 2. THE ANALYTICS ENGINE (Technical + CFA Fundamentals) ---
def fetch_comprehensive_data(ticker_list):
    results = []
    for symbol in ticker_list:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            hist = stock.history(period="1y")
            
            # --- Technical Indicators (Trader Focus) ---
            # RSI Calculation
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # SMAs
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]

            # --- CFA L2 Fundamentals (FCFF/FCFE) ---
            is_stmt = stock.income_stmt
            bs_stmt = stock.balance_sheet
            cf_stmt = stock.cashflow
            
            # Get latest year values
            ni = is_stmt.loc['Net Income'].iloc[0]
            ebit = is_stmt.loc['Ebit'].iloc[0]
            tax_prov = is_stmt.loc['Tax Provision'].iloc[0]
            pretax_inc = is_stmt.loc['Pretax Income'].iloc[0]
            tax_rate = tax_prov / pretax_inc if pretax_inc > 0 else 0.25
            
            dep = cf_stmt.loc['Depreciation And Amortization'].iloc[0]
            capex = abs(cf_stmt.loc['Capital Expenditure'].iloc[0])
            wc_change = cf_stmt.loc['Change In Working Capital'].iloc[0]
            int_exp = is_stmt.loc['Interest Expense'].iloc[0]
            net_borrowing = cf_stmt.loc['Net Issuance Payments Of Debt'].iloc[0]

            # FCFF = NI + NCC + [Int * (1-t)] - FCInv - WCInv
            fcff = ni + dep + (int_exp * (1 - tax_rate)) - capex - wc_change
            # FCFE = FCFF - [Int * (1-t)] + Net Borrowing
            fcfe = fcff - (int_exp * (1 - tax_rate)) + net_borrowing

            results.append({
                "Ticker": symbol.replace(".NS", ""),
                "Price": info.get("currentPrice"),
                "Change %": round(((info.get("currentPrice") - info.get("previousClose")) / info.get("previousClose")) * 100, 2),
                "Market Cap (Cr)": info.get("marketCap", 0) / 10**7,
                "Sector": info.get("sector"),
                "RSI (14)": round(rsi.iloc[-1], 2),
                "Above SMA 200": "Yes" if info.get("currentPrice") > sma_200 else "No",
                "FCFF (Cr)": round(fcff / 10**7, 2),
                "FCFE (Cr)": round(fcfe / 10**7, 2),
                "ROE (%)": round((ni / bs_stmt.loc['Stockholders Equity'].iloc[0]) * 100, 2)
            })
        except:
            continue
    return pd.DataFrame(results)

# --- 3. STREAMLIT UI ---
st.set_page_config(layout="wide", page_title="India Finviz Clone")

# Top Section: Macro Data
macro = get_rbi_macro()
st.title("📈 India Market Finviz (CFA L2 + Trader Dashboard)")
m1, m2, m3 = st.columns(3)
m1.metric("RBI Repo Rate", macro["Repo Rate"])
m2.metric("RBI CRR", macro["CRR"])
m3.metric("Market Region", "NSE (India)")

# Sidebar Ticker Input & Filters
st.sidebar.header("Configuration")
ticker_input = st.sidebar.text_area("Enter NSE Tickers (comma separated)", 
                                   "RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ICICIBANK.NS, BHARTIARTL.NS, SBIN.NS")
tickers = [t.strip() for t in ticker_input.split(",")]

st.sidebar.subheader("Screener Filters")
min_roe = st.sidebar.slider("Minimum ROE (%)", 0, 40, 15)
rsi_limit = st.sidebar.slider("Maximum RSI (Avoid Overbought)", 30, 90, 70)

# Fetch Data
with st.spinner('Calculating CFA Metrics & Technicals...'):
    df = fetch_comprehensive_data(tickers)

# Visual 1: Heatmap
st.subheader("Market Heatmap (Size: Market Cap | Color: % Change)")
if not df.empty:
    fig = px.treemap(df, path=['Sector', 'Ticker'], values='Market Cap (Cr)',
                     color='Change %', color_continuous_scale='RdYlGn', 
                     color_continuous_midpoint=0, hover_data=['RSI (14)', 'FCFF (Cr)'])
    st.plotly_chart(fig, use_container_width=True)

# Visual 2: The Screener
st.divider()
st.subheader("Visual 2: Integrated Screener")
filtered_df = df[(df['ROE (%)'] >= min_roe) & (df['RSI (14)'] <= rsi_limit)]
st.dataframe(filtered_df.style.background_gradient(subset=['Change %', 'ROE (%)'], cmap='RdYlGn'))

# Financial Deep Dive
st.divider()
st.subheader("Company Deep Dive (Audit Financials)")
selected_stock = st.selectbox("Select Ticker for Statement Analysis", tickers)
stock_obj = yf.Ticker(selected_stock)

tab1, tab2, tab3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
with tab1: st.dataframe(stock_obj.income_stmt)
with tab2: st.dataframe(stock_obj.balance_sheet)
with tab3: st.dataframe(stock_obj.cashflow)