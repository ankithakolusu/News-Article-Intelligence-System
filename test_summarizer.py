from modules.summarizer import summarize_text


article = """
Artificial intelligence is becoming an important technology in modern society.
Many companies are using artificial intelligence to improve their products and services.
Healthcare organizations are using AI to help doctors analyze medical information.
Educational institutions are also using AI tools to support students and teachers.
Experts believe that artificial intelligence will continue to influence many industries.
However, organizations must use AI responsibly and protect user information.
"""


summary = summarize_text(article, sentence_count=3)

print("Original Article:")
print(article)

print("\nGenerated Summary:")
print(summary)