import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# Arbwr Short Drama Channel Bot Script
# ပုံများကို Memory ထဲတွင် ကြိုတင်သိမ်းဆည်းထားခြင်းဖြင့် ပိုမိုမြန်ဆန်စေပါသည်။

# ပုံလမ်းကြောင်း ရယူရန် Function
def get_image_path(image_name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, image_name)



# ဇာတ်လမ်းဒေတာများနှင့် ပုံအမည်များ
DRAMA_DATA = {
    'love': ("Romance.jpg", "💖 *အချစ်ဇာတ်လမ်းများ*\n\n1. Boss ရဲ့လျှို့ဝှက်ချစ်သူ\n2. ကံကြမ္မာပေးတဲ့ အချစ်\n3. အိမ်နီးချင်းဥက္ကဌကြီး"),
    'family': ("Family.jpg", "🏠 *အိမ်ထောင်ရေးဇာတ်လမ်းများ*\n\n1. ပြန်လည်ဆုံစည်းခြင်း\n2. ယောက္ခမနှင့် ချွေးမ\n3. အိမ်ထောင်ရှင်တို့ရဲ့ လျှို့ဝှက်ချက်"),
    'palace': ("Royal.jpg", "👑 *နန်းတွင်းဇာတ်လမ်းများ*\n\n1. နန်းတွင်းပရိယာယ်\n2. မိဖုရားကြီးရဲ့ ကလဲ့စား\n3. မင်းသားနှင့် မိန်းကလေး"),
    'ceo': ("Workplace.jpg", "🏢 *ကုမ္ပဏီဥက္ကဌဇာတ်လမ်းများ*\n\n1. Cold Boss\n2. CEO ရဲ့ဇနီးအတု\n3. ကျွန်မရဲ့သူဌေးမင်း"),
    'action': ("Action.jpg", "⚔️ *အက်ရှင်ဇာတ်လမ်းများ*\n\n1. ဓားသိုင်းလောက\n2. သူရဲကောင်းရဲ့ ခရီးစဉ်\n3. လက်စားချေသူ"),
    'revenge': ("Betrayal.jpg", "🩸 *လက်စားချေခြင်းဇာတ်လမ်းများ*\n\n1. ပြန်လာသော ဘုရင်မ\n2. မျက်ရည်မရှိသော ကလဲ့စား\n3. သစ္စာဖောက်သူများ"),
    'life': ("Life.jpg", "🎭 *ဘဝသရုပ်ဖော်ဇာတ်လမ်းများ*\n\n1. လောကဓံ\n2. မိခင်မေတ္တာ\n3. ရုန်းကန်ခြင်းများ"),
    'thriller': ("Thriller.jpg", "🔪 *သည်းထိတ်ရင်ဖိုဇာတ်လမ်းများ*\n\n1. လျှို့ဝှက်လူသတ်သမား\n2. ပဟေဠိအိမ်ကြီး\n3. နောက်ယောင်ခံသူ"),
    'fantasy': ("Deception.jpg", "🪄 *စိတ်ကူးယဉ်ဇာတ်လမ်းများ*\n\n1. နတ်ဘုရားတို့ရဲ့ စစ်ပွဲ\n2. အာကာသခရီးသည်\n3. မှော်ပညာရှင်"),
    'comedy': ("Funny.jpg", "😂 *ဟာသဇာတ်လမ်းများ*\n\n1. သူငယ်ချင်းများ\n2. မင်္ဂလာဆောင်ဟာသ\n3. ရယ်စရာလူသား"),
    'new_movies': ("poster.jpg", "🆕 *ဇာတ်ကားအသစ်များ*\n\n1. ဥက္ကဌကြီး၏ ချစ်သက်သေ (ယနေ့တင်)\n2. နန်းတွင်းကစားပွဲ (မနေ့ကတင်)\n3. ချစ်ခြင်းရဲ့ ကလဲ့စား (အသစ်)")
}

# Main Menu Keyboard
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💖 အချစ်ဇာတ်လမ်း", callback_data='love'), InlineKeyboardButton("🏠 အိမ်ထောင်ရေး", callback_data='family')],
        [InlineKeyboardButton("👑 နန်းတွင်းကား", callback_data='palace'), InlineKeyboardButton("🏢 ကုမ္ပဏီဥက္ကဌ", callback_data='ceo')],
        [InlineKeyboardButton("⚔️ ရှေးဟောင်းအက်ရှင်", callback_data='action'), InlineKeyboardButton("🩸 လက်စားချေခြင်း", callback_data='revenge')],
        [InlineKeyboardButton("🎭 ဘဝသရုပ်ဖော်", callback_data='life'), InlineKeyboardButton("🔪 သည်းထိတ်ရင်ဖို", callback_data='thriller')],
        [InlineKeyboardButton("🪄 စိတ်ကူးယဉ်", callback_data='fantasy'), InlineKeyboardButton("😂 ဟာသဇာတ်လမ်း", callback_data='comedy')],
        [InlineKeyboardButton("🆕 ဇာတ်ကားအသစ်များ", callback_data='new_movies'), InlineKeyboardButton("📢 Channel သို့ဝင်ရန်", url='https://t.me/arbwrdrama')]
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
        await update.message.reply_text(text=WELCOME_TEXT + "\n\n(Poster မတွေ့ပါ)", parse_mode='Markdown', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # answer callback ချက်ချင်းလုပ်ခြင်းဖြင့် Loading အဝိုင်းလည်နေတာကို ပျောက်စေပါတယ်
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

    if data in DRAMA_DATA:
        image_name, response_text = DRAMA_DATA[data]
        image_path = get_image_path(image_name)
        
        back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 မူလစာမျက်နှာသို့", callback_data='main_menu')]])

        if os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=photo, caption=response_text, parse_mode='Markdown'),
                    reply_markup=back_keyboard
                )
        else:
            await query.edit_message_caption(caption=response_text + "\n\n(ပုံမတွေ့ပါ)", reply_markup=back_keyboard, parse_mode='Markdown')

if __name__ == '__main__':
    TOKEN = "8586583701:AAGvLjxSf2_-Bq06Nb0Hnum2UjCNDbpmAmw"
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running fast...")
    application.run_polling()
