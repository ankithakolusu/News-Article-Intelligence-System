from modules.similarity import calculate_similarity


article1 = """
Microsoft has launched a new artificial intelligence platform
for businesses and organizations.
"""

article2 = """
Microsoft introduced a new AI platform designed for
businesses and organizations.
"""

article3 = """
The football team won the championship after an exciting match.
"""


similarity1 = calculate_similarity(article1, article2)
similarity2 = calculate_similarity(article1, article3)


print("Similarity between Article 1 and Article 2:")
print(round(similarity1, 2))

print("\nSimilarity between Article 1 and Article 3:")
print(round(similarity2, 2))