from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def calculate_similarity(article1, article2):

    # Store both articles
    articles = [article1, article2]

    # Convert text into TF-IDF vectors
    vectorizer = TfidfVectorizer()

    tfidf_matrix = vectorizer.fit_transform(articles)

    # Calculate cosine similarity
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])

    return similarity[0][0]