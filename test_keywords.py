from modules.keywords import extract_keywords


article = """
Artificial intelligence is transforming healthcare.
Healthcare organizations are using artificial intelligence to help doctors
analyze medical information and improve patient care.
AI technology is also being used for medical research and diagnosis.
"""


keywords = extract_keywords(article, 8)

print("Important Keywords:")

for keyword in keywords:
    print("-", keyword)