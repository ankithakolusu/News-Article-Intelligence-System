import sqlite3


DATABASE = "data/news.db"


connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()


cursor.execute("""
    SELECT id, title, summary, keywords, entities, sentiment
    FROM news
    LIMIT 3
""")


articles = cursor.fetchall()


for article in articles:

    print("\n========================================")
    print("Article ID:", article[0])
    print("Title:", article[1])

    print("\nSummary:")
    print(article[2])

    print("\nKeywords:")
    print(article[3])

    print("\nEntities:")
    print(article[4])

    print("\nSentiment:")
    print(article[5])


connection.close()