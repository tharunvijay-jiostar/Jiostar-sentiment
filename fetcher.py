"""
fetcher.py
----------
Fetches YouTube comments for JioStar shows and runs sentiment analysis
using HuggingFace's cardiffnlp/twitter-roberta-base-sentiment model.
"""

import os
import json
import time
import sqlite3
from datetime import datetime
from googleapiclient.discovery import build
from transformers import pipeline

# ── Config ────────────────────────────────────────────────────────────────────

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "YOUR_API_KEY_HERE")
DB_PATH = "data/sentiment.db"

# JioStar shows → their official YouTube channel search queries
SHOWS = {
    "IPL 2025":               "IPL 2025 highlights JioCinema",
    "Bigg Boss 18":           "Bigg Boss 18 official Colors TV",
    "Khatron Ke Khiladi":     "Khatron Ke Khiladi 14 official",
    "Anupamaa":               "Anupamaa Star Plus official",
    "Star Vs Food":           "Star Vs Food Disney Plus Hotstar",
}

MAX_COMMENTS_PER_VIDEO = 50   # YouTube free tier: 10,000 units/day
MAX_VIDEOS_PER_SHOW    = 3

# ── Sentiment model ───────────────────────────────────────────────────────────

def load_model():
    """
    Loads cardiffnlp/twitter-roberta-base-sentiment from HuggingFace.
    First run downloads ~500MB; cached locally after that.
    Labels: LABEL_0 = negative, LABEL_1 = neutral, LABEL_2 = positive
    """
    print("Loading sentiment model (downloads on first run)...")
    classifier = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-roberta-base-sentiment",
        tokenizer="cardiffnlp/twitter-roberta-base-sentiment",
        return_all_scores=True,
        truncation=True,
        max_length=512,
    )
    print("Model ready.")
    return classifier

LABEL_MAP = {
    "LABEL_0": "negative",
    "LABEL_1": "neutral",
    "LABEL_2": "positive",
}

def analyse_sentiment(classifier, text: str) -> dict:
    """
    Returns a dict with:
      - sentiment: 'positive' | 'neutral' | 'negative'
      - score:     0–100 confidence in the winning label
      - scores:    all three raw probabilities
    """
    text = text[:512].strip()
    if not text:
        return {"sentiment": "neutral", "score": 50, "scores": {}}

    results = classifier(text)[0]
    scores  = {LABEL_MAP[r["label"]]: round(r["score"] * 100, 1) for r in results}
    winner  = max(scores, key=scores.get)
    return {
        "sentiment": winner,
        "score":     scores[winner],
        "scores":    scores,
    }

# ── YouTube helpers ───────────────────────────────────────────────────────────

def get_youtube_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def search_videos(yt, query: str, max_results: int = MAX_VIDEOS_PER_SHOW) -> list[dict]:
    """Search YouTube for videos matching a show query."""
    response = yt.search().list(
        q=query,
        part="id,snippet",
        type="video",
        maxResults=max_results,
        order="date",                  # most recent first
        relevanceLanguage="hi",        # prefer Hindi results
    ).execute()

    videos = []
    for item in response.get("items", []):
        videos.append({
            "video_id":    item["id"]["videoId"],
            "title":       item["snippet"]["title"],
            "channel":     item["snippet"]["channelTitle"],
            "published_at": item["snippet"]["publishedAt"],
        })
    return videos

def fetch_comments(yt, video_id: str, max_comments: int = MAX_COMMENTS_PER_VIDEO) -> list[str]:
    """Fetch top-level comments for a video."""
    comments = []
    try:
        response = yt.commentThreads().list(
            videoId=video_id,
            part="snippet",
            maxResults=min(max_comments, 100),
            order="relevance",
            textFormat="plainText",
        ).execute()

        for item in response.get("items", []):
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            if len(text.strip()) > 10:          # skip very short comments
                comments.append(text.strip())

    except Exception as e:
        # Comments disabled or quota exceeded
        print(f"  Warning: could not fetch comments for {video_id}: {e}")

    return comments

# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            show_name   TEXT NOT NULL,
            video_id    TEXT NOT NULL,
            video_title TEXT,
            comment     TEXT NOT NULL,
            sentiment   TEXT NOT NULL,
            score       REAL NOT NULL,
            pos_score   REAL,
            neu_score   REAL,
            neg_score   REAL,
            platform    TEXT DEFAULT 'youtube',
            fetched_at  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at     TEXT NOT NULL,
            show_name  TEXT,
            videos     INTEGER,
            comments   INTEGER
        )
    """)
    conn.commit()
    return conn

def save_comment(conn, show: str, video: dict, comment: str, analysis: dict):
    conn.execute("""
        INSERT INTO comments
            (show_name, video_id, video_title, comment, sentiment, score,
             pos_score, neu_score, neg_score, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        show,
        video["video_id"],
        video["title"],
        comment,
        analysis["sentiment"],
        analysis["score"],
        analysis["scores"].get("positive"),
        analysis["scores"].get("neutral"),
        analysis["scores"].get("negative"),
        datetime.utcnow().isoformat(),
    ))

# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(shows: dict = SHOWS):
    conn       = init_db()
    classifier = load_model()
    yt         = get_youtube_client()

    total_comments = 0

    for show_name, query in shows.items():
        print(f"\n{'─'*50}")
        print(f"Show: {show_name}")
        print(f"Query: {query}")

        videos   = search_videos(yt, query)
        show_comments = 0

        for video in videos:
            print(f"  Video: {video['title'][:60]}...")
            comments = fetch_comments(yt, video["video_id"])
            print(f"  Fetched {len(comments)} comments")

            for comment in comments:
                analysis = analyse_sentiment(classifier, comment)
                save_comment(conn, show_name, video, comment, analysis)
                show_comments += 1

            conn.commit()
            time.sleep(0.5)     # be gentle with the API

        conn.execute(
            "INSERT INTO runs (run_at, show_name, videos, comments) VALUES (?,?,?,?)",
            (datetime.utcnow().isoformat(), show_name, len(videos), show_comments)
        )
        conn.commit()
        total_comments += show_comments
        print(f"  Done: {show_comments} comments analysed")

    conn.close()
    print(f"\nPipeline complete. Total comments analysed: {total_comments}")

if __name__ == "__main__":
    run_pipeline()
