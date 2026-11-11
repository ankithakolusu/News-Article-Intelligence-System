from textblob import TextBlob


def analyze_sentiment(text):

    # Create TextBlob object
    analysis = TextBlob(text)

    # Get polarity value
    polarity = analysis.sentiment.polarity

    # Determine sentiment
    if polarity > 0:
        sentiment = "Positive"
    elif polarity < 0:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    return sentiment, polarity