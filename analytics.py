"""
analytics.py
------------
Query the SQLite database to compute sentiment metrics for the dashboard.
All functions return plain dicts/lists — easy to plug into Streamlit or an API.
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "data/sentiment.db"

def get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ── Summary metrics (top metric cards) ───────────────────────────────────────

def overall_sentiment(days: int = 7, db_path: str = DB_PATH) -> dict:
    """
    Returns overall positive/neutral/negative % for the last N days.
    Example output:
      { 'positive': 72, 'neutral': 13, 'negative': 15, 'total': 48200 }
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn  = get_conn(db_path)
    rows  = conn.execute("""
        SELECT sentiment, COUNT(*) as cnt
        FROM comments
        WHERE fetched_at >= ?
        GROUP BY sentiment
    """, (since,)).fetchall()
    conn.close()

    counts = {r["sentiment"]: r["cnt"] for r in rows}
    total  = sum(counts.values()) or 1
    return {
        "positive": round(counts.get("positive", 0) / total * 100),
        "neutral":  round(counts.get("neutral",  0) / total * 100),
        "negative": round(counts.get("negative", 0) / total * 100),
        "total":    total,
    }

# ── Per-show sentiment score (0–100) ─────────────────────────────────────────

def sentiment_by_show(days: int = 7, db_path: str = DB_PATH) -> list[dict]:
    """
    Returns a list of shows sorted by positive sentiment score.
    Example:
      [{ 'show': 'IPL 2025', 'positive': 89, 'neutral': 8, 'negative': 3 }, ...]
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn  = get_conn(db_path)
    rows  = conn.execute("""
        SELECT show_name, sentiment, COUNT(*) as cnt
        FROM comments
        WHERE fetched_at >= ?
        GROUP BY show_name, sentiment
    """, (since,)).fetchall()
    conn.close()

    data = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
    for r in rows:
        data[r["show_name"]][r["sentiment"]] = r["cnt"]

    results = []
    for show, counts in data.items():
        total = sum(counts.values()) or 1
        results.append({
            "show":     show,
            "positive": round(counts["positive"] / total * 100),
            "neutral":  round(counts["neutral"]  / total * 100),
            "negative": round(counts["negative"] / total * 100),
            "total":    total,
        })

    return sorted(results, key=lambda x: x["positive"], reverse=True)

# ── Daily trend (for line chart) ─────────────────────────────────────────────

def daily_trend(days: int = 7, db_path: str = DB_PATH) -> list[dict]:
    """
    Returns day-by-day sentiment percentages.
    Example:
      [{ 'date': '2025-05-01', 'positive': 68, 'neutral': 17, 'negative': 15 }, ...]
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn  = get_conn(db_path)
    rows  = conn.execute("""
        SELECT DATE(fetched_at) as day, sentiment, COUNT(*) as cnt
        FROM comments
        WHERE fetched_at >= ?
        GROUP BY day, sentiment
        ORDER BY day ASC
    """, (since,)).fetchall()
    conn.close()

    daily = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
    for r in rows:
        daily[r["day"]][r["sentiment"]] = r["cnt"]

    trend = []
    for day in sorted(daily.keys()):
        counts = daily[day]
        total  = sum(counts.values()) or 1
        trend.append({
            "date":     day,
            "positive": round(counts["positive"] / total * 100),
            "neutral":  round(counts["neutral"]  / total * 100),
            "negative": round(counts["negative"] / total * 100),
        })
    return trend

# ── Recent comments feed ──────────────────────────────────────────────────────

def recent_comments(limit: int = 20, show: str = None, sentiment: str = None,
                    db_path: str = DB_PATH) -> list[dict]:
    """
    Fetch recent comments with optional filters.
    """
    conn   = get_conn(db_path)
    query  = "SELECT * FROM comments WHERE 1=1"
    params = []

    if show:
        query  += " AND show_name = ?"
        params.append(show)
    if sentiment:
        query  += " AND sentiment = ?"
        params.append(sentiment)

    query += " ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)

    rows   = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Alert: shows with declining sentiment ─────────────────────────────────────

def sentiment_alerts(threshold: int = 40, db_path: str = DB_PATH) -> list[dict]:
    """
    Returns shows where positive sentiment is below threshold — needs attention.
    """
    shows = sentiment_by_show(db_path=db_path)
    return [s for s in shows if s["positive"] < threshold]

# ── Quick summary print ───────────────────────────────────────────────────────

def print_summary(db_path: str = DB_PATH):
    print("\n" + "=" * 50)
    print("JIOSTAR SENTIMENT SUMMARY")
    print("=" * 50)

    overall = overall_sentiment(db_path=db_path)
    print(f"\nOverall (last 7 days) — {overall['total']:,} comments")
    print(f"  Positive: {overall['positive']}%")
    print(f"  Neutral:  {overall['neutral']}%")
    print(f"  Negative: {overall['negative']}%")

    print("\nBy show:")
    for s in sentiment_by_show(db_path=db_path):
        bar = "█" * (s["positive"] // 5)
        print(f"  {s['show']:<25} {bar} {s['positive']}% positive")

    alerts = sentiment_alerts(db_path=db_path)
    if alerts:
        print("\n⚠ Needs attention:")
        for a in alerts:
            print(f"  {a['show']} — only {a['positive']}% positive")

if __name__ == "__main__":
    print_summary()
