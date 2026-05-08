"""
app.py
------
Streamlit dashboard for JioStar Sentiment Analysis.
Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from analytics import (
    overall_sentiment,
    sentiment_by_show,
    daily_trend,
    recent_comments,
    sentiment_alerts,
)
from fetcher import run_pipeline, load_model, analyse_sentiment

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="JioStar Sentiment Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 JioStar Sentiment Dashboard")
st.caption("Real-time public sentiment across shows · Powered by YouTube API + HuggingFace")

# ── Sidebar controls ──────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Controls")
    days = st.slider("Days to analyse", 1, 30, 7)

    st.divider()
    st.subheader("Fetch new data")
    if st.button("🔄 Run pipeline now", use_container_width=True):
        with st.spinner("Fetching comments and analysing sentiment..."):
            run_pipeline()
        st.success("Pipeline complete!")
        st.rerun()

    st.divider()
    st.caption("Data stored in: data/sentiment.db")

# ── Top metric cards ──────────────────────────────────────────────────────────

overall = overall_sentiment(days=days)
shows   = sentiment_by_show(days=days)
alerts  = sentiment_alerts()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Overall positive", f"{overall['positive']}%",
              delta=None, help="% of positive comments in selected period")
with col2:
    st.metric("Comments analysed", f"{overall['total']:,}")
with col3:
    best = shows[0] if shows else {"show": "—", "positive": 0}
    st.metric("Top show", best["show"], f"{best['positive']}% positive")
with col4:
    worst = shows[-1] if shows else {"show": "—", "positive": 0}
    delta_color = "normal"
    st.metric("Needs attention", worst["show"], f"{worst['positive']}% positive",
              delta_color="inverse")

# ── Alerts ────────────────────────────────────────────────────────────────────

if alerts:
    st.warning(
        f"⚠️  **{len(alerts)} show(s) below 40% positive sentiment:** "
        + ", ".join(a["show"] for a in alerts)
    )

st.divider()

# ── Charts row ────────────────────────────────────────────────────────────────

left, right = st.columns(2)

with left:
    st.subheader("Sentiment by show")
    if shows:
        df_shows = pd.DataFrame(shows)
        fig = px.bar(
            df_shows,
            x="positive",
            y="show",
            orientation="h",
            color="positive",
            color_continuous_scale=["#E24B4A", "#EF9F27", "#639922"],
            range_color=[0, 100],
            labels={"positive": "Positive %", "show": ""},
            text="positive",
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            margin=dict(l=0, r=40, t=10, b=0),
            height=300,
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data yet. Run the pipeline from the sidebar.")

with right:
    st.subheader("7-day trend")
    trend = daily_trend(days=days)
    if trend:
        df_trend = pd.DataFrame(trend)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_trend["date"], y=df_trend["positive"],
                                   name="Positive", line=dict(color="#639922", width=2), fill="tozeroy",
                                   fillcolor="rgba(99,153,34,0.08)"))
        fig2.add_trace(go.Scatter(x=df_trend["date"], y=df_trend["negative"],
                                   name="Negative", line=dict(color="#E24B4A", width=2), fill="tozeroy",
                                   fillcolor="rgba(226,75,74,0.05)"))
        fig2.add_trace(go.Scatter(x=df_trend["date"], y=df_trend["neutral"],
                                   name="Neutral", line=dict(color="#888780", width=2)))
        fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                           yaxis=dict(range=[0, 100], ticksuffix="%"),
                           legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No trend data yet.")

# ── Comment feed ──────────────────────────────────────────────────────────────

st.divider()
st.subheader("Comment feed")

filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    show_names   = ["All shows"] + [s["show"] for s in shows]
    show_filter  = st.selectbox("Filter by show", show_names)
with filter_col2:
    sent_filter  = st.selectbox("Filter by sentiment", ["All", "positive", "neutral", "negative"])

comments = recent_comments(
    limit=50,
    show=None if show_filter == "All shows" else show_filter,
    sentiment=None if sent_filter == "All" else sent_filter,
)

SENTIMENT_COLOR = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}

if comments:
    df_comments = pd.DataFrame(comments)[["show_name", "sentiment", "score", "comment", "fetched_at"]]
    df_comments["sentiment"] = df_comments["sentiment"].map(
        lambda s: f"{SENTIMENT_COLOR.get(s, '')} {s}"
    )
    df_comments["score"] = df_comments["score"].map(lambda x: f"{x:.0f}%")
    df_comments.columns = ["Show", "Sentiment", "Confidence", "Comment", "Fetched at"]
    st.dataframe(df_comments, use_container_width=True, height=350)
else:
    st.info("No comments match the current filter.")

# ── Custom comment analyser ───────────────────────────────────────────────────

st.divider()
st.subheader("🔍 Analyse a custom comment")

custom_text = st.text_area("Paste a YouTube comment or tweet:", height=100,
                            placeholder="e.g. IPL coverage this year is absolutely insane...")

if st.button("Analyse sentiment", type="primary") and custom_text.strip():
    with st.spinner("Running model..."):
        classifier = load_model()
        result     = analyse_sentiment(classifier, custom_text)

    color_map = {"positive": "green", "neutral": "orange", "negative": "red"}
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Sentiment", result["sentiment"].capitalize())
    with col_b:
        st.metric("Confidence", f"{result['score']:.1f}%")
    with col_c:
        scores = result["scores"]
        st.metric("Positive / Neutral / Negative",
                  f"{scores.get('positive',0):.0f}% / {scores.get('neutral',0):.0f}% / {scores.get('negative',0):.0f}%")
