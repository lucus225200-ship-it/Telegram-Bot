import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONSTANTS & DATABASE PATH ---
DATA_FILE = "bot_data.json"
CHANNEL_ID = "@Arbwrshotrtdrama"

# --- DATABASE LOGIC ---
# Hashtag နှင့် Category ချိတ်ဆက်မှု
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
    """JSON ဖိုင်မှ ဒေတာများကို ဖတ်ယူခြင်း"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    # ဒေတာမရှိသေးပါက အလွတ်ဖြင့် စတင်မည်
    return {key: [] for key in HASHTAG_MAP.values()} | {"new_movies": []}

def save_data(data):
    """ဒေတာများကို JSON ဖိုင်ထဲသို့ သိမ်းဆည်းခြင်း"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Persistent data ကို စတင်ယူခြင်း
persistent_data = load_data()

def get_image_path(image_name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, image_name)

# Category အလိုက် ခေါင်းစဉ်နှင့် ပုံများ
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

def get_drama_text(category_key):
    """စာရင်းကို စစ်ဆေးပြီး ပြသရန် စာသားထုတ်ပေးခြင်း"""
    img, header = CATEGORY_HEADERS.get(category_key, ("poster.jpg", "Unknown"))
    titles = persistent_data.get(category_key, [])
    
    if not titles:
        # ဇာတ်ကားမရှိသေးပါက ဤစာသားကို ပြပါမည်
        return img, f"{header}\n\n⚠️ ဇာတ်ကားများ မရှိသေးပါ။"
    
    list_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
    return img, f"{header}\n\n{list_text}"

# --- AUTO-UPDATE LOGIC ---
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Channel Post များမှ ဇာတ်ကားများကို အလိုအလျောက် စာရင်းသွင်းပေးခြင်း"""
    if not update.channel_post or not update.channel_post.text:
        return

    text = update.channel_post.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    found_category = None
    movie_title = None

    for i, line in enumerate(lines):
        for hashtag, cat_key in HASHTAG_MAP.items():
            if hashtag.lower() in line.lower():
                found_category = cat_key
                # Hashtag အောက်မှ ပထမဆုံး စာကြောင်းကို ယူခြင်း
                if i + 1 < len(lines):
                    movie_title = lines[i+1]
                break
        if found_category:
            break

    if found_category and movie_title:
        # Category ထဲသို့ ထည့်ခြင်း
        if movie_title not in persistent_data[found_category]:
            persistent_data[found_category].append(movie_title)
        
        # New Movies စာရင်း (FIFO - အများဆုံး ၅ ကား)
        if movie_title not in persistent_data['new_movies']:
            persistent_data['new_movies'].insert(0, movie_title)
            if len(persistent_data['new_movies']) > 5:
                persistent_data['new_movies'].pop()
        
        save_data(persistent_data)

# --- KEYBOARDS & COMMANDS ---
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

    if data in CATEGORY_HEADERS:
        image_name, response_text = get_drama_text(data)
        image_path = get_image_path(image_name)
        back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 မူလစာမျက်နှာသို့", callback_data='main_menu')]])

        if os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo, caption=response_text, parse_mode='Markdown'),
                    reply_markup=back_keyboard
                )
        else:
            await query.edit_message_caption(caption=response_text, reply_markup=back_keyboard, parse_mode='Markdown')

if __name__ == '__main__':
    # နောက်ဆုံးပေးထားသော Token ကို အသုံးပြုထားပါသည်
    TOKEN = "8586583701:AAEHh1zKDUx2Aeyo2eT-HX8V2_-tAJORAu4"
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))
    
    application.run_polling()
