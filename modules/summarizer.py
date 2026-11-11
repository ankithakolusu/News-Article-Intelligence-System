import re
from collections import Counter

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize


# Download required NLTK resources
nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("stopwords")


def summarize_text(text, sentence_count=3):

    # Split article into sentences
    sentences = sent_tokenize(text)

    # If the article is already short
    if len(sentences) <= sentence_count:
        return " ".join(sentences)

    # Get English stop words
    stop_words = set(stopwords.words("english"))

    # Calculate word frequencies
    words = word_tokenize(text.lower())

    word_frequencies = Counter(
        word for word in words
        if word.isalpha() and word not in stop_words
    )

    # Calculate scores for each sentence
    sentence_scores = {}

    for sentence in sentences:

        sentence_words = word_tokenize(sentence.lower())

        score = sum(
            word_frequencies.get(word, 0)
            for word in sentence_words
            if word.isalpha() and word not in stop_words
        )

        sentence_scores[sentence] = score

    # Select highest-scoring sentences
    important_sentences = sorted(
        sentence_scores,
        key=sentence_scores.get,
        reverse=True
    )[:sentence_count]

    # Keep the original article order
    summary_sentences = [
        sentence for sentence in sentences
        if sentence in important_sentences
    ]

    return " ".join(summary_sentences)