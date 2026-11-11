# 📰 News Article Intelligence System

A Python-based news intelligence system that collects news articles from **GDELT**, stores them in a **SQLite** database, analyzes them with **NLP**, and presents the results in an interactive **Streamlit** dashboard.

## ✨ Features

- **News collection:** fetches news articles from the GDELT project
- **Database storage:** saves articles in SQLite for fast, local access
- **Keyword extraction:** pulls out the most important keywords from each article
- **Entity recognition:** identifies people, organizations and locations mentioned in articles
- **Article similarity:** finds related or duplicate articles using NLP
- **Interactive dashboard:** browse, search and explore results through a Streamlit web app

## 🛠️ Tech Stack

| Area | Tools |
|---|---|
| Language | Python 3 |
| Web app | Streamlit |
| Database | SQLite |
| NLP | Keyword extraction, named entity recognition, text similarity |
| Data source | GDELT |

## 📁 Project Structure

```
News-Article-Intelligence-System/
├── modules/                    # Core modules (collector, entities, keywords, similarity)
├── app.py                      # Streamlit dashboard (main entry point)
├── database.py                 # SQLite database setup and queries
├── process_news.py             # Processes collected articles (NLP pipeline)
├── requirements.txt            # Python dependencies
├── test_article_similarity.py  # Tests for article similarity
├── test_collector.py           # Tests for news collector
├── test_database.py            # Tests for database
├── test_entities.py            # Tests for entity extraction
├── test_keywords.py            # Tests for keyword extraction
└── .gitignore
```

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/ankithakolusu/News-Article-Intelligence-System.git
cd News-Article-Intelligence-System
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> If your NLP library needs a language model (for example spaCy), download it as well, e.g. `python -m spacy download en_core_web_sm`.

### 4. Process the news data

```bash
python process_news.py
```

### 5. Run the app

```bash
streamlit run app.py
```

Then open the local URL shown in your terminal (usually http://localhost:8501).

## 🧪 Running Tests

```bash
python test_database.py
python test_collector.py
python test_keywords.py
python test_entities.py
python test_article_similarity.py
```

If you use pytest, you can run everything at once with `pytest`.
