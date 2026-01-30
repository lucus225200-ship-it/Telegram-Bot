import os
import json
import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONSTANTS & DATABASE PATH ---
DATA_FILE = "bot_data.json"

# --- DATABASE LOGIC ---
HASHTAG_MAP = {
    '#romance': 'love',
    '#family': 'family',
    '#palace': 'palace',
    '#ceo': 'ceo',
    '#action': 'action',
    '#revenge': 'revenge',
    '#life': 'life',
    '#thriller': 'thriller',
    '#fantasy': 'fantasy',
    '#comedy': 'comedy'
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure new data structures exist
                if 'enhanced_data' not in data:
                    data['enhanced_data'] = {v: [] for v in HASHTAG_MAP.values()}
                if 'new_movies_list' not in data:
                    data['new_movies_list'] = []
                return data
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    return {
        'enhanced_data': {v: [] for v in HASHTAG_MAP.values()},
        'new_movies_list': []
    }

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

persistent_data = load_data()

def get_image_path(image_name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, image_name)

CATEGORY_HEADERS = {
    'love': ("Romance.jpg", "💖 *အချစ်ဇာတ်လမ်းများ*"),
    'family': ("Family.jpg", "🏠 *အိမ်ထောင်ရေးဇာတ်လမ်းများ*"),
    'palace': ("Royal.jpg", "👑 *နန်းတွင်းဇာတ်လမ်းများ*"),
    'ceo': ("Workplace.jpg", "🏢 *ကုမ္ပဏီဥက္ကဌဇာတ်လမ်းများ*"),
    'action': ("Action.jpg", "⚔️ *အက်ရှင်ဇာတ်လမ်းများ*"),
    'revenge': ("Betrayal.jpg", "🩸 *လက်စားချေခြင်းဇာတ်လမ်းများ*"),
    'life': ("Life.jpg", "🎭 *ဘဝသရုပ်ဖော်ဇာတ်လမ်းများ*"),
    'thriller': ("Thriller.jpg", "🔪 *သည်းထိတ်ရင်ဖိုဇာတ်လမ်းများ*"),
    'fantasy': ("Deception.jpg", "🪄 *စိတ်ကူးယဉ်ဇာတ်လမ်းများ*"),
    'comedy': ("Funny.jpg", "😂 *ဟာသဇာတ်လမ်းများ*"),
    'new_movies': ("poster.jpg", "🆕 *ဇာတ်ကားအသစ်များ*")
}

# --- DATE HELPER ---
def get_myanmar_date(date_str):
    try:
        post_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        now = datetime.datetime.now().date()
        diff = (now - post_date).days
        
        if diff == 0:
            return "(ယနေ့)"
        elif diff == 1:
            return "(မနေ့က)"
        else:
            myan_numbers = {'0':'၀', '1':'၁', '2':'၂', '3':'၃', '4':'၄', '5':'၅', '6':'၆', '7':'၇', '8':'၈', '9':'၉'}
            diff_str = str(diff)
            myan_diff = "".join([myan_numbers.get(d, d) for d in diff_str])
            return f"({myan_diff} ရက်)"
    except:
        return ""

# --- BUTTON BUILDER (Rule #1, #2, #3) ---
def build_movie_buttons(category_key):
    if category_key == 'new_movies':
        movies = persistent_data.get('new_movies_list', [])
        header_text = CATEGORY_HEADERS['new_movies'][1]
    else:
        movies = persistent_data.get('enhanced_data', {}).get(category_key, [])
        header_text = CATEGORY_HEADERS.get(category_key, ("poster.jpg", "Unknown"))[1]

    keyboard = []
    if not movies:
        caption = f"{header_text}\n\n⚠️ ဇာတ်ကားများ မရှိသေးပါ။"
    else:
        caption = f"{header_text}\n\nကြည့်ရှုလိုသည့် ဇာတ်ကားကို နှိပ်ပါ 👇"
        for movie in movies:
            # Rule: One title = One button with Jump Link
            keyboard.append([InlineKeyboardButton(f"🎬 {movie['title']}", url=movie['link'])])
            # Rule: Non-clickable time label underneath
            time_label = get_myanmar_date(movie['date'])
            keyboard.append([InlineKeyboardButton(time_label, callback_data="none")])

    keyboard.append([InlineKeyboardButton("🔙 မူလစာမျက်နှာသို့", callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard), caption

# --- CHANNEL HANDLER (Rule #1, #2) ---
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post or update.edited_channel_post
    if not post: return

    text = post.text if post.text else post.caption
    if not text: return

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    found_category = None
    movie_title = None

    for i, line in enumerate(lines):
        for hashtag, cat_key in HASHTAG_MAP.items():
            if hashtag.lower() in line.lower():
                found_category = cat_key
                if i + 1 < len(lines):
                    movie_title = lines[i+1] # First line after hashtag
                break
        if found_category: break

    if found_category and movie_title:
        # Generate Jump Link
        if post.chat.username:
            post_link = f"https://t.me/{post.chat.username}/{post.message_id}"
        else:
            chat_id_str = str(post.chat.id).replace("-100", "")
            post_link = f"https://t.me/c/{chat_id_str}/{post.message_id}"

        movie_entry = {
            "title": movie_title,
            "link": post_link,
            "date": datetime.datetime.now().strftime("%Y-%m-%d")
        }

        # Update Category List (Newest at Top)
        cat_list = persistent_data['enhanced_data'][found_category]
        # Remove if exists to re-insert at top
        persistent_data['enhanced_data'][found_category] = [m for m in cat_list if m['title'] != movie_title]
        persistent_data['enhanced_data'][found_category].insert(0, movie_entry)

        # Update New Movies (FIFO - Max 5)
        new_list = persistent_data['new_movies_list']
        persistent_data['new_movies_list'] = [m for m in new_list if m['title'] != movie_title]
        persistent_data['new_movies_list'].insert(0, movie_entry)
        
        if len(persistent_data['new_movies_list']) > 5:
            persistent_data['new_movies_list'].pop() # Remove oldest

        save_data(persistent_data)
        logger.info(f"Added to DB: {movie_title}")

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💖 အချစ်ဇာတ်လမ်း", callback_data='love'), InlineKeyboardButton("🏠 အိမ်ထောင်ရေး", callback_data='family')],
        [InlineKeyboardButton("👑 နန်းတွင်းကား", callback_data='palace'), InlineKeyboardButton("🏢 ကုမ္ပဏီဥက္ကဌ", callback_data='ceo')],
        [InlineKeyboardButton("⚔️ ရှေးဟောင်းအက်ရှင်", callback_data='action'), InlineKeyboardButton("🩸 လက်စားချေခြင်း", callback_data='revenge')],
        [InlineKeyboardButton("🎭 ဘဝသရုပ်ဖော်", callback_data='life'), InlineKeyboardButton("🔪 သည်းထိတ်ရင်ဖို", callback_data='thriller')],
        [InlineKeyboardButton("🪄 စိတ်ကူးယဉ်", callback_data='fantasy'), InlineKeyboardButton("😂 ဟာသဇာတ်လမ်း", callback_data='comedy')],
        [InlineKeyboardButton("🆕 ဇာတ်ကားအသစ်များ", callback_data='new_movies'), 
         InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url='https://t.me/Arbwrshotrtdrama')]
    ])

