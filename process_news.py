
import sqlite3
import json

from database import create_database, insert_article, get_article_count
from modules.news_collector import collect_news

from modules.summarizer import summarize_text
from modules.keywords import extract_keywords
from modules.entities import extract_entities
from modules.sentiment import analyze_sentiment


DATABASE = "data/news.db"


def collect_and_save_news():

    print("\nStarting real news collection...")

    articles = collect_news()

    print("\nArticles collected:", len(articles))

    for article in articles:
        insert_article(article)

    print("News collection completed!")

    print("Total articles in database:", get_article_count())


def process_articles():

    connection = sqlite3.connect(DATABASE)

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id, title, description, content
            FROM news
            WHERE summary IS NULL
               OR keywords IS NULL
               OR entities IS NULL
               OR sentiment IS NULL
        """)

        articles = cursor.fetchall()

        print("\nArticles waiting for NLP analysis:", len(articles))

        for article in articles:

            article_id = article[0]
            title = article[1] or ""
            description = article[2] or ""
            content = article[3] or ""

            text = title + ". " + description + ". " + content

            try:
                summary = summarize_text(text, sentence_count=3)

                keywords = extract_keywords(
                    text,
                    number_of_keywords=10
                )

                entities = extract_entities(text)

                sentiment, polarity = analyze_sentiment(text)

                keywords_json = json.dumps(keywords)
                entities_json = json.dumps(entities)

                cursor.execute("""
                    UPDATE news
                    SET summary = ?,
                        keywords = ?,
                        entities = ?,
                        sentiment = ?
                    WHERE id = ?
                """, (
                    summary,
                    keywords_json,
                    entities_json,
                    sentiment,
                    article_id
                ))

                print("Processed:", title)

            except Exception as error:
                print("Error processing article:", title)
                print(error)

        connection.commit()

    finally:
        connection.close()

    print("\nNLP analysis completed!")


def process_all_news():

    create_database()

    collect_and_save_news()

    process_articles()

    total = get_article_count()

    print("\nFinal database article count:", total)

    return total


if __name__ == "__main__":

    process_all_news()
