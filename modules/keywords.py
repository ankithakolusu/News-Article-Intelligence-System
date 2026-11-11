import nltk

from collections import Counter
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


# Download required NLTK resources
nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("stopwords")


def extract_keywords(text, number_of_keywords=10):

    # Convert text to lowercase
    text = text.lower()

    # Tokenize the text
    words = word_tokenize(text)

    # Get English stop words
    stop_words = set(stopwords.words("english"))

    # Keep only meaningful words
    meaningful_words = [
        word for word in words
        if word.isalpha() and word not in stop_words
    ]

    # Count word frequency
    word_frequency = Counter(meaningful_words)

    # Get most common words
    keywords = word_frequency.most_common(number_of_keywords)

    # Return only the words
    return [word for word, frequency in keywords]