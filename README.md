# JioStar Sentiment Dashboard — Backend

Real-time sentiment analysis on public YouTube comments for JioStar shows,
using the YouTube Data API v3 and HuggingFace's RoBERTa model.

---

## Project structure

```
jiostar_sentiment/
├── fetcher.py        ← YouTube API + HuggingFace sentiment pipeline
├── analytics.py      ← Query SQLite DB, compute stats for dashboard
├── app.py            ← Streamlit dashboard
├── requirements.txt
├── .env              ← Your API key (create this, don't commit it)
└── data/
    └── sentiment.db  ← Auto-created SQLite database
```

---

## 1. Get a YouTube Data API key

1. Go to https://console.cloud.google.com
2. Create a new project (e.g. "JioStar Sentiment")
3. Enable **YouTube Data API v3**
4. Go to Credentials → Create API Key
5. Copy the key

---

## 2. Set up the project

```bash
# Clone / download the project folder, then:
cd jiostar_sentiment

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 3. Configure your API key

Create a `.env` file in the project root:

```
YOUTUBE_API_KEY=AIzaSy...your_key_here
```

Or export it directly:
```bash
export YOUTUBE_API_KEY="AIzaSy...your_key_here"
```

---

## 4. Run the pipeline

```bash
# Fetch YouTube comments + analyse sentiment → saves to data/sentiment.db
python fetcher.py
```

On first run, HuggingFace downloads the RoBERTa model (~500MB). It's cached
locally after that so subsequent runs are fast.

---

## 5. Launch the Streamlit dashboard

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 6. Automate with a cron job (optional)

Run the pipeline every 6 hours automatically:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path):
0 */6 * * * cd /path/to/jiostar_sentiment && source venv/bin/activate && python fetcher.py
```

---

## YouTube API quota notes

- Free tier: **10,000 units/day**
- `search.list` = 100 units per call
- `commentThreads.list` = 1 unit per call
- Current config (5 shows × 3 videos × 50 comments) ≈ **515 units/run** — safe

To add more shows, just add entries to the `SHOWS` dict in `fetcher.py`.

---

## Extending the project

| What to add | How |
|---|---|
| Reddit comments | Use `praw` library (Reddit's official Python API) |
| Twitter/X comments | Use `tweepy` with Academic API access |
| More languages (Tamil, Telugu) | Switch model to `ai4bharat/indic-bert` |
| Email alerts | Add `smtplib` call when `sentiment_alerts()` returns results |
| REST API | Wrap `analytics.py` functions with `fastapi` |
