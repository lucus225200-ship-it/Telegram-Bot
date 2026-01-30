import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONSTANTS & DATABASE PATH ---
DATA_FILE = "bot_data.json"
# သင့် Channel ID ကို ဒီမှာ သေချာအောင် ပြန်စစ်ပေးပါ
CHANNEL_ID = "@Arbwrshotrtdrama"

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
                return json.load(f)
        except:
            pass
    return {key: [] for key in HASHTAG_MAP.values()} | {"new_movies": []}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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

def get_drama_text(category_key):
    img, header = CATEGORY_HEADERS.get(category_key, ("poster.jpg", "Unknown"))
    titles = persistent_data.get(category_key, [])
    if not titles:
        return img, f"{header}\n\n⚠️ ဇာတ်ကားများ မရှိသေးပါ။"
    list_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
    return img, f"{header}\n\n{list_text}"

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Channel မှာ ပို့စ်တင်လိုက်ရင် Bot က အလိုအလျောက် သိမ်းဆည်းပေးမယ့် အပိုင်း"""
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
                if i + 1 < len(lines):
                    movie_title = lines[i+1]
                break
        if found_category:
            break
            
    if found_category and movie_title:
        if movie_title not in persistent_data[found_category]:
            persistent_data[found_category].append(movie_title)
        
        # ဇာတ်ကားအသစ် (၅) ကား စာရင်းထဲ ထည့်ခြင်း
        if movie_title not in persistent_data['new_movies']:
            persistent_data['new_movies'].insert(0, movie_title)
            if len(persistent_data['new_movies']) > 5:
                persistent_data['new_movies'].pop()
                
        save_data(persistent_data)
        logging.info(f"Added movie: {movie_title} to {found_category}")

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
    # !!! အရေးကြီးသည် - @BotFather ထံမှရသော Bot အသစ်၏ Token ကို အောက်ပါနေရာတွင် ထည့်ပါ
    NEW_BOT_TOKEN = "ဘော့အသစ်၏_TOKEN_ကို_ဒီမှာထည့်ပါ"
    
    application = ApplicationBuilder().token(NEW_BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))
    
    print("Channel Bot is online and listening...")
    
    # drop_pending_updates=True က အဟောင်းများကို ရှင်းပေးပါလိမ့်မည်။
    application.run_polling(drop_pending_updates=True)
