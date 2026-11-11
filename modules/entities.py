import spacy


# Load English language model
nlp = spacy.load("en_core_web_sm")


def extract_entities(text):

    # Process the text
    doc = nlp(text)

    entities = []

    # Extract named entities
    for ent in doc.ents:

        entities.append({
            "text": ent.text,
            "label": ent.label_
        })

    return entities