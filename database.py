
import sqlite3
import os

# Database file location
DATABASE = "data/news.db"


# -----------------------------------------
# CREATE DATABASE AND NEWS TABLE
# -----------------------------------------

def create_database():

    os.makedirs("data", exist_ok=True)

    connection = sqlite3.connect(DATABASE)

    try:

        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                content TEXT,
                source TEXT,
                url TEXT UNIQUE,
                published_date TEXT,
                category TEXT,
                image_url TEXT,
                summary TEXT,
                keywords TEXT,
                entities TEXT,
                sentiment TEXT
            )
        """)

        connection.commit()

    finally:
        connection.close()


# -----------------------------------------
# ADD IMAGE COLUMN TO EXISTING DATABASE
# -----------------------------------------

def add_image_column():

    connection = sqlite3.connect(DATABASE)

    try:

        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(news)")

        columns = [
            column[1]
            for column in cursor.fetchall()
        ]

        if "image_url" not in columns:

            cursor.execute("""
                ALTER TABLE news
                ADD COLUMN image_url TEXT
            """)

            connection.commit()

            print("Image column added successfully!")

        else:

            print("Image column already exists!")

    finally:
        connection.close()


# -----------------------------------------
# INSERT NEWS ARTICLE
# -----------------------------------------

def insert_article(article):

    connection = sqlite3.connect(DATABASE)

    try:

        cursor = connection.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO news
            (
                title,
                description,
                content,
                source,
                url,
                published_date,
                category,
                image_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article.get("title", ""),
            article.get("description", ""),
            article.get("content", ""),
            article.get("source", ""),
            article.get("url", ""),
            article.get("published_date", ""),
            article.get("category", ""),
            article.get("image_url")
        ))

        connection.commit()

    finally:
        connection.close()


# -----------------------------------------
# GET TOTAL ARTICLE COUNT
# -----------------------------------------

def get_article_count():

    connection = sqlite3.connect(DATABASE)

    try:

        cursor = connection.cursor()

        cursor.execute("SELECT COUNT(*) FROM news")

        count = cursor.fetchone()[0]

        return count

    finally:
        connection.close()


# -----------------------------------------
# RUN DATABASE DIRECTLY
# -----------------------------------------

if __name__ == "__main__":

    create_database()

    add_image_column()

    print("Database created successfully!")

    print(
        "Total articles:",
        get_article_count()
    )
