import re
import nltk

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


# Download required NLTK resources
nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("stopwords")


def clean_text(text):

    # Convert text to lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r"http\S+|www\S+", "", text)

    # Remove special characters and numbers
    text = re.sub(r"[^a-zA-Z\s]", "", text)

    # Tokenize text
    words = word_tokenize(text)

    # Load English stop words
    stop_words = set(stopwords.words("english"))

    # Remove stop words
    words = [
        word for word in words
        if word not in stop_words
    ]

    # Join words back into a sentence
    cleaned_text = " ".join(words)

    return cleaned_text