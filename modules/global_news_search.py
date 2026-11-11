
import requests


GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def search_global_news(query, max_records=25, timespan="7d"):
    """
    Search for real news articles from publishers worldwide
    using the GDELT DOC API.
    """

    if not query or not query.strip():
        print("Please enter a news topic.")
        return []

    params = {
        "query": query.strip(),
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "timespan": timespan,
        "sort": "DateDesc"
    }

    headers = {
        "User-Agent": "GlobalNewsIntelligence/1.0"
    }

    try:
        response = requests.get(
            GDELT_API_URL,
            params=params,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        if "json" not in response.headers.get("Content-Type", "").lower():
            print("The news API returned an unexpected response.")
            return []

        data = response.json()

        articles = data.get("articles", [])

        results = []

        for article in articles:

            title = article.get("title", "")
            url = article.get("url", "")

            if not title or not url:
                continue

            results.append({
                "title": title,
                "url": url,
                "source": article.get("domain", "Unknown"),
                "image_url": article.get("socialimage", ""),
                "published_date": article.get("seendate", ""),
                "language": article.get("language", "Unknown"),
                "source_country": article.get(
                    "sourcecountry", "Unknown"
                )
            })

        return results

    except requests.exceptions.Timeout:
        print("News search timed out. Please try again.")
        return []

    except requests.exceptions.RequestException as error:
        print("News API connection error:", error)
        return []

    except ValueError:
        print("Unable to read the news API response.")
        return []

    except Exception as error:
        print("Unexpected error:", error)
        return []


if __name__ == "__main__":

    topic = input("Enter a news topic: ")

    print("\nSearching global news...")

    articles = search_global_news(topic)

    print("\nTotal articles found:", len(articles))

    for index, article in enumerate(articles, start=1):

        print("\n", index, ".", article["title"])
        print("Source:", article["source"])
        print("Country:", article["source_country"])
        print("Language:", article["language"])
        print("Published:", article["published_date"])
        print("Image:", article["image_url"])
        print("Original article:", article["url"])
