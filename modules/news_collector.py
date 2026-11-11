
import feedparser
import requests
import re
import html

from urllib.parse import urljoin


# ==========================================================
# 1. NEWS SOURCES
# ==========================================================

NEWS_FEEDS = [
    {
        "source": "BBC",
        "category": "World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml"
    },
    {
        "source": "BBC",
        "category": "Technology",
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"
    },
    {
        "source": "BBC",
        "category": "Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml"
    },
    {
        "source": "BBC",
        "category": "Science",
        "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
    },
    {
        "source": "BBC",
        "category": "Sports",
        "url": "https://feeds.bbci.co.uk/sport/rss.xml"
    },
    {
        "source": "The Guardian",
        "category": "World",
        "url": "https://www.theguardian.com/world/rss"
    },
    {
        "source": "The Guardian",
        "category": "Technology",
        "url": "https://www.theguardian.com/uk/technology/rss"
    },
    {
        "source": "The Guardian",
        "category": "Business",
        "url": "https://www.theguardian.com/uk/business/rss"
    },
    {
        "source": "Al Jazeera",
        "category": "World",
        "url": "https://www.aljazeera.com/xml/rss/all.xml"
    }
]


# Maximum articles collected from each feed
MAX_ARTICLES_PER_FEED = 30

# Request timeout in seconds
REQUEST_TIMEOUT = 20

# Browser-like request identification
HEADERS = {
    "User-Agent": "NewsArticleIntelligenceSystem/1.0"
}


# ==========================================================
# 2. CLEAN NEWS DESCRIPTION
# ==========================================================

def clean_description(text):
    """Remove HTML tags and unnecessary spaces."""

    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", str(text))

    text = html.unescape(text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==========================================================
# 3. EXTRACT ARTICLE IMAGE
# ==========================================================

def get_article_image(item):
    """
    Extract an image URL from RSS article information.

    Checks media content, thumbnails, enclosures,
    links and images inside article descriptions.
    """

    # Check media content
    media_content = item.get("media_content", [])

    for media in media_content:

        image_url = media.get("url", "")

        if image_url:
            return image_url

    # Check media thumbnail
    media_thumbnail = item.get("media_thumbnail", [])

    for media in media_thumbnail:

        image_url = media.get("url", "")

        if image_url:
            return image_url

    # Check RSS enclosures
    for enclosure in item.get("enclosures", []):

        image_url = enclosure.get("href", "")

        if not image_url:
            image_url = enclosure.get("url", "")

        if image_url:
            return image_url

    # Check links
    for link in item.get("links", []):

        link_type = link.get("type", "")

        if link_type.startswith("image/"):

            image_url = link.get("href", "")

            if image_url:
                return image_url

    # Check image inside description
    description = item.get("summary", "")

    if not description:

        content = item.get("content", [])

        if content:
            description = content[0].get("value", "")

    image_match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        str(description),
        re.IGNORECASE
    )

    if image_match:
        return html.unescape(image_match.group(1))

    return None


# ==========================================================
# 4. EXTRACT ARTICLE DESCRIPTION
# ==========================================================

def get_article_description(item):
    """Get a readable article description."""

    description = item.get("summary", "")

    if not description:

        content = item.get("content", [])

        if content:
            description = content[0].get("value", "")

    return clean_description(description)


# ==========================================================
# 5. COLLECT NEWS FROM RSS FEEDS
# ==========================================================

def collect_news(max_articles_per_feed=MAX_ARTICLES_PER_FEED):

    articles = []

    seen_urls = set()

    print("\n======================================")
    print("NEWS ARTICLE INTELLIGENCE SYSTEM")
    print("Starting latest news collection")
    print("======================================")

    for feed_info in NEWS_FEEDS:

        source = feed_info["source"]

        category = feed_info["category"]

        feed_url = feed_info["url"]

        print("\n--------------------------------------")

        print("Source:", source)

        print("Category:", category)

        try:

            # Download fresh RSS feed data
            response = requests.get(
                feed_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if not feed.entries:

                print("No articles found. Skipping feed.")

                continue

            print(
                "Articles available:",
                len(feed.entries)
            )

            collected_count = 0

            for item in feed.entries[:max_articles_per_feed]:

                # Get article title
                title = clean_description(
                    item.get("title", "")
                )

                # Get article URL
                url = item.get("link", "").strip()

                if not title or not url:
                    continue

                # Convert relative links to absolute links
                url = urljoin(feed_url, url)

                # Avoid duplicate URLs
                if url in seen_urls:
                    continue

                seen_urls.add(url)

                # Get article description
                description = get_article_description(item)

                # Get article image
                image_url = get_article_image(item)

                if image_url:
                    image_url = urljoin(url, image_url)

                # Get publication date
                published_date = item.get(
                    "published",
                    item.get(
                        "updated",
                        "Date not available"
                    )
                )

                # Maintain compatibility with process_news.py
                article = {

                    "title": title,

                    "description": description,

                    "content": description,

                    "source": source,

                    "url": url,

                    "image_url": image_url,

                    "published_date": published_date,

                    "category": category
                }

                articles.append(article)

                collected_count += 1

            print(
                "Successfully collected:",
                collected_count
            )

        except requests.exceptions.Timeout:

            print(
                "Connection timed out. Skipping:",
                source,
                category
            )

        except requests.exceptions.RequestException as error:

            print(
                "Network error:",
                error
            )

        except Exception as error:

            print(
                "Unexpected collection error:",
                error
            )

    # ======================================================
    # 6. COLLECTION SUMMARY
    # ======================================================

    print("\n======================================")

    print("NEWS COLLECTION COMPLETED")

    print("Total unique articles:", len(articles))

    print("======================================")

    return articles


# ==========================================================
# 7. TEST NEWS COLLECTOR
# ==========================================================

if __name__ == "__main__":

    collected_articles = collect_news()

    print("\nSample collected articles:")

    for index, article in enumerate(
        collected_articles[:5],
        start=1
    ):

        print("\n", index, article["title"])

        print("Source:", article["source"])

        print("Category:", article["category"])

        print("Published:", article["published_date"])

        print("Image:", article["image_url"])

        print("URL:", article["url"])
