from modules.sentiment import analyze_sentiment


articles = [
    "The new technology is excellent and has greatly improved people's lives.",
    "The company suffered a major loss and the situation is very disappointing.",
    "The company announced a new product today."
]


for article in articles:

    sentiment, polarity = analyze_sentiment(article)

    print("Article:", article)
    print("Sentiment:", sentiment)
    print("Polarity:", polarity)
    print()