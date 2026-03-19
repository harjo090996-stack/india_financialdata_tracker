import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import numpy as np

# --- 0. NIFTY 100 LIST ---
def get_nifty_100():
    """Returns NIFTY 100 companies list"""
    nifty_100 = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS",
        "ASIANPAINT.NS", "MARUTI.NS", "HDFC.NS", "BAJAJFINSV.NS", "WIPRO.NS",
        "AXISBANK.NS", "SUNPHARMA.NS", "DMARUTI.NS", "ADANIPORTS.NS", "BAJAJ-AUTO.NS",
        "TECHM.NS", "JSWSTEEL.NS", "TATA.NS", "KOTAKBANK.NS", "HCLTECH.NS",
        "TITAN.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS", "UPL.NS",
        "GAIL.NS", "IOC.NS", "BPCL.NS", "INDIGO.NS", "LUPIN.NS",
        "DIVISLAB.NS", "CIPLA.NS", "EICHERMOT.NS", "NESTLEIND.NS", "M&M.NS",
        "HEROMOTOCO.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "BANKINDIA.NS", "CENTRALBK.NS",
        "INDUSIND.NS", "ABCAPITAL.NS", "ABBOTINDIA.NS", "AUROPHARMA.NS", "CADILAHC.NS",
        "COLPAL.NS", "CONCOR.NS", "CUMMINSIND.NS", "DRREDDY.NS", "ESCORTS.NS",
        "EXIDEIND.NS", "FEDERALBNK.NS", "GICRE.NS", "GODREJCP.NS", "GODREJPROP.NS",
        "GRAPHITE.NS", "GRINDWELL.NS", "GSECL.NS", "HAVELLS.NS", "HDFCAMC.NS",
        "HEXAWARE.NS", "HINDALCO.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "HONEYWELL.NS",
        "ICIL.NS", "IDBI.NS", "IDEA.NS", "IDFCFIRSTB.NS", "IFBIND.NS",
        "IGAZPSU.NS", "INDIAMART.NS", "INDIANB.NS", "INDIGO.NS", "INDUSTOWER.NS",
        "IRB.NS", "JBCHEPHARM.NS", "JINDALSTEL.NS", "JSLHISSAR.NS", "JSWENERGY.NS",
        "JSWINFRA.NS", "KAJARIACER.NS", "MAHSEAMLESS.NS", "MANAPPURAM.NS", "MGL.NS",
        "MINDTREE.NS", "MRPL.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NYKAA.NS",
        "OBEROIRLTY.NS", "ONGC.NS", "PEL.NS", "PETRONET.NS", "PIDILITIND.NS"
    ]
    return nifty_100

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

def format_financials_to_crores(dataframe):
    """Convert financial statement values to Crores (divide by 10^7).
    Maintains columns that are ratios or small numbers unchanged."""
    df_copy = dataframe.copy()
    
    # List of columns that should NOT be divided (ratios, percentages, etc.)
    exclude_columns = ['EPS', 'Ratio', 'Margin', 'Growth', 'Return', 'Yield']
    
    for col in df_copy.columns:
        # Check if column should be excluded based on name
        should_exclude = any(exclude_term in str(col).lower() for exclude_term in exclude_columns)
        
        if not should_exclude:
            try:
                # Attempt to convert to numeric and divide by 10^7 for values > 1 million
                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                # Only convert columns with large numbers (likely in base currency)
                if (df_copy[col].abs().max() > 1_000_000) or (df_copy[col].notna().sum() > 0 and 
                    df_copy[col].abs().max() > 100_000):
                    df_copy[col] = df_copy[col] / 1e7
                    df_copy[col] = df_copy[col].round(2)
            except:
                pass
    
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
# Use NIFTY 100 companies by default
nifty_100 = get_nifty_100()
tickers = nifty_100

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
        filtered_df = df[(df['ROE (%)'] >= min_roe) & (df['RSI (14)'] <= rsi_limit)].reset_index(drop=True)
        
        if not filtered_df.empty:
            # Show first 10 companies by default
            initial_display_count = min(10, len(filtered_df))
            
            # Multiselect to add more companies
            all_available_tickers = filtered_df['Ticker'].tolist()
            default_tickers = filtered_df['Ticker'].head(initial_display_count).tolist()
            
            selected_tickers = st.multiselect(
                "Select companies to display (showing first 10 by default):",
                options=all_available_tickers,
                default=default_tickers,
                key="screener_select"
            )
            
            if selected_tickers:
                display_df = filtered_df[filtered_df['Ticker'].isin(selected_tickers)]
                st.dataframe(display_df.style.background_gradient(subset=['Change %', 'ROE (%)'], cmap='RdYlGn'))
            else:
                st.info("No companies selected to display.")
        else:
            st.info("No stocks match the current filters.")
    else:
        st.warning("Could not retrieve data. Please check ticker symbols.")

    st.divider()
    selected_stock = st.selectbox("Company Deep Dive", tickers)
    if selected_stock:
        s_obj = yf.Ticker(selected_stock)
        
        # Get financial statements and format to Crores
        income_stmt = s_obj.income_stmt
        balance_sheet = s_obj.balance_sheet
        cash_flow = s_obj.cashflow
        
        # Format data to Crores
        income_stmt_cr = format_financials_to_crores(income_stmt)
        balance_sheet_cr = format_financials_to_crores(balance_sheet)
        cash_flow_cr = format_financials_to_crores(cash_flow)
        
        t1, t2, t3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
        with t1: 
            st.caption("Values in Crores (₹)")
            st.dataframe(income_stmt_cr)
        with t2: 
            st.caption("Values in Crores (₹)")
            st.dataframe(balance_sheet_cr)
        with t3:
            st.caption("Values in Crores (₹)")
            st.dataframe(cash_flow_cr)
