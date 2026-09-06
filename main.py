import os
import feedparser
import google.generativeai as genai
from email.mime.text import MIMEText
import smtplib
from datetime import datetime

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/.rss/full/"
]

def get_news():

    articles = []

    for url in RSS_FEEDS:

        feed = feedparser.parse(url)

        for entry in feed.entries[:5]:

            articles.append(
                f"""
Title:
{entry.title}

Summary:
{entry.get('summary','')}
"""
            )

    return "\n".join(articles)


def generate_article(news_text):

    genai.configure(
        api_key=os.environ["GEMINI_API_KEY"]
    )

    model = genai.GenerativeModel(
        "gemini-3.1-pro-preview"
    )

    with open("prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()

    final_prompt = prompt + "\n\n" + news_text

    response = model.generate_content(
        final_prompt
    )

    return response.text


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

    article = generate_article(news)

    send_mail(article)
