import os
import time
import re
import feedparser
from google import genai
from google.genai import errors
from email.mime.text import MIMEText
import smtplib
from datetime import datetime

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/.rss/full/"
]

def clean_html(text):
    """HTMLタグを簡易除去する関数"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).strip()

def get_news():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                summary = clean_html(entry.get('summary', ''))
                articles.append(
                    f"Title:\n{entry.title}\n\nSummary:\n{summary}\n"
                )
        except Exception as e:
            print(f"Warning: Failed to fetch RSS feed {url}: {e}")

    return "\n---\n".join(articles)


def generate_article(news_text):
    # GEMINI_API_KEY 環境変数を自動認識します
    client = genai.Client()

    # main.py と同じ階層にある prompt.txt を安全に取得
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_dir, "prompt.txt")

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    final_prompt = f"{prompt}\n\n{news_text}"

    max_retries = 3
    retry_delay = 45  # 429エラー時は45秒待機して再試行

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=final_prompt
            )
            return response.text
        except errors.APIError as e:
            if "RESOURCE_EXHAUSTED" in str(e) or getattr(e, 'code', None) == 429:
                print(f"Quota exceeded (429). Retrying in {retry_delay}s... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                raise e

    raise RuntimeError("Failed to generate article after maximum retries due to quota limits.")


def send_mail(article):
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    receiver = os.environ["MAIL_TO"]

    subject = f"暗号資産ニュース整理 {datetime.now().strftime('%Y-%m-%d')}"

    msg = MIMEText(article, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


if __name__ == "__main__":
    news = get_news()
    if not news.strip():
        print("No news articles fetched. Exiting.")
    else:
        article = generate_article(news)
        send_mail(article)
        print("Mail sent successfully!")
