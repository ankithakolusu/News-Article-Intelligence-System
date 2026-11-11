import sqlite3

from modules.similarity import calculate_similarity


DATABASE = "data/news.db"


# Connect to database
connection = sqlite3.connect(DATABASE)

cursor = connection.cursor()


# Get two news articles
cursor.execute("""
    SELECT title, description
    FROM news
    LIMIT 2
""")


articles = cursor.fetchall()


connection.close()


# Check whether two articles are available
if len(articles) < 2:

    print("Not enough articles in the database.")

else:

    article1 = articles[0][0] + ". " + (articles[0][1] or "")
    article2 = articles[1][0] + ". " + (articles[1][1] or "")


    # Calculate similarity
    similarity = calculate_similarity(
        article1,
        article2
    )


    print("Article 1:")
    print(articles[0][0])

    print("\nArticle 2:")
    print(articles[1][0])

    print("\nSimilarity Score:")
    print(round(similarity, 2))