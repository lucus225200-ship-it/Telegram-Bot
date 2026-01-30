import json
import logging
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Use either User Bot or Admin Bot Token to watch
WATCHER_TOKEN = "8586583701:AAE-ZVQJjw0mqKl0ePcM9QGbnVv4gLbm2fE"
DATA_PATH = "storage/movies.json"

HASHTAG_MAP = {
    '#အချစ်ဇာတ်လမ်း': 'love',
    '#အိမ်ထောင်ရေး': 'family',
    '#နန်းတွင်း': 'palace',
    # ... add all other mappings
}

def update_movie_db(category, title, link):
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {"categories": {}, "new_movies": []}

    entry = {
        "title": title,
        "link": link,
        "date": datetime.datetime.now().strftime("%d/%m")
    }

    # Category Update (Append only)
    if category not in data["categories"]:
        data["categories"][category] = []
    
    # Don't duplicate if already exists
    if not any(m['link'] == link for m in data["categories"][category]):
        data["categories"][category].insert(0, entry)

    # New Movies Update (FIFO 5)
    data["new_movies"] = [m for m in data["new_movies"] if m['link'] != link]
    data["new_movies"].insert(0, entry)
    data["new_movies"] = data["new_movies"][:5]

    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def watch_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post or update.edited_channel_post
    if not post: return
    
    content = post.text or post.caption or ""
    lines = content.split('\n')
    
    category = None
    for hashtag, key in HASHTAG_MAP.items():
        if hashtag in lines[0]:
            category = key
            break
            
    if category and len(lines) > 1:
        title = lines[1].strip()
        link = f"https://t.me/{post.chat.username}/{post.message_id}"
        update_movie_db(category, title, link)
        logging.info(f"Updated: {title} in {category}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(WATCHER_TOKEN).build()
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, watch_posts))
    app.run_polling()
