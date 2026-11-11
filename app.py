import hashlib
import html as htmllib
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from modules.global_news_search import search_global_news
from process_news import process_all_news


# ==========================================================
# 1. PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="News Article Intelligence System",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = Path("data/news.db")

PAGES = [
    "Dashboard",
    "Global News Search",
    "Latest News",
    "Trending Topics",
    "Daily Digest",
    "Multilingual Reader",
    "Saved Articles",
    "News Analytics",
    "My News Space",
]

LANGS = {
    "English": "en", "Hindi": "hi", "Telugu": "te", "Tamil": "ta",
    "Spanish": "es", "French": "fr", "German": "de", "Arabic": "ar",
    "Chinese": "zh-CN", "Japanese": "ja", "Russian": "ru",
}

BADGE = {"Positive": "🟢 Positive", "Neutral": "🟡 Neutral", "Negative": "🔴 Negative"}

# Extra publisher feeds, collected in addition to your process_all_news() pipeline.
# (publisher, feed url, category, country, language)
EXTRA_FEEDS = [
    ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml", "World", "United Kingdom", "English"),
    ("BBC News", "https://feeds.bbci.co.uk/news/business/rss.xml", "Business", "United Kingdom", "English"),
    ("BBC News", "https://feeds.bbci.co.uk/news/technology/rss.xml", "Technology", "United Kingdom", "English"),
    ("BBC News", "https://feeds.bbci.co.uk/news/health/rss.xml", "Health", "United Kingdom", "English"),
    ("BBC News", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "Science", "United Kingdom", "English"),
    ("The Guardian", "https://www.theguardian.com/world/rss", "World", "United Kingdom", "English"),
    ("The Guardian", "https://www.theguardian.com/uk/business/rss", "Business", "United Kingdom", "English"),
    ("The Guardian", "https://www.theguardian.com/technology/rss", "Technology", "United Kingdom", "English"),
    ("The Guardian", "https://www.theguardian.com/science/rss", "Science", "United Kingdom", "English"),
    ("The Guardian", "https://www.theguardian.com/society/health/rss", "Health", "United Kingdom", "English"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "World", "Qatar", "English"),
    ("DW News", "https://rss.dw.com/rdf/rss-en-all", "World", "Germany", "English"),
    ("The Hindu", "https://www.thehindu.com/news/national/feeder/default.rss", "World", "India", "English"),
    ("The Hindu", "https://www.thehindu.com/business/feeder/default.rss", "Business", "India", "English"),
    ("The Hindu", "https://www.thehindu.com/sci-tech/feeder/default.rss", "Technology", "India", "English"),
    ("NDTV", "https://feeds.feedburner.com/ndtvnews-top-stories", "World", "India", "English"),
]

# Used to fill Country / Language for articles whose database rows do not have them.
PUBLISHER_INFO = {
    "bbc": ("United Kingdom", "English"), "guardian": ("United Kingdom", "English"),
    "al jazeera": ("Qatar", "English"), "aljazeera": ("Qatar", "English"),
    "dw.com": ("Germany", "English"), "deutsche welle": ("Germany", "English"), "dw news": ("Germany", "English"),
    "thehindu": ("India", "English"), "the hindu": ("India", "English"), "ndtv": ("India", "English"),
    "indiatimes": ("India", "English"), "times of india": ("India", "English"),
    "cnn": ("United States", "English"), "nytimes": ("United States", "English"),
    "new york times": ("United States", "English"), "npr": ("United States", "English"),
    "reuters": ("United Kingdom", "English"), "apnews": ("United States", "English"),
}

EXPECTED_COLUMNS = [
    "id", "title", "description", "content", "source", "url", "image_url",
    "published_date", "category", "summary", "keywords", "entities",
    "sentiment", "source_country", "language",
]
TEXT_COLUMNS = [
    "title", "description", "content", "source", "url", "image_url",
    "published_date", "category", "summary", "source_country", "language",
]


# ==========================================================
# 2. CUSTOM DESIGN
# ==========================================================

st.markdown("""
<style>
    .main-title {
        font-size: 34px;
        font-weight: 800;
        color: #2878D0;
        margin-bottom: 5px;
    }

    .subtitle {
        color: #888888;
        font-size: 15px;
        margin-bottom: 20px;
    }

    div[data-testid="stMetric"] {
        background-color: rgba(120, 120, 120, 0.08);
        padding: 15px;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================================
# 3. DATABASE FUNCTIONS
# ==========================================================

@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_news_table():
    if not DB_PATH.exists():
        return None
    try:
        with db() as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "news" in tables:
            return "news"
        if "articles" in tables:
            return "articles"
        return None
    except sqlite3.Error:
        return None


def ensure_news_columns():
    """Adds nullable Country / Language columns if missing. Nothing is removed or changed."""
    table = get_news_table()
    if table is None:
        return
    try:
        with db() as conn:
            cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            for col in ("source_country", "language"):
                if col not in cols:
                    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {col} TEXT')
    except sqlite3.Error:
        pass


def init_tables():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS saved_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, source TEXT, url TEXT UNIQUE,
                image_url TEXT, published_date TEXT
            );
            CREATE TABLE IF NOT EXISTS reading_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, source TEXT, url TEXT, read_at TEXT
            );
            CREATE TABLE IF NOT EXISTS user_prefs (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT);
        """)
    ensure_news_columns()


def get_meta(key, default=None):
    with db() as conn:
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(key, value):
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO app_meta VALUES (?, ?)", (key, str(value)))


def get_pref(key, default):
    with db() as conn:
        row = conn.execute("SELECT value FROM user_prefs WHERE key=?", (key,)).fetchone()
    try:
        return json.loads(row[0]) if row else default
    except (json.JSONDecodeError, TypeError):
        return default


def set_pref(key, value):
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO user_prefs VALUES (?, ?)", (key, json.dumps(value)))


def save_article(article):
    try:
        with db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO saved_articles
                (title, source, url, image_url, published_date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                safe_text(article.get("title"), ""),
                safe_text(article.get("source"), ""),
                safe_text(article.get("url"), ""),
                safe_text(article.get("image_url"), ""),
                safe_text(article.get("published_date"), ""),
            ))
        return True
    except sqlite3.Error as error:
        st.error(f"Could not save article: {error}")
        return False


def unsave_article(url):
    with db() as conn:
        conn.execute("DELETE FROM saved_articles WHERE url=?", (url,))


def is_saved(url):
    with db() as conn:
        return conn.execute("SELECT 1 FROM saved_articles WHERE url=?", (url,)).fetchone() is not None


def load_bookmarks():
    try:
        with db() as conn:
            return pd.read_sql_query("SELECT * FROM saved_articles ORDER BY id DESC", conn)
    except Exception:
        return pd.DataFrame()


def mark_read(article):
    with db() as conn:
        conn.execute(
            "INSERT INTO reading_history (title, source, url, read_at) VALUES (?, ?, ?, ?)",
            (safe_text(article.get("title"), ""), safe_text(article.get("source"), ""),
             safe_text(article.get("url"), ""), datetime.now(timezone.utc).isoformat()),
        )


def load_history(limit=40):
    with db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM reading_history ORDER BY id DESC LIMIT ?", conn, params=(limit,))


def clear_personal_data():
    with db() as conn:
        conn.executescript("DELETE FROM saved_articles; DELETE FROM reading_history; DELETE FROM user_prefs;")


# ==========================================================
# 4. TEXT HELPERS AND NEWS UNDERSTANDING (NLP)
# ==========================================================

def parse_json(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text:
        return []
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return list(result.values())
        return [result]
    except (json.JSONDecodeError, TypeError):
        return [p.strip() for p in text.split(",") if p.strip()]


def safe_text(value, default="Not available"):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    value = str(value).strip()
    return value if value and value.lower() not in ("nan", "none") else default


def clean_text(text):
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", text).strip()


STOP = set("""the a an and or of to in on for with at by from is are was were be been as it its this that these those
after over new says said will has have had not but into more than their his her they you who what how why when where
about out up down off just also can could would should may might one two our your all any some most other such only
then there here being very much many year years day days week today news report reports amid""".split())
POS = set("""win wins won gain gains growth grow success improve improved record boost peace agree agreement deal recover
recovery rise rises safe breakthrough celebrate support hope progress benefit best good great strong launch launches
praise praised cure reward surge victory happy""".split())
NEG = set("""war attack attacks crash death dead die killed kill crisis fall falls fell loss lose fear threat conflict fire
flood disaster ban crime cut cuts risk warn warns warning collapse fail fails failure victim injured injuries
backlash protest scandal strike worst fraud arrest violence shortage decline drop drops""".split())
NEGATORS = {"no", "not", "never", "without", "cannot"}


def _words(text):
    return re.findall(r"[a-z][a-z'-]{2,}", text.lower())


def sentiment_score(text):
    tokens, raw = _words(text), 0
    for i, word in enumerate(tokens):
        s = 1 if word in POS else -1 if word in NEG else 0
        if s and i and tokens[i - 1] in NEGATORS:
            s = -s
        raw += s
    score = round(raw / (abs(raw) + 3), 3)
    return score, ("Positive" if score > 0.1 else "Negative" if score < -0.1 else "Neutral")


def existing_sentiment(value, text):
    """Understands labels or numbers already in your database; otherwise analyses the text."""
    s = safe_text(value, "").lower()
    if s:
        try:
            x = float(s)
            return ("Positive" if x > 0.1 else "Negative" if x < -0.1 else "Neutral"), x
        except ValueError:
            pass
        if "pos" in s:
            return "Positive", 0.5
        if "neg" in s:
            return "Negative", -0.5
        if "neu" in s:
            return "Neutral", 0.0
    score, label = sentiment_score(text)
    return label, score


def extract_keywords(text, n=6):
    counts = Counter(w for w in _words(text) if w not in STOP and len(w) > 3)
    return [w for w, _ in counts.most_common(n)]


def extract_entities(text, n=6):
    found = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*", text)
    entities = []
    for e in found:
        e = re.sub(r"^(The|A|An)\s+", "", e)
        if len(e) > 3 and e.lower() not in STOP and e not in entities:
            entities.append(e)
    return entities[:n]


def summarize(title, body, limit=320):
    body = clean_text(body)
    if len(body) < 40:
        return title
    out = ""
    for s in re.split(r"(?<=[.!?])\s+", body)[:3]:
        if len(out) + len(s) > limit and out:
            break
        out += (" " if out else "") + s
    return out[:limit + 40]


def key_points(text, n=3):
    """Picks the most informative sentences of an article as bullet points."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text(text)) if len(s.strip()) > 30]
    if len(sentences) < 2:
        return []
    freq = Counter(w for w in _words(text) if w not in STOP and len(w) > 3)
    scored = []
    for i, s in enumerate(sentences):
        ws = [w for w in _words(s) if w not in STOP]
        scored.append((sum(freq[w] for w in ws) / (len(ws) ** 0.5 + 1), i))
    best = sorted(sorted(scored, reverse=True)[:n], key=lambda x: x[1])
    return [sentences[i] for _, i in best]


def title_key(title):
    return re.sub(r"[^a-z0-9]", "", str(title).lower())[:90]


def infer_publisher_info(source, url):
    blob = f"{source} {url}".lower()
    for key, info in PUBLISHER_INFO.items():
        if key in blob:
            return info
    return None


def to_dt(value):
    s = str(value).strip() if value is not None else ""
    if not s or s.lower() in ("nan", "none", "nat", "not available"):
        return pd.NaT
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return pd.Timestamp(d).tz_convert("UTC")
    except Exception:
        pass
    try:
        return pd.to_datetime(s, utc=True)
    except Exception:
        return pd.NaT


def ago(ts):
    if ts is None or pd.isna(ts):
        return "unknown time"
    minutes = int((pd.Timestamp.now(tz="UTC") - ts).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 1440:
        return f"{minutes // 60} h ago"
    return f"{minutes // 1440} d ago"


def fmt_time(ts):
    if ts is None or pd.isna(ts):
        return "Not available"
    return f"{ts.strftime('%d %b %Y, %H:%M UTC')} · {ago(ts)}"


def enrich(df):
    """Prepares articles: dates, duplicates, country/language, summaries, keywords, entities, sentiment."""
    df = df.copy()
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    for col in TEXT_COLUMNS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["keywords"] = df["keywords"].apply(lambda v: "" if v is None else v)
    df["entities"] = df["entities"].apply(lambda v: "" if v is None else v)

    df["published_dt"] = pd.to_datetime(pd.Series([to_dt(v) for v in df["published_date"]], index=df.index), utc=True)
    df = df.sort_values("published_dt", ascending=False, na_position="last")

    # Duplicate removal: same title or same link
    keys = [title_key(t) or f"row{i}" for i, t in enumerate(df["title"])]
    df["_tk"] = keys
    df = df[~df.duplicated("_tk")]
    df = df[~(df["url"].ne("") & df.duplicated("url"))]

    rows = df.to_dict("records")
    out = {k: [] for k in ("summary_text", "kw_list", "ent_list", "label", "score", "_blob", "source_country", "language", "source")}
    for r in rows:
        source = r["source"] or "Unknown"
        info = infer_publisher_info(source, r["url"])
        country = r["source_country"] if r["source_country"] and r["source_country"] != "Not available" else (info[0] if info else "Unknown")
        language = r["language"] if r["language"] and r["language"] != "Not available" else (info[1] if info else "Unknown")
        body = r["description"] or r["content"][:700]
        text = f"{r['title']}. {body}"
        kws = [str(k) for k in parse_json(r["keywords"])] or extract_keywords(text)
        ents = [str(e) for e in parse_json(r["entities"])] or extract_entities(text)
        label, score = existing_sentiment(r["sentiment"], text)
        summary = r["summary"] if len(r["summary"]) >= 20 else summarize(r["title"], body)
        out["summary_text"].append(summary)
        out["kw_list"].append(kws[:8])
        out["ent_list"].append(ents[:8])
        out["label"].append(label)
        out["score"].append(score)
        out["source_country"].append(country)
        out["language"].append(language)
        out["source"].append(source)
        out["_blob"].append(" ".join([r["title"], body, summary, " ".join(kws), " ".join(ents), source, r["category"]]).lower())
    for k, v in out.items():
        df[k] = v
    return df.reset_index(drop=True)


def db_signature():
    try:
        return DB_PATH.stat().st_mtime_ns
    except OSError:
        return 0


def load_raw():
    table = get_news_table()
    if table is None:
        return pd.DataFrame()
    try:
        with db() as conn:
            return pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
    except Exception as error:
        st.error(f"Unable to load database articles: {error}")
        return pd.DataFrame()


@st.cache_data(show_spinner="Preparing articles…")
def _load_news(signature):
    raw = load_raw()
    return enrich(raw) if not raw.empty else raw


def load_news():
    return _load_news(db_signature())


def prepare_external(results):
    if isinstance(results, pd.DataFrame):
        df = results
    else:
        df = pd.DataFrame(results or [])
    return enrich(df) if not df.empty else df


def apply_filters(df, q="", category="All", country="All", language="All",
                  publisher="All", label="All", days=None):
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    for term in q.lower().split():
        mask &= df["_blob"].str.contains(term, regex=False)
    for col, val in (("category", category), ("source_country", country), ("language", language),
                     ("source", publisher), ("label", label)):
        if val and val != "All":
            mask &= df[col] == val
    if days:
        mask &= df["published_dt"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
    return df[mask]


def trending_topics(df, field="kw_list", hours=24, min_count=2):
    """Counts topics in the latest window compared with the window before it."""
    dated = df.dropna(subset=["published_dt"])
    if dated.empty:
        return pd.DataFrame(), None
    ref = min(dated["published_dt"].max(), pd.Timestamp.now(tz="UTC"))
    start, prev_start = ref - pd.Timedelta(hours=hours), ref - pd.Timedelta(hours=2 * hours)
    cur, prev = Counter(), Counter()
    for ts, items in zip(dated["published_dt"], dated[field]):
        if ts >= start:
            cur.update(set(items))
        elif ts >= prev_start:
            prev.update(set(items))
    rows = [{"Topic": k, "Now": c, "Before": prev[k], "Momentum": round(c / (prev[k] + 1), 2)}
            for k, c in cur.items() if c >= min_count]
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["Now", "Momentum"], ascending=False)
    return out, ref


def related_articles(article, pool, n=5):
    base = set(article.get("kw_list") or []) | set(article.get("ent_list") or [])
    if not base or pool.empty:
        return []
    scored = []
    for r in pool.head(1500).to_dict("records"):
        if r["url"] == article.get("url") or r["_tk"] == title_key(article.get("title")):
            continue
        other = set(r["kw_list"]) | set(r["ent_list"])
        if other:
            j = len(base & other) / len(base | other)
            if j > 0.12:
                scored.append((j, r))
    return [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)[:n]]


def _chunks(text, size=450):
    parts, cur = [], ""
    for piece in re.split(r"(?<=[.!?\n])\s*", text):
        if len(cur) + len(piece) > size and cur:
            parts.append(cur)
            cur = ""
        cur += piece + " "
    if cur.strip():
        parts.append(cur)
    return [p.strip()[:size] for p in parts if p.strip()]


def _translate_google(text, target):
    r = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    return "".join(seg[0] for seg in r.json()[0] if seg[0])


def _translate_mymemory(text, target):
    out = []
    for part in _chunks(text[:2000]):
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": part, "langpair": f"en|{target}"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if str(data.get("responseStatus")) != "200":
            raise RuntimeError(str(data.get("responseDetails"))[:120])
        out.append(data["responseData"]["translatedText"])
    return " ".join(out)


@st.cache_data(show_spinner=False, ttl=86400)
def _translate_cached(text, target):
    """Tries Google first, then MyMemory. Raises on failure, so failures are never cached."""
    errors = []
    for name, fn in (("Google", _translate_google), ("MyMemory", _translate_mymemory)):
        try:
            out = fn(text[:4500], target)
            if out and out.strip():
                return out
            errors.append(f"{name}: empty answer")
        except Exception as error:
            errors.append(f"{name}: {type(error).__name__}: {str(error)[:150]}")
    raise RuntimeError(" | ".join(errors))


def translate_text(text, target):
    try:
        st.session_state.pop("translate_error", None)
        return _translate_cached(text, target)
    except Exception as error:
        st.session_state["translate_error"] = str(error)
        return ""


def translation_error_text():
    detail = st.session_state.get("translate_error", "")
    return "Translation unavailable. " + (f"Details: {detail}" if detail else "Please try again.")


# ==========================================================
# 5. EXTRA PUBLISHER FEEDS (RSS) AND REFRESH
# ==========================================================

def _local(tag):
    return tag.split("}")[-1].lower()


def parse_feed(data):
    """Reads RSS 2.0, RSS 1.0 (RDF) and Atom feeds."""
    items = []
    for el in ET.fromstring(data).iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        r = {"title": "", "url": "", "desc": "", "date": "", "image": ""}
        for ch in el:
            name, text = _local(ch.tag), (ch.text or "")
            if name == "title":
                r["title"] = clean_text(text)
            elif name == "link":
                r["url"] = (ch.get("href") or text).strip() or r["url"]
            elif name in ("description", "summary", "encoded", "content") and ch.text and not r["desc"]:
                r["desc"] = clean_text(text)[:700]
            elif name in ("pubdate", "published", "updated", "date") and not r["date"]:
                r["date"] = text.strip()
            if name in ("thumbnail", "content", "enclosure") and ch.get("url") and not r["image"]:
                if name != "enclosure" or "image" in (ch.get("type") or ""):
                    r["image"] = ch.get("url")
        if r["title"] and r["url"]:
            items.append(r)
    return items


def _pull_feed(feed):
    publisher, url, category, country, language = feed
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (NewsArticleIntelligenceSystem)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return feed, parse_feed(resp.read()), None
    except Exception as error:
        return feed, [], str(error)[:70]


def collect_extra_feeds():
    """Adds fresh articles from extra publishers to your existing news table (duplicates skipped)."""
    table = get_news_table()
    if table is None:
        return 0, [{"Source": "Extra publishers", "Fetched": 0, "New": 0,
                    "Status": "Skipped (news table not created yet)"}]
    ensure_news_columns()
    with db() as conn:
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        cols = [r[1] for r in info]
        if "title" not in cols or "url" not in cols:
            return 0, [{"Source": "Extra publishers", "Fetched": 0, "New": 0, "Status": "Skipped (no title/url column)"}]
        urls = {r[0] for r in conn.execute(f'SELECT url FROM "{table}"')}
        titles = {title_key(r[0]) for r in conn.execute(f'SELECT title FROM "{table}"')}
    id_info = next((r for r in info if r[1] == "id"), None)
    id_is_int = bool(id_info) and "INT" in (id_info[2] or "").upper()

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(_pull_feed, EXTRA_FEEDS))

    report, total_added = [], 0
    for (publisher, _, category, country, language), items, error in results:
        batch = []
        for it in items:
            tk = title_key(it["title"])
            if it["url"] in urls or tk in titles:
                continue
            urls.add(it["url"])
            titles.add(tk)
            text = f"{it['title']}. {it['desc']}"
            label, _ = existing_sentiment("", text)
            published = to_dt(it["date"])
            published = published if not pd.isna(published) else pd.Timestamp.now(tz="UTC")
            row = {
                "title": it["title"], "description": it["desc"], "content": it["desc"],
                "source": publisher, "url": it["url"], "image_url": it["image"],
                "published_date": min(published, pd.Timestamp.now(tz="UTC")).isoformat(),
                "category": category, "summary": summarize(it["title"], it["desc"]),
                "keywords": json.dumps(extract_keywords(text)), "entities": json.dumps(extract_entities(text)),
                "sentiment": label, "source_country": country, "language": language,
            }
            if id_info and not id_is_int:
                row["id"] = hashlib.sha1(it["url"].encode()).hexdigest()
            batch.append(row)
        added = 0
        if batch:
            with db() as conn:
                for row in batch:
                    use = [c for c in cols if c in row]
                    try:
                        added += conn.execute(
                            f'INSERT INTO "{table}" ({",".join(chr(34) + c + chr(34) for c in use)}) '
                            f'VALUES ({",".join("?" * len(use))})', [row[c] for c in use]).rowcount
                    except sqlite3.Error:
                        continue
        total_added += added
        report.append({"Source": f"{publisher} · {category}", "Fetched": len(items), "New": added,
                       "Status": "OK" if not error else f"Failed: {error}"})
    return total_added, report


def refresh_news(include_extra=True):
    report, total, any_ok = [], None, False
    try:
        total = process_all_news()
        any_ok = True
        report.append({"Source": "Core news pipeline (process_all_news)", "Fetched": "-",
                       "New": "-", "Status": f"OK · {total} articles in database"})
    except Exception as error:
        report.append({"Source": "Core news pipeline (process_all_news)", "Fetched": "-",
                       "New": "-", "Status": f"Failed: {str(error)[:90]}"})
    added = 0
    if include_extra:
        try:
            added, extra = collect_extra_feeds()
            report += extra
            any_ok = any_ok or added > 0 or any(r["Status"] == "OK" for r in extra)
        except Exception as error:
            report.append({"Source": "Extra publishers", "Fetched": 0, "New": 0, "Status": f"Failed: {str(error)[:90]}"})
    ensure_news_columns()
    if any_ok:
        set_meta("last_refresh", datetime.now(timezone.utc).isoformat())
    return {"total": total, "extra_added": added, "report": report, "ok": any_ok}


# ==========================================================
# 5B. RELIABLE WORLDWIDE SEARCH (GDELT + AUTOMATIC BACKUPS)
# ==========================================================
# Why the old search often showed "No articles found":
#   * GDELT allows only ONE request every 5 seconds. When it is exceeded it answers with a
#     plain-text message instead of JSON, which the old code treated as "no articles".
#   * GDELT returns articles in every language, so results could be off-topic or unreadable.
# This section fixes both. The search tries, in order:
#   1. GDELT (English sources first, with the 5-second rule respected and automatic retry)
#   2. your original search_global_news() function
#   3. Google News RSS (backup, no key needed)
#   4. Bing News RSS (backup, no key needed)
#   5. GDELT in all languages
# The first one that returns articles is used, so any topic gives results immediately.

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
SEARCH_HEADERS = {"User-Agent": "Mozilla/5.0 (NewsArticleIntelligenceSystem)"}
_GDELT_LAST_CALL = [0.0]


def _timespan_days(timespan):
    try:
        return max(1, int(str(timespan).lower().rstrip("d")))
    except ValueError:
        return 7


def _clean_query(query):
    text = re.sub(r"[^\w\s'\-]", " ", str(query), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip() or str(query).strip()


def _records(results):
    if isinstance(results, pd.DataFrame):
        return results.to_dict("records")
    return list(results or [])


def _blank_article(title, url, source, published, image="", description="", country="", language=""):
    return {
        "title": title, "description": description, "content": description,
        "source": source, "url": url, "image_url": image,
        "published_date": published, "category": "Search result", "summary": "",
        "keywords": "", "entities": "", "sentiment": "",
        "source_country": country, "language": language,
    }


def _gdelt_direct(query, max_records, timespan, english_only):
    """Calls the GDELT DOC API directly and respects its one-request-per-5-seconds rule."""
    gdelt_query = _clean_query(query) + (" sourcelang:english" if english_only else "")
    params = {
        "query": gdelt_query, "mode": "artlist", "format": "json", "sort": "datedesc",
        "maxrecords": int(max_records), "timespan": str(timespan),
    }
    last_message = ""
    for _ in range(3):
        wait = 5.3 - (time.time() - _GDELT_LAST_CALL[0])
        if wait > 0:
            time.sleep(wait)
        _GDELT_LAST_CALL[0] = time.time()
        response = requests.get(GDELT_DOC_API, params=params, headers=SEARCH_HEADERS, timeout=25)
        body = response.text.strip()
        if body.startswith("{"):
            try:
                data = response.json()
            except ValueError:
                data = {}
            found = []
            for a in data.get("articles") or []:
                try:
                    published = datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(
                        tzinfo=timezone.utc).isoformat()
                except ValueError:
                    published = datetime.now(timezone.utc).isoformat()
                title = clean_text(a.get("title", ""))
                url = a.get("url", "")
                if title and url:
                    found.append(_blank_article(
                        title, url, a.get("domain") or "GDELT", published,
                        image=a.get("socialimage", ""),
                        country=a.get("sourcecountry", ""), language=a.get("language", "")))
            return found
        last_message = body[:150]
        if "limit" not in body.lower():
            break  # a real query problem (not the rate limit), retrying will not help
    raise RuntimeError(last_message or "GDELT did not return data")


def _news_rss(url, max_records, source_default, split_publisher):
    """Reads a news-search RSS feed (Google News or Bing News) with the app's own feed parser."""
    response = requests.get(url, headers=SEARCH_HEADERS, timeout=20)
    response.raise_for_status()
    found = []
    for it in parse_feed(response.content)[:max_records]:
        title, source = it["title"], source_default
        if split_publisher and " - " in title:
            title, source = title.rsplit(" - ", 1)
        published = to_dt(it["date"])
        published = published if not pd.isna(published) else pd.Timestamp.now(tz="UTC")
        found.append(_blank_article(
            title.strip(), it["url"], source.strip() or source_default,
            min(published, pd.Timestamp.now(tz="UTC")).isoformat(),
            image=it["image"], description="", language="English"))
    return found


def _google_news(query, max_records, timespan):
    q = urllib.parse.quote_plus(f"{_clean_query(query)} when:{_timespan_days(timespan)}d")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    return _news_rss(url, max_records, "Google News", True)


def _bing_news(query, max_records, timespan):
    q = urllib.parse.quote_plus(_clean_query(query))
    return _news_rss(f"https://www.bing.com/news/search?q={q}&format=rss", max_records, "Bing News", False)


def robust_global_search(query, max_records=25, timespan="7d"):
    """Returns (articles, where_they_came_from, list_of_problems). Never raises."""
    problems = []
    max_records = int(max_records)
    steps = [
        ("GDELT (English sources)", lambda: _gdelt_direct(query, max_records, timespan, True)),
        ("GDELT (your search_global_news function)",
         lambda: _records(search_global_news(query, max_records=max_records, timespan=timespan))),
        ("Google News", lambda: _google_news(query, max_records, timespan)),
        ("Bing News", lambda: _bing_news(query, max_records, timespan)),
        ("GDELT (all languages)", lambda: _gdelt_direct(query, max_records, timespan, False)),
    ]
    for name, run in steps:
        try:
            found = run()
            if name.startswith("GDELT (your"):
                _GDELT_LAST_CALL[0] = time.time()
            if found:
                return found[:max_records], name, problems
            problems.append(f"{name}: no articles for this topic")
        except Exception as error:
            problems.append(f"{name}: {type(error).__name__}: {str(error)[:120]}")
    return [], "", problems


# ==========================================================
# 6. DISPLAY COMPONENTS
# ==========================================================

def display_article(article, key, index=None, pool=None):
    title = safe_text(article.get("title"), "Untitled article")
    url = safe_text(article.get("url"), "")
    uid = f"{key}_{hashlib.md5((url or title).encode()).hexdigest()[:8]}"

    with st.container(border=True):
        st.markdown(f"### {index}. {title}" if index is not None else f"### {title}")

        image_url = safe_text(article.get("image_url"), "")
        if image_url.startswith(("https://", "http://")):
            try:
                st.image(image_url, width=380)
            except Exception:
                pass

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Publisher:**", safe_text(article.get("source")))
            st.write("**Country:**", safe_text(article.get("source_country")))
            st.write("**Topic:**", safe_text(article.get("category"), "General"))
        with col2:
            st.write("**Language:**", safe_text(article.get("language")))
            st.write("**Published:**", fmt_time(article.get("published_dt")))
            st.write("**Sentiment:**", BADGE.get(article.get("label"), "🟡 Neutral"))

        summary = safe_text(article.get("summary_text"), "")
        if summary and summary != title:
            st.write("**Summary:**", summary)
        points = key_points(safe_text(article.get("description"), "") or safe_text(article.get("content"), ""))
        if points:
            st.write("**Important points:**")
            for p in points:
                st.markdown(f"- {p}")
        kws, ents = article.get("kw_list") or [], article.get("ent_list") or []
        if kws:
            st.caption("🔑 Keywords: " + ", ".join(map(str, kws)))
        if ents:
            st.caption("🏢 Entities: " + ", ".join(map(str, ents)))

        b1, b2, b3 = st.columns(3)
        with b1:
            if url.startswith(("https://", "http://")):
                st.link_button("Read Original Article ↗", url, use_container_width=True)
        with b2:
            if url:
                saved = is_saved(url)
                if st.button("★ Saved — click to remove" if saved else "☆ Save Article",
                             key=f"save_{uid}", use_container_width=True):
                    unsave_article(url) if saved else save_article(article)
                    st.rerun()
        with b3:
            if st.button("✔ Mark as read", key=f"read_{uid}", use_container_width=True):
                mark_read(article)
                st.toast("Added to your reading history")

        with st.expander("🌐 Translate  ·  🔗 Related reports"):
            t1, t2 = st.columns(2)
            with t1:
                lang = st.selectbox("Translate to", list(LANGS), index=1, key=f"lang_{uid}")
                if st.button("Translate", key=f"tr_{uid}"):
                    out = translate_text(f"{title}\n\n{summary}", LANGS[lang])
                    st.write(out or translation_error_text())
            with t2:
                st.write("")
                if st.button("Find related reports", key=f"rel_{uid}"):
                    related = related_articles(article, pool if pool is not None else pd.DataFrame())
                    if not related:
                        st.write("No closely related reports found yet.")
                    for r in related:
                        st.markdown(f"- [{r['title']}]({r['url']}) — {r['source']}, {ago(r['published_dt'])}")


def show_articles(df, prefix, pool, start=1):
    for i, article in enumerate(df.to_dict("records"), start=start):
        display_article(article, f"{prefix}{i}", i, pool)


def paginate(total, size, key):
    pages = max(1, -(-total // size))
    if pages == 1:
        return 0
    page = st.number_input(f"Page (1–{pages})", 1, pages, 1, key=key)
    return (int(page) - 1) * size


def export_csv(df, filename, key):
    if df.empty:
        return
    cols = ["title", "source", "source_country", "language", "category", "published_date", "label", "summary_text", "url"]
    st.download_button("⬇ Download results as CSV", df[cols].to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv", key=key)


def options(df, col):
    return ["All"] + (sorted(x for x in df[col].unique() if x and x != "Unknown") if not df.empty else [])


def show_refresh_report(result):
    if result["ok"]:
        st.success("News update completed successfully! "
                   f"Total articles in database: {result['total'] if result['total'] is not None else 'updated'}"
                   f" · New articles from extra publishers: {result['extra_added']}")
    else:
        st.warning("The update could not collect news. Please check your internet connection and try again.")
    with st.expander("Source report"):
        st.dataframe(pd.DataFrame(result["report"]), use_container_width=True, hide_index=True)


# ==========================================================
# UI START
# ==========================================================

init_tables()


# ==========================================================
# 7. SIDEBAR
# ==========================================================

st.sidebar.title("🌍 News Intelligence")
st.sidebar.caption("Explore worldwide news and understand important events.")

page = st.sidebar.radio("Navigation", PAGES)

st.sidebar.checkbox("Auto-refresh when the app opens (if older than 30 min)", value=True, key="auto_refresh")
st.sidebar.checkbox("Include extra publishers (Al Jazeera, DW, The Hindu, NDTV…)", value=True, key="extra_sources")

_last = to_dt(get_meta("last_refresh"))
st.sidebar.caption("Last update: " + (ago(_last) if not pd.isna(_last) else "never"))
st.sidebar.divider()
st.sidebar.caption("News Article Intelligence System")


# ==========================================================
# 8. MAIN HEADER + REFRESH LATEST NEWS
# ==========================================================

st.markdown('<div class="main-title">🌍 News Article Intelligence System</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Discover, explore and understand news from around the world.</div>',
            unsafe_allow_html=True)
st.divider()

# Automatic refresh once per browser session when the data is old
if "booted" not in st.session_state:
    st.session_state["booted"] = True
    if st.session_state.get("auto_refresh", True) and (pd.isna(_last) or
                                                       pd.Timestamp.now(tz="UTC") - _last > pd.Timedelta(minutes=30)):
        with st.spinner("Collecting the latest worldwide news. Please wait..."):
            st.session_state["refresh_result"] = refresh_news(st.session_state.get("extra_sources", True))
        st.rerun()

st.subheader("🔄 Update Worldwide News")
st.write("Click below to collect the latest news and update article summaries, keywords and sentiment analysis.")

if st.button("🔄 Refresh Latest News", use_container_width=True, type="primary"):
    try:
        with st.spinner("Collecting latest news and processing articles. Please wait..."):
            st.session_state["refresh_result"] = refresh_news(st.session_state.get("extra_sources", True))
        st.rerun()
    except Exception as error:
        st.error(f"Unable to refresh news: {error}")

if st.session_state.get("refresh_result"):
    show_refresh_report(st.session_state.pop("refresh_result"))

df = load_news()
NOW = pd.Timestamp.now(tz="UTC")


# ==========================================================
# 9. DASHBOARD
# ==========================================================

if page == "Dashboard":

    st.subheader("📊 News Dashboard")

    c = st.columns(6)
    c[0].metric("Total Articles", len(df))
    c[1].metric("News Sources", df["source"].nunique() if not df.empty else 0)
    c[2].metric("Categories", df["category"].replace("", pd.NA).dropna().nunique() if not df.empty else 0)
    c[3].metric("Countries", df.loc[df["source_country"] != "Unknown", "source_country"].nunique() if not df.empty else 0)
    c[4].metric("Last 24 hours", int((df["published_dt"] >= NOW - pd.Timedelta(hours=24)).sum()) if not df.empty else 0)
    c[5].metric("Saved Articles", len(load_bookmarks()))

    st.divider()

    if not df.empty:
        mood = df.head(300)["label"].value_counts()
        st.caption("Mood of the 300 most recent articles:  " + "  ·  ".join(f"{BADGE[k]} {v}" for k, v in mood.items()))
        trend, ref = trending_topics(df)
        if not trend.empty:
            st.markdown("**🔥 Trending now:** " + "  ·  ".join(f"`{t}`" for t in trend["Topic"].head(8)))

        st.subheader("📰 Recently Collected News")
        show_articles(df.head(8), "dash", df)
    else:
        st.info("No news articles were found in the database. Click **Refresh Latest News** (internet required).")


# ==========================================================
# 10. GLOBAL NEWS SEARCH
# ==========================================================

elif page == "Global News Search":

    st.subheader("🌎 Search Global News")
    st.write("Search for news topics and discover articles from international publishers.")

    tab_world, tab_archive = st.tabs(["🌎 Worldwide search (GDELT)", "🗂 Search collected archive"])

    with tab_world:
        with st.form("global_search_form"):
            query = st.text_input("Enter any news topic",
                                  placeholder="Example: Artificial Intelligence, Cricket, Climate Change")
            f1, f2 = st.columns(2)
            timespan = f1.selectbox("Time range", ["1d", "3d", "7d", "14d", "30d"], index=2,
                                    format_func=lambda x: {"1d": "Last 24 hours", "3d": "Last 3 days", "7d": "Last 7 days",
                                                           "14d": "Last 14 days", "30d": "Last 30 days"}[x])
            max_records = f2.selectbox("Number of articles", [25, 50, 100], index=0)
            submitted = st.form_submit_button("🔍 Search Worldwide", use_container_width=True)

        if submitted:
            if not query.strip():
                st.warning("Please enter a news topic.")
            else:
                with st.spinner("Searching worldwide news. Please wait..."):
                    try:
                        results, via, problems = robust_global_search(
                            query.strip(), max_records=max_records, timespan=timespan)
                        st.session_state["global_results"] = prepare_external(results)
                        st.session_state["global_query"] = query.strip()
                        st.session_state["global_via"] = via
                        st.session_state["global_problems"] = problems
                    except Exception as error:
                        st.session_state["global_results"] = pd.DataFrame()
                        st.session_state["global_query"] = query.strip()
                        st.session_state["global_via"] = ""
                        st.session_state["global_problems"] = [f"Unexpected error: {error}"]
                        st.error(f"Global search error: {error}")

        if "global_results" in st.session_state:
            gdf = st.session_state["global_results"]
            st.divider()
            st.subheader(f"Results for: {st.session_state.get('global_query', '')}")
            if not gdf.empty:
                if st.session_state.get("global_via"):
                    st.caption(f"Results provided by: {st.session_state['global_via']}")
                g1, g2, g3, g4 = st.columns(4)
                sel_country = g1.selectbox("Filter by country", options(gdf, "source_country"), key="g_country")
                sel_lang = g2.selectbox("Filter by language", options(gdf, "language"), key="g_lang")
                sel_pub = g3.selectbox("Filter by publisher", options(gdf, "source"), key="g_pub")
                sel_mood = g4.selectbox("Filter by sentiment", ["All", "Positive", "Neutral", "Negative"], key="g_mood")
                shown = apply_filters(gdf, country=sel_country, language=sel_lang, publisher=sel_pub, label=sel_mood)
                st.success(f"Found {len(gdf)} articles. Showing {len(shown)} articles.")
                off = paginate(len(shown), 10, "g_page")
                show_articles(shown.iloc[off:off + 10], "glob", df, start=off + 1)
                export_csv(shown, "global_news_results.csv", "g_csv")
            else:
                st.warning("No articles found. Try a different topic or search again later.")
                st.caption("Global news availability depends on the articles indexed by GDELT.")
                if st.session_state.get("global_problems"):
                    with st.expander("Technical details (why nothing was found)"):
                        for problem in st.session_state["global_problems"]:
                            st.write("- " + problem)

    with tab_archive:
        if df.empty:
            st.info("The archive is empty. Click **Refresh Latest News** first.")
        else:
            a1, a2, a3 = st.columns([3, 1, 1])
            q = a1.text_input("Search title, summary, keywords, entities or publisher", key="a_q")
            rng = a2.selectbox("Time range", ["All time", "Last 24 hours", "Last 7 days", "Last 30 days"], key="a_rng")
            sort = a3.selectbox("Sort by", ["Newest first", "Oldest first", "Most positive", "Most negative"], key="a_sort")
            a4, a5, a6, a7, a8 = st.columns(5)
            cat = a4.selectbox("Topic", options(df, "category"), key="a_cat")
            ctry = a5.selectbox("Country", options(df, "source_country"), key="a_ctry")
            lng = a6.selectbox("Language", options(df, "language"), key="a_lng")
            pub = a7.selectbox("Publisher", options(df, "source"), key="a_pub")
            mood = a8.selectbox("Sentiment", ["All", "Positive", "Neutral", "Negative"], key="a_mood")
            days = {"All time": None, "Last 24 hours": 1, "Last 7 days": 7, "Last 30 days": 30}[rng]
            res = apply_filters(df, q, cat, ctry, lng, pub, mood, days)
            if sort == "Oldest first":
                res = res.sort_values("published_dt", na_position="last")
            elif sort == "Most positive":
                res = res.sort_values("score", ascending=False)
            elif sort == "Most negative":
                res = res.sort_values("score")
            st.write(f"**{len(res)}** articles found")
            off = paginate(len(res), 10, "a_page")
            show_articles(res.iloc[off:off + 10], "arch", df, start=off + 1)
            export_csv(res, "news_archive_results.csv", "a_csv")


# ==========================================================
# 11. LATEST NEWS
# ==========================================================

elif page == "Latest News":

    st.subheader("📰 Latest Collected News")

    if not df.empty:
        l1, l2, l3 = st.columns([3, 1, 1])
        search_text = l1.text_input("Search collected articles", placeholder="Search title, publisher or topic")
        selected_category = l2.selectbox("Select news category", options(df, "category"))
        selected_mood = l3.selectbox("Sentiment", ["All", "Positive", "Neutral", "Negative"])

        filtered_df = apply_filters(df, search_text, selected_category, label=selected_mood)
        st.write(f"Articles available: {len(filtered_df)}  ·  sorted by publication date (newest first)")
        off = paginate(len(filtered_df), 10, "latest_page")
        show_articles(filtered_df.iloc[off:off + 10], "latest", df, start=off + 1)
    else:
        st.info("No collected news articles are available.")


# ==========================================================
# 12. TRENDING TOPICS
# ==========================================================

elif page == "Trending Topics":

    st.subheader("🔥 Trending Topics")

    if df.empty:
        st.info("Collect news articles to see trending topics.")
    else:
        hours = st.select_slider("Compare the latest … with the period before it", [6, 12, 24, 48, 72], value=24,
                                 format_func=lambda h: f"{h} hours")
        left, right = st.columns(2)
        ref_shown = None
        for col, field, title in [(left, "kw_list", "Keywords"), (right, "ent_list", "People, places & organisations")]:
            with col:
                st.markdown(f"**{title}**")
                trend, ref_shown = trending_topics(df, field, hours)
                if trend.empty:
                    st.info("Not enough articles in this window.")
                else:
                    st.bar_chart(trend.head(15).set_index("Topic")["Now"])
                    rising = trend[trend["Momentum"] > 1].sort_values("Momentum", ascending=False).head(5)
                    if not rising.empty:
                        st.caption("📈 Rising fast: " + ", ".join(rising["Topic"]))
        if ref_shown is not None:
            st.caption(f"Window ends at the newest article: {fmt_time(ref_shown)}")

        topic = st.text_input("Open a topic to see its coverage", placeholder="Type a keyword from the charts")
        if topic.strip():
            res = apply_filters(df, topic)
            st.write(f"{len(res)} articles mention **{topic}**")
            show_articles(res.head(8), "trend", df)


# ==========================================================
# 13. DAILY DIGEST
# ==========================================================

elif page == "Daily Digest":

    st.subheader("📰 Daily Digest")

    if df.empty:
        st.info("Collect news articles to build your digest.")
    else:
        cats = sorted(c for c in df["category"].unique() if c)
        saved_topics = [t for t in get_pref("topics", cats[:4]) if t in cats]
        topics = st.multiselect("Topics in your digest", cats, default=saved_topics or cats[:4])
        per_topic = st.slider("Stories per topic", 2, 8, 4)
        lines = ["NEWS ARTICLE INTELLIGENCE SYSTEM - DAILY DIGEST", ""]
        for topic in topics:
            part = df[df["category"] == topic].head(per_topic)
            st.markdown(f"### {topic}")
            lines.append(topic.upper())
            for a in part.to_dict("records"):
                st.markdown(f"- **[{a['title']}]({a['url']})** — {a['source']}, {ago(a['published_dt'])} · "
                            f"{BADGE[a['label']]}  \n  {a['summary_text']}")
                lines.append(f"- {a['title']} ({a['source']})\n  {a['url']}")
            lines.append("")
        if topics:
            st.download_button("⬇ Download digest (text)", "\n".join(lines).encode("utf-8"),
                               file_name="daily_digest.txt")


# ==========================================================
# 14. MULTILINGUAL READER
# ==========================================================

elif page == "Multilingual Reader":

    st.subheader("🌐 Multilingual Reader")
    st.write("Translate summaries and understand international news in your own language.")

    lang = st.selectbox("Read in", list(LANGS), index=1)
    tab_a, tab_b = st.tabs(["Translate an article", "Translate any text"])

    with tab_a:
        if df.empty:
            st.info("No articles yet. Refresh the news first.")
        else:
            pool = df.head(80).reset_index(drop=True)
            pick = st.selectbox("Choose an article", range(len(pool)),
                                format_func=lambda i: f"{pool.loc[i, 'title'][:90]} — {pool.loc[i, 'source']}")
            a = pool.loc[pick]
            text = f"{a['title']}\n\n{a['summary_text']}"
            c1, c2 = st.columns(2)
            c1.markdown("**Original**")
            c1.write(text)
            c2.markdown(f"**{lang}**")
            c2.write(translate_text(text, LANGS[lang]) or translation_error_text())
            if a["url"].startswith(("https://", "http://")):
                st.link_button("Read the full original article ↗", a["url"])

    with tab_b:
        custom = st.text_area("Paste any news text", height=160)
        if st.button("Translate text") and custom.strip():
            st.write(translate_text(custom.strip(), LANGS[lang]) or translation_error_text())


# ==========================================================
# 15. SAVED ARTICLES
# ==========================================================

elif page == "Saved Articles":

    st.subheader("⭐ Your Saved Articles")

    bookmarks = load_bookmarks()

    if not bookmarks.empty:
        st.success(f"You have saved {len(bookmarks)} articles.")
        for _, article in bookmarks.iterrows():
            with st.container(border=True):
                st.markdown(f"### {safe_text(article['title'])}")
                st.write("**Publisher:**", safe_text(article["source"]))
                st.write("**Published:**", fmt_time(to_dt(article["published_date"])))

                image_url = safe_text(article["image_url"], "")
                if image_url.startswith(("https://", "http://")):
                    try:
                        st.image(image_url, width=380)
                    except Exception:
                        pass

                b1, b2 = st.columns(2)
                url = safe_text(article["url"], "")
                if url.startswith(("https://", "http://")):
                    b1.link_button("Read Article ↗", url, use_container_width=True)
                if b2.button("Remove Bookmark", key=f"remove_{article['id']}", use_container_width=True):
                    with db() as conn:
                        conn.execute("DELETE FROM saved_articles WHERE id=?", (int(article["id"]),))
                    st.rerun()
        st.download_button("⬇ Download saved articles (CSV)",
                           bookmarks.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
                           file_name="saved_articles.csv", mime="text/csv")
    else:
        st.info("You have not saved any articles yet. Use the Save Article button in the news sections.")


# ==========================================================
# 16. NEWS ANALYTICS
# ==========================================================

elif page == "News Analytics":

    st.subheader("📈 News Analytics Dashboard")

    if df.empty:
        st.info("Collect news articles to view analytics.")
    else:
        period = st.select_slider("Period", ["Last 3 days", "Last 7 days", "Last 14 days", "Last 30 days", "All time"],
                                  value="All time")
        days = {"Last 3 days": 3, "Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "All time": None}[period]
        a = apply_filters(df, days=days)

        if a.empty:
            st.info("No articles in this period. Try a longer period or refresh the news.")
        else:
            m = st.columns(4)
            m[0].metric("Articles analysed", len(a))
            m[1].metric("Average sentiment", f"{a['score'].mean():+.2f}")
            m[2].metric("Most active publisher", a["source"].value_counts().index[0])
            m[3].metric("Most covered country", a.loc[a["source_country"] != "Unknown", "source_country"].value_counts().index[0]
                        if (a["source_country"] != "Unknown").any() else "Unknown")

            dated = a.dropna(subset=["published_dt"]).copy()
            dated["day"] = dated["published_dt"].dt.date

            st.markdown("### News by Category")
            cats = a["category"].replace("", "Unknown").value_counts()
            st.bar_chart(cats)

            st.markdown("### Top 10 News Publishers")
            st.bar_chart(a["source"].value_counts().head(10))

            st.markdown("### Sentiment Distribution")
            st.bar_chart(a["label"].value_counts())

            if not dated.empty:
                c1, c2 = st.columns(2)
                c1.markdown("### Articles by Publication Date")
                c1.line_chart(dated.groupby("day").size())
                c2.markdown("### Sentiment Trend (average per day)")
                c2.line_chart(dated.groupby("day")["score"].mean())

            c3, c4 = st.columns(2)
            c3.markdown("### Sentiment by Topic")
            c3.bar_chart(pd.crosstab(a["category"].replace("", "Unknown"), a["label"]))
            c4.markdown("### Coverage by Country (top 15)")
            c4.bar_chart(a.loc[a["source_country"] != "Unknown", "source_country"].value_counts().head(15))

            st.markdown("### Source Comparison")
            comp = a.groupby("source").agg(
                Articles=("title", "count"),
                Average_sentiment=("score", "mean"),
                Positive=("label", lambda s: int((s == "Positive").sum())),
                Neutral=("label", lambda s: int((s == "Neutral").sum())),
                Negative=("label", lambda s: int((s == "Negative").sum())),
            ).sort_values("Articles", ascending=False).round(2)
            st.dataframe(comp, use_container_width=True)

            st.markdown("### Top Keywords")
            kw = Counter(k for ks in a["kw_list"] for k in set(ks))
            if kw:
                st.bar_chart(pd.Series(dict(kw.most_common(15))))

            st.caption("Sentiment and keywords use a simple rule-based method. Treat them as indicators, not verdicts.")


# ==========================================================
# 17. MY NEWS SPACE
# ==========================================================

elif page == "My News Space":

    st.subheader("👤 My News Space")

    cats = sorted(c for c in df["category"].unique() if c) if not df.empty else []
    st.markdown("### Topic preferences")
    chosen = st.multiselect("Favourite topics (used in the Daily Digest)", cats,
                            default=[t for t in get_pref("topics", cats[:4]) if t in cats])
    if st.button("Save preferences"):
        set_pref("topics", chosen)
        st.success("Preferences saved.")

    st.markdown("### 🕘 Reading history")
    history = load_history()
    if history.empty:
        st.info("Nothing read yet. Use **✔ Mark as read** on any article.")
    else:
        for _, h in history.iterrows():
            link = safe_text(h["url"], "")
            title = safe_text(h["title"])
            st.markdown(f"- [{title}]({link}) — {safe_text(h['source'])} · read {ago(to_dt(h['read_at']))}"
                        if link else f"- {title} — {safe_text(h['source'])}")

    st.divider()
    if st.button("Clear saved articles, reading history and preferences"):
        clear_personal_data()
        st.success("Your personal data has been cleared.")
        st.rerun()


# ==========================================================
# 18. FOOTER
# ==========================================================

st.divider()

st.caption("🌍 News Article Intelligence System | Powered by Python, Streamlit, SQLite, NLP and GDELT.")
st.caption("News articles belong to their respective publishers. "
           "Always consult the original publisher for the complete report.")
