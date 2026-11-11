from modules.entities import extract_entities


article = """
Elon Musk announced a new technology project in California.
Microsoft and Google are developing artificial intelligence systems.
The project will begin in January 2026.
"""


entities = extract_entities(article)

print("Named Entities:")

for entity in entities:
    print("-", entity["text"], "->", entity["label"])