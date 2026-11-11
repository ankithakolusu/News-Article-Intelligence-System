
from collections import Counter

from modules.news_collector import collect_news
from database import create_database, insert_article, get_article_count


# Create database
create_database()

# Collect news
articles = collect_news()

print("\n================================")
print("NEWS COLLECTION RESULTS")
print("================================")

print("Total articles collected:", len(articles))


# Count articles by publisher
source_count = Counter(
    article["source"] for article in articles
)

print("\nPublisher-wise article count:")

for source, count in source_count.items():
    print(source, ":", count)


# Save articles
for article in articles:
    insert_article(article)

print("\nArticles saved to database!")

# Display database count
print("Total articles in database:", get_article_count())

print("\nNews collection completed!")
