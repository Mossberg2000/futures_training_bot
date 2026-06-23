# futures_training_bot.py

import streamlit as st
import yfinance as yf
import plotly.express as px
import pandas as pd
import feedparser

# ---------- CONFIG ----------

st.set_page_config(page_title="Futures Training Bot", layout="wide")

# Futures markets: symbol -> full name
MARKETS = {
    "ES=F": "S&P 500 Futures (ES)",
    "NQ=F": "Nasdaq Futures (NQ)",
    "YM=F": "Dow Futures (YM)",
    "RTY=F": "Russell 2000 Futures (RTY)",
    "CL=F": "Crude Oil Futures (CL)",
    "NG=F": "Natural Gas Futures (NG)",
    "GC=F": "Gold Futures (GC)",
    "SI=F": "Silver Futures (SI)",
    "6E=F": "Euro FX Futures (6E)",
    "6B=F": "British Pound Futures (6B)",
    "6J=F": "Japanese Yen Futures (6J)",
    "ZB=F": "30-Year Bond Futures (ZB)",
    "ZN=F": "10-Year Note Futures (ZN)",
}

MARKET_SYMBOLS = list(MARKETS.keys())

# ---------- INDEX MAPPING FOR NEWS + CONTEXT ----------

NEWS_ANALYST_MAP = {
    "ES=F": "^GSPC",
    "NQ=F": "^NDX",
    "YM=F": "^DJI",
    "RTY=F": "^RUT",
    "CL=F": "CL=F",
    "NG=F": "NG=F",
    "GC=F": "GC=F",
    "SI=F": "SI=F",
    "6E=F": "EURUSD=X",
    "6B=F": "GBPUSD=X",
    "6J=F": "JPY=X",
    "ZB=F": "^TNX",
    "ZN=F": "^TNX",
}

# ---------- SIMPLE BULLET DESCRIPTIONS FOR EACH INDEX ----------

INDEX_DESCRIPTIONS = {
    "^GSPC": [
        "Tracks 500 large U.S. companies",
        "Shows how the overall U.S. stock market is performing",
        "Used worldwide as a benchmark for market strength",
    ],
    "^NDX": [
        "Tracks the biggest technology and growth companies",
        "Moves quickly and reacts strongly to tech news",
        "Includes companies like Apple, Microsoft, Nvidia, and Amazon",
    ],
    "^DJI": [
        "Tracks 30 major U.S. companies",
        "Shows how the overall stock market is performing",
        "Includes companies like Apple, Boeing, and McDonald's",
    ],
    "^RUT": [
        "Tracks 2,000 small U.S. companies",
        "Shows how smaller businesses are performing",
        "Moves faster than large-cap indexes",
    ],
    "CL=F": [
        "Represents crude oil prices",
        "Moves quickly based on global events",
        "Affects gas prices, transportation, and trade",
    ],
    "NG=F": [
        "Represents natural gas prices",
        "Highly volatile and reacts to weather + supply changes",
        "Used heavily in energy production",
    ],
    "GC=F": [
        "Represents gold prices",
        "A safe-haven asset during uncertainty",
        "Moves when investors worry about the economy",
    ],
    "SI=F": [
        "Represents silver prices",
        "Moves with gold but with bigger swings",
        "Used in industry and investing",
    ],
    "EURUSD=X": [
        "Shows the value of the Euro vs the U.S. Dollar",
        "Moves based on interest rates and economic news",
        "Used to measure European economic strength",
    ],
    "GBPUSD=X": [
        "Shows the value of the British Pound vs the U.S. Dollar",
        "Moves based on UK economic conditions",
        "Affected by Bank of England decisions",
    ],
    "JPY=X": [
        "Shows the value of the Japanese Yen vs the U.S. Dollar",
        "Often used as a safe-haven currency",
        "Moves with global risk sentiment",
    ],
    "^TNX": [
        "Represents the 10-year U.S. Treasury yield",
        "Moves opposite to bond prices",
        "A key indicator for interest rates and inflation",
    ],
}

# ---------- MARKETWATCH NEWS KEYWORDS (MEDIUM FILTER) ----------

NEWS_KEYWORDS = {
    "^GSPC": ["s&p", "spx", "broad market", "large cap", "u.s. stocks"],
    "^NDX": ["nasdaq", "tech", "technology", "growth stocks", "big tech"],
    "^DJI": ["dow", "djia", "blue chip", "industrial stocks"],
    "^RUT": ["small caps", "russell", "rut", "small-cap", "small business"],
    "CL=F": ["oil", "crude", "energy markets", "oil prices"],
    "NG=F": ["natural gas", "gas prices", "energy"],
    "GC=F": ["gold", "precious metals", "safe haven"],
    "SI=F": ["silver", "metals", "precious metals"],
    "EURUSD=X": ["euro", "eurusd", "currency", "forex", "europe"],
    "GBPUSD=X": ["pound", "gbpusd", "sterling", "uk", "britain"],
    "JPY=X": ["yen", "jpy", "japan", "currency", "forex"],
    "^TNX": ["treasury", "yield", "interest rates", "bond market", "10-year"],
}

MARKETWATCH_FEED = "https://www.marketwatch.com/rss/topstories"

# ---------- HELPERS: DATA ----------

@st.cache_data
def load_market_data(symbol: str):
    data = yf.download(symbol, period="1mo", interval="1h")
    if data.empty:
        return data, pd.Timestamp.utcnow()
    data.columns = [col[0] if isinstance(col, tuple) else col for col in data.columns]
    return data, pd.Timestamp.utcnow()


def ensure_fresh_data(symbol: str, max_age_seconds: int = 300):
    data, ts = load_market_data(symbol)
    age = (pd.Timestamp.utcnow() - ts).total_seconds()
    if age > max_age_seconds:
        st.cache_data.clear()
        data, ts = load_market_data(symbol)
    return data, ts


def get_index_price_info(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        current_price = info.get("regularMarketPrice")
        prev_close = info.get("previousClose")
        day_change = None
        if current_price is not None and prev_close not in (None, 0):
            day_change = (current_price - prev_close) / prev_close * 100
        return {"current_price": current_price, "day_change": day_change}
    except Exception:
        return None

# ---------- HELPERS: NEWS ----------

@st.cache_data
def get_marketwatch_news(index_symbol: str, max_items: int = 3):
    feed = feedparser.parse(MARKETWATCH_FEED)
    entries = feed.entries or []

    keywords = NEWS_KEYWORDS.get(index_symbol, [])
    keywords_lower = [k.lower() for k in keywords]

    filtered = []
    for e in entries:
        title = getattr(e, "title", "") or ""
        link = getattr(e, "link", "") or ""
        summary = getattr(e, "summary", "") or ""
        text = (title + " " + summary).lower()

        if not title or not link:
            continue

        if keywords_lower:
            if any(k in text for k in keywords_lower):
                filtered.append({"title": title, "link": link})
        else:
            filtered.append({"title": title, "link": link})

        if len(filtered) >= max_items:
            break

    return filtered

# ---------- HELPERS: TREND + CHARTS ----------

def detect_trend(data: pd.DataFrame):
    """
    Real-world leaning (Option C) with a guard against impossible messages:
    - If rounded prices are the same -> sideways
    - Else if percent change is very small (< 0.1%) -> sideways
    - Else up/down based on sign of percent change
    """
    if data.empty or "Close" not in data.columns:
        return "sideways", "Not enough data to determine a clear trend."

    first_close = float(data["Close"].iloc[0])
    last_close = float(data["Close"].iloc[-1])

    # Rounded values for display (4 decimals to handle FX like Yen)
    first_r = round(first_close, 4)
    last_r = round(last_close, 4)

    pct_change = 0.0
    if first_close != 0:
        pct_change = ((last_close - first_close) / first_close) * 100

    same_rounded_price = first_r == last_r

    # Real-world leaning but avoid nonsense like "fell from 0.01 to 0.01"
    if same_rounded_price or abs(pct_change) < 0.1:
        return "sideways", (
            f"The price stayed near {first_r:.4f} and {last_r:.4f}, "
            f"changing only {pct_change:.2f}%. This suggests the market was mostly sideways, "
            f"with neither buyers nor sellers clearly in control."
        )

    if pct_change > 0:
        return "up", (
            f"The price increased from {first_r:.4f} to {last_r:.4f}, "
            f"a gain of {pct_change:.2f}%. This suggests buyers were stronger than sellers, "
            f"and the market was moving upward overall."
        )
    else:
        return "down", (
            f"The price fell from {first_r:.4f} to {last_r:.4f}, "
            f"a decrease of {pct_change:.2f}%. This suggests sellers were stronger than buyers, "
            f"and the market was moving downward overall."
        )


def compute_volatility_label(data: pd.DataFrame):
    if data.empty or "Close" not in data.columns:
        return "unknown", None

    returns = data["Close"].pct_change().dropna()
    if returns.empty:
        return "unknown", None

    vol = returns.std() * 100  # percent
    if vol < 0.5:
        label = "low"
    elif vol < 1.5:
        label = "moderate"
    else:
        label = "high"
    return label, vol


def plot_line_chart(data, title):
    fig = px.line(data, x=data.index, y="Close", title=title)
    fig.update_layout(height=400)
    return fig


def plot_trendline_overlay(data):
    df = data.copy()
    df["MA_5"] = df["Close"].rolling(window=5).mean()
    fig = px.line(df, x=df.index, y="Close")
    fig.add_scatter(x=df.index, y=df["MA_5"], mode="lines", name="5-Period MA")
    fig.update_layout(title="Smoothed Trendline (5-Period Moving Average)", height=300)
    return fig

# ---------- RENDER HELPERS ----------

def render_market_overview(futures_symbol: str):
    st.markdown("### Market Overview")

    index_symbol = NEWS_ANALYST_MAP.get(futures_symbol)
    price_info = get_index_price_info(index_symbol)

    if not price_info:
        st.info("Market overview is not available right now.")
        return

    st.write(f"**Index:** {index_symbol}")

    if price_info["current_price"] is not None:
        if price_info["day_change"] is not None:
            change = f"{price_info['day_change']:.2f}%"
            if price_info["day_change"] > 0:
                st.success(f"**Current Price:** {price_info['current_price']} (Up {change} today)")
            elif price_info["day_change"] < 0:
                st.error(f"**Current Price:** {price_info['current_price']} (Down {change} today)")
            else:
                st.info(f"**Current Price:** {price_info['current_price']} (Unchanged today)")
        else:
            st.write(f"**Current Price:** {price_info['current_price']}")

    st.markdown("#### What this market represents")
    for bullet in INDEX_DESCRIPTIONS.get(index_symbol, ["No description available."]):
        st.write(f"- {bullet}")

    st.markdown("#### Recent News")
    news_items = get_marketwatch_news(index_symbol, max_items=3)

    if not news_items:
        st.info("No recent news available for this index (MarketWatch).")
    else:
        for item in news_items:
            st.markdown(f"- [{item['title']}]({item['link']})")
        st.caption(f"*Filtered for {index_symbol}-related news (MarketWatch, medium filter).*")


def render_price_relationship_explanation():
    st.markdown("### Why the Chart Price and Current Price Look Different")
    st.write(
        """
You're looking at **two different instruments** that track the **same market**:

- The **chart** shows the **futures contract price**, which uses a large contract multiplier.
- The **Market Overview** shows the **index price**, which is the official value of the market.

Even though the **numbers are different**, the **direction is the same**.

This teaches you how to read the **trend**, not match the exact price.
"""
    )


def render_analyst_outlook(futures_symbol: str, data: pd.DataFrame):
    """
    Custom 'Analyst Outlook' using your own historical data:
    - Uses trend (up/down/sideways)
    - Uses approximate percent move
    - Uses volatility label
    - No external analyst ratings needed
    """
    st.markdown("### Analyst Outlook")

    if data.empty or "Close" not in data.columns:
        st.write("Not enough recent data to build an outlook.")
        return

    index_symbol = NEWS_ANALYST_MAP.get(futures_symbol)
    trend, _ = detect_trend(data)

    first_close = float(data["Close"].iloc[0])
    last_close = float(data["Close"].iloc[-1])
    pct_change = 0.0
    if first_close != 0:
        pct_change = ((last_close - first_close) / first_close) * 100

    vol_label, vol_value = compute_volatility_label(data)

    st.write(f"**Based on futures symbol:** {futures_symbol} (index reference: {index_symbol})")

    direction_text = {
        "up": "an overall upward bias (bullish tone)",
        "down": "an overall downward bias (bearish tone)",
        "sideways": "no clear directional bias (range-bound tone)",
    }.get(trend, "an uncertain directional bias")

    if vol_value is not None:
        st.write(
            f"Over this recent period, the market shows **{direction_text}**, "
            f"with an approximate move of **{pct_change:.2f}%** and "
            f"**{vol_label} volatility** (hourly standard deviation around {vol_value:.2f}%)."
        )
    else:
        st.write(
            f"Over this recent period, the market shows **{direction_text}**, "
            f"with an approximate move of **{pct_change:.2f}%**."
        )

    st.write(
        """
Use this as a simple, rules-based outlook:

- **Uptrend + low/moderate volatility:** steady bullish environment  
- **Uptrend + high volatility:** bullish but choppy, moves can reverse quickly  
- **Downtrend + low/moderate volatility:** steady bearish pressure  
- **Downtrend + high volatility:** sharp moves, risk of big swings  
- **Sideways:** focus on patience; the market is undecided  
"""
    )

# ---------- SIDEBAR ----------

st.sidebar.title("Futures Training Bot")

module = st.sidebar.selectbox("Select Module", ["Beginner Lesson", "Beginner Scenario"])

market_choice = st.sidebar.selectbox(
    "Select Market",
    ["All Markets"] + [MARKETS[sym] for sym in MARKET_SYMBOLS],
)

if st.sidebar.button("Refresh Market Data"):
    st.cache_data.clear()
    st.rerun()

# ---------- MAIN: BEGINNER LESSON ----------

if module == "Beginner Lesson":
    st.title("Understanding Futures with Simple Charts")

    st.write(
        """
Before you can trade or analyze any market, you need to understand **direction**.
Direction tells you who is in control:

- **Buyers (Uptrend)**
- **Sellers (Downtrend)**
- **Neither side (Sideways)**

A simple line chart is one of the easiest ways to see this.
"""
    )

    st.markdown("### What You’re Looking For")
    st.write(
        """
When you look at a chart, focus on the **overall movement from left to right**:

- **Uptrend:**  
  The line is rising over time. Price makes higher highs and higher lows.  
  This means buyers are stronger.

- **Downtrend:**  
  The line is falling over time. Price makes lower highs and lower lows.  
  This means sellers are stronger.

- **Sideways:**  
  The line moves in a range without clear direction.  
  This means neither side is in control.
"""
    )

    st.markdown("### Why This Matters")
    st.write(
        """
Trend reading is the foundation of trading.  
If you can identify direction, you can:

- Avoid trading against the market  
- Understand when momentum is building  
- Recognize when the market is slowing down  
- Build confidence before learning advanced tools  

Everything else — indicators, patterns, strategies — sits on top of this skill.
"""
    )

    st.markdown("### How Futures Fit In")
    st.write(
        """
Futures markets move quickly and respond to news, economic data, and global events.  
But no matter how fast they move, the **trend still tells the story**.

In this training, you’ll learn to read the trend using:

- Real futures charts  
- Real market data  
- Real index news and context  
- Simple explanations designed for beginners  
"""
    )

    st.success("When you're ready, switch to **Beginner Scenario** to practice reading real trends.")

# ---------- MAIN: BEGINNER SCENARIO ----------

if module == "Beginner Scenario":
    st.title("Beginner Practice Scenario: Futures Trend")
    st.write(
        """
Look at the overall direction from left to right and decide whether the market is
moving **up**, **down**, or **sideways**.
"""
    )

    if market_choice == "All Markets":

        if "market_index" not in st.session_state:
            st.session_state.market_index = 0
        if "show_explanation" not in st.session_state:
            st.session_state.show_explanation = False

        current_symbol = MARKET_SYMBOLS[st.session_state.market_index]
        current_name = MARKETS[current_symbol]

        st.subheader(f"{current_name} — Last 1 Month (1h Data)")

        data, ts = ensure_fresh_data(current_symbol)

        if data.empty:
            st.error("No price data returned.")
        else:
            st.plotly_chart(
                plot_line_chart(data, f"{current_name} (1h Data)"),
                use_container_width=True,
            )

            render_market_overview(current_symbol)
            render_price_relationship_explanation()

            trend, explanation = detect_trend(data)

            st.markdown("### Trendline Overlay")
            st.plotly_chart(plot_trendline_overlay(data), use_container_width=True)

            st.markdown("---")
            st.markdown("### Navigation")

            col1, col2, col3 = st.columns([1, 1, 1])

            if col1.button("Previous Market"):
                st.session_state.market_index = (
                    st.session_state.market_index - 1
                ) % len(MARKET_SYMBOLS)
                st.session_state.show_explanation = False

            if col2.button("Show Explanation"):
                st.session_state.show_explanation = True

            if col3.button("Next Market"):
                if st.session_state.show_explanation:
                    st.session_state.market_index = (
                        st.session_state.market_index + 1
                    ) % len(MARKET_SYMBOLS)
                    st.session_state.show_explanation = False
                else:
                    st.warning("View the explanation first before moving on.")

            if st.session_state.show_explanation:
                st.markdown("### Trend Explanation")
                if trend == "up":
                    st.success(explanation)
                elif trend == "down":
                    st.error(explanation)
                else:
                    st.info(explanation)

                render_analyst_outlook(current_symbol, data)

            st.caption(f"Data timestamp: {data.index[-1]} | Fetched at: {ts}")

    else:
        selected_name = market_choice
        current_symbol = next(sym for sym, name in MARKETS.items() if name == selected_name)
        current_name = MARKETS[current_symbol]

        st.subheader(f"{current_name} — Last 1 Month (1h Data)")

        data, ts = ensure_fresh_data(current_symbol)

        if data.empty:
            st.error("No price data returned.")
        else:
            st.plotly_chart(
                plot_line_chart(data, f"{current_name} (1h Data)"),
                use_container_width=True,
            )

            render_market_overview(current_symbol)
            render_price_relationship_explanation()

            trend, explanation = detect_trend(data)

            st.markdown("### What do you think the market is doing?")
            choice = st.radio("Choose one:", ["Going Up", "Going Down", "Sideways"])

            if st.button("Submit"):
                st.markdown("#### Feedback")
                if trend == "up" and choice == "Going Up":
                    st.success(f"Correct.\n\n{explanation}")
                elif trend == "down" and choice == "Going Down":
                    st.success(f"Correct.\n\n{explanation}")
                elif trend == "sideways" and choice == "Sideways":
                    st.success(f"Correct.\n\n{explanation}")
                else:
                    st.error(f"Not quite.\n\n{explanation}")

                render_analyst_outlook(current_symbol, data)

            st.caption(f"Data timestamp: {data.index[-1]} | Fetched at: {ts}")
