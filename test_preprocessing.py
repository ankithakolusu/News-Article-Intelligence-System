from modules.preprocessing import clean_text


text = """
Artificial Intelligence is changing the way people use technology.
It is being used in healthcare, education, business, and many other fields.
Visit https://example.com for more information!
"""


cleaned_text = clean_text(text)

print("Original Text:")
print(text)

print("\nCleaned Text:")
print(cleaned_text)