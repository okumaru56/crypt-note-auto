import os
import time
import re
import feedparser
from google import genai
from google.genai import errors
from email.mime.text import MIMEText
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9以降で標準搭載

# 日本時間（JST）で現在日時を取得
jst = ZoneInfo("Asia/Tokyo")
now_jst = datetime.now(jst)

# 日付文字列を作成（例: 2026-09-08 または 2026年09月08日）
today_str = now_jst.strftime("%Y-%m-%d")

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
                published_date = entry.get('published', entry.get('updated', '日付不明'))
                
                articles.append(
                    f"Title: {entry.title}\n"
                    f"Date: {published_date}\n"
                    f"Summary: {summary}\n"
                )
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    return "\n---\n".join(articles)


import time
from google.genai import errors

def generate_article(news_text):
    client = genai.Client()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_dir, "prompt.txt")

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    # JSTでの日付組み込み（前回の修正）
    jst = ZoneInfo("Asia/Tokyo")
    today_str = datetime.now(jst).strftime("%Y年%m月%d日")

    final_prompt = f"本日の日付: {today_str}\n\n{prompt}\n\n{news_text}"

    max_retries = 5       # 最大5回まで再試行
    retry_delay = 40      # 混雑時は40秒待機

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=final_prompt
            )
            return response.text
        except errors.APIError as e:
            # エラーメッセージまたはステータスコードから 429 / 503 を判定
            err_msg = str(e)
            is_busy = (
                "UNAVAILABLE" in err_msg or 
                "RESOURCE_EXHAUSTED" in err_msg or 
                getattr(e, 'code', None) in [429, 503]
            )

            if is_busy and attempt < max_retries - 1:
                print(f"API busy/unavailable (Attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise e

    raise RuntimeError("Failed to generate article after maximum retries due to server availability or quota limits.")

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
