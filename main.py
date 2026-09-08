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



def generate_article(news_text):
    # GEMINI_API_KEY 環境変数を自動認識します
    client = genai.Client()

    # main.py と同じ階層にある prompt.txt を安全に取得
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_dir, "prompt.txt")

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()
    today_str = datetime.now().strftime("%Y年%m月%d日")
    
    # プロンプトの冒頭に今日の日付を明記して渡す（2026/9/8）
    final_prompt = f"本日の日付: {today_str}\n\n{prompt}\n\n{news_text}"

    
    # final_prompt = f"{prompt}\n\n{news_text}"

    max_retries = 3
    retry_delay = 45  # 429エラー時は45秒待機して再試行

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
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