WELCOME_TEXT = (
    "🎬 *Arbwr Short Drama Channel မှ ကြိုဆိုပါတယ်ခင်ဗျာ!*\n\n"
    "မြန်မာစာတန်းထိုးနှင့် မြန်မာစကားပြော တရုတ်ဇာတ်လမ်းတိုကောင်းများကို "
    "ဤနေရာတွင် စုစည်းပေးထားပါသည်။\n\n"
    "ကြည့်ရှုလိုသော အမျိုးအစားကို အောက်ပါခလုတ်များတွင် ရွေးချယ်နိုင်ပါသည်။ 👇"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image_path = get_image_path("poster.jpg")
    reply_markup = get_main_keyboard()
    if os.path.exists(image_path):
        with open(image_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=WELCOME_TEXT, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=WELCOME_TEXT, parse_mode='Markdown', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'main_menu':
        image_path = get_image_path("poster.jpg")
        if os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo, caption=WELCOME_TEXT, parse_mode='Markdown'),
                    reply_markup=get_main_keyboard()
                )
        return
        
    if data in CATEGORY_HEADERS or data == 'new_movies':
        reply_markup, response_text = build_movie_buttons(data)
        image_name = CATEGORY_HEADERS.get(data, ("poster.jpg", ""))[0]
        image_path = get_image_path(image_name)
        
        if os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo, caption=response_text, parse_mode='Markdown'),
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_caption(caption=response_text, reply_markup=reply_markup, parse_mode='Markdown')

if __name__ == '__main__':
    TOKEN = "8586583701:AAE-ZVQJjw0mqKl0ePcM9QGbnVv4gLbm2fE"
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_handler(MessageHandler(
        filters.ChatType.CHANNEL & (filters.TEXT | filters.CAPTION), 
        channel_post_handler
    ))
    
    logger.info("Bot is starting with FIFO and Jump Link logic...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
