import os
import sqlite3
from threading import Thread
from PIL import Image
from flask import Flask
import telebot
from telebot import types

# --- خادم وهمي لإبقاء البوت نشطاً على المنصة ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- إعدادات البوت الأساسية ---
BOT_TOKEN = "7915236613:AAELMc9S8zCkqPcQLJnTpw76jWyR3OZyeMw"
ADMIN_ID = 6586440875

bot = telebot.TeleBot(BOT_TOKEN)

# --- إدارة قاعدة البيانات (SQLite) ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  lang TEXT DEFAULT 'ar')''')

    for column, definition in [
        ('banned', 'INTEGER DEFAULT 0'),
        ('joined_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
    ]:
        try:
            c.execute(f'ALTER TABLE users ADD COLUMN {column} {definition}')
        except sqlite3.OperationalError:
            pass

    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', '0')")
    conn.commit()
    conn.close()

def ensure_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def get_user_lang(user_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT lang FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 'ar'

def set_user_lang(user_id, lang):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''INSERT INTO users (user_id, lang) VALUES (?, ?)
                 ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang''', (user_id, lang))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users')
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def is_banned(user_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT banned FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def set_banned(user_id, flag):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    c.execute('UPDATE users SET banned = ? WHERE user_id = ?', (1 if flag else 0, user_id))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE banned = 1')
    banned = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE date(joined_at) = date('now')")
    today = c.fetchone()[0]
    conn.close()
    return total, banned, today

def get_maintenance():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'maintenance'")
    row = c.fetchone()
    conn.close()
    return row[0] == '1' if row else False

def set_maintenance(flag):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = 'maintenance'", ('1' if flag else '0',))
    conn.commit()
    conn.close()

init_db()

# --- النصوص والترجمات ---
TEXTS = {
    'ar': {
        'welcome': "مرحباً بك! اختر لغتك / Welcome! Choose your language:",
        'lang_set': "تم اختيار اللغة العربية بنجاح! 🇦🇪\nأرسل لي أي صورة للبدء في تحويلها.",
        'choose_format': "اختر الصيغة التي تريد التحويل إليها:",
        'converting': "⏳ جاري تحويل الملف...",
        'success': "✅ تم التحويل بنجاح!",
        'error': "❌ حدث خطأ أثناء معالجة الملف. تأكد من إرسال صورة صالحة.",
        'admin_menu': "⚙️ *لوحة تحكم الأدمن*\nاختر أحد الخيارات:",
        'stats': "📊 عدد المستخدمين الكلي: {}",
        'broadcast_prompt': "أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين الآن:",
        'broadcast_sent': "✅ تمت الإذاعة بنجاح لـ {} مستخدم.",
        'banned': "🚫 لقد تم حظرك من استخدام هذا البوت.",
        'maintenance': "🛠 البوت في وضع الصيانة حالياً، يرجى المحاولة لاحقاً.",
        'help': ("*📖 طريقة استخدام البوت*\n\n"
                  "1️⃣ أرسل أي صورة وسيعرض عليك البوت صيغ التحويل المتاحة (JPG / PNG / PDF).\n"
                  "2️⃣ يمكنك استخدام /jpg أو /png أو /pdf ثم إرسال الصورة ليتم تحويلها مباشرة دون اختيار.\n"
                  "3️⃣ استخدم /convert للبدء في عملية تحويل جديدة.\n"
                  "4️⃣ استخدم /settings لتغيير لغة البوت.\n"
                  "5️⃣ استخدم /about لمعرفة المزيد عن هذا البوت."),
        'about': ("*ℹ️ عن البوت*\n\n"
                   "بوت لتحويل الصور بين صيغ JPG و PNG و PDF بسهولة وسرعة.\n"
                   "تم التطوير باستخدام Python و Pillow."),
        'settings': "⚙️ اختر لغتك المفضلة:",
        'convert_prompt': "📤 أرسل لي أي صورة الآن وسأعرض عليك صيغ التحويل المتاحة.",
        'send_image_for': "📤 أرسل الصورة الآن وسأحوّلها مباشرة إلى صيغة {}."
    },
    'en': {
        'welcome': "Welcome! Choose your language / مرحباً بك! اختر لغتك:",
        'lang_set': "English selected successfully! 🇬🇧\nSend me any image to start converting.",
        'choose_format': "Choose the target format:",
        'converting': "⏳ Converting your file...",
        'success': "✅ Converted successfully!",
        'error': "❌ An error occurred while processing the file. Make sure it's a valid image.",
        'admin_menu': "⚙️ *Admin Control Panel*\nChoose an option:",
        'stats': "📊 Total registered users: {}",
        'broadcast_prompt': "Send the message you want to broadcast to all users now:",
        'broadcast_sent': "✅ Broadcast sent successfully to {} users.",
        'banned': "🚫 You have been banned from using this bot.",
        'maintenance': "🛠 The bot is currently under maintenance, please try again later.",
        'help': ("*📖 How to use this bot*\n\n"
                  "1️⃣ Send any image and the bot will show you the available formats (JPG / PNG / PDF).\n"
                  "2️⃣ Use /jpg, /png or /pdf then send an image to convert it directly without choosing.\n"
                  "3️⃣ Use /convert to start a new conversion.\n"
                  "4️⃣ Use /settings to change the bot language.\n"
                  "5️⃣ Use /about to learn more about this bot."),
        'about': ("*ℹ️ About this bot*\n\n"
                   "A bot that converts images between JPG, PNG and PDF quickly and easily.\n"
                   "Built with Python and Pillow."),
        'settings': "⚙️ Choose your preferred language:",
        'convert_prompt': "📤 Send me any image now and I'll show you the available formats.",
        'send_image_for': "📤 Send the image now and I'll convert it directly to {}."
    }
}

user_files = {}
user_presets = {}

def admin_main_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 إذاعة للجميع", callback_data="admin_broadcast"),
    )
    markup.add(
        types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban"),
        types.InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban"),
    )
    markup.add(
        types.InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users"),
        types.InlineKeyboardButton("🛠 وضع الصيانة", callback_data="admin_maintenance"),
    )
    markup.add(
        types.InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    ensure_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇦🇪 العربية", callback_data="lang_ar"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.send_message(message.chat.id, TEXTS['ar']['welcome'], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def set_language_callback(call):
    lang = call.data.split('_')[1]
    set_user_lang(call.from_user.id, lang)
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, TEXTS[lang]['lang_set'])

@bot.message_handler(commands=['help'])
def help_cmd(message):
    ensure_user(message.from_user.id)
    lang = get_user_lang(message.from_user.id)
    bot.reply_to(message, TEXTS[lang]['help'], parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def about_cmd(message):
    ensure_user(message.from_user.id)
    lang = get_user_lang(message.from_user.id)
    bot.reply_to(message, TEXTS[lang]['about'], parse_mode="Markdown")

@bot.message_handler(commands=['settings'])
def settings_cmd(message):
    ensure_user(message.from_user.id)
    lang = get_user_lang(message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇦🇪 العربية", callback_data="lang_ar"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.reply_to(message, TEXTS[lang]['settings'], reply_markup=markup)

@bot.message_handler(commands=['convert'])
def convert_cmd(message):
    user_id = message.from_user.id
    ensure_user(user_id)
    lang = get_user_lang(user_id)
    if is_banned(user_id):
        bot.reply_to(message, TEXTS[lang]['banned'])
        return
    user_presets.pop(user_id, None)
    bot.reply_to(message, TEXTS[lang]['convert_prompt'])

@bot.message_handler(commands=['jpg', 'png', 'pdf'])
def preset_format_cmd(message):
    user_id = message.from_user.id
    ensure_user(user_id)
    lang = get_user_lang(user_id)
    if is_banned(user_id):
        bot.reply_to(message, TEXTS[lang]['banned'])
        return
    fmt = message.text.strip('/').lower()
    user_presets[user_id] = fmt
    bot.reply_to(message, TEXTS[lang]['send_image_for'].format(fmt.upper()))

@bot.message_handler(content_types=['photo', 'document'])
def handle_file(message):
    user_id = message.from_user.id
    ensure_user(user_id)
    lang = get_user_lang(user_id)

    if is_banned(user_id):
        bot.reply_to(message, TEXTS[lang]['banned'])
        return

    if get_maintenance() and user_id != ADMIN_ID:
        bot.reply_to(message, TEXTS[lang]['maintenance'])
        return

    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
    else:
        if not (message.document.mime_type and message.document.mime_type.startswith('image/')):
            bot.reply_to(message, TEXTS[lang]['error'])
            return
        file_id = message.document.file_id

    user_files[user_id] = file_id

    preset = user_presets.pop(user_id, None)
    if preset:
        msg = bot.reply_to(message, TEXTS[lang]['converting'])
        perform_conversion(message.chat.id, user_id, preset, lang, msg.message_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("JPG 🖼️", callback_data="convert_jpg"),
        types.InlineKeyboardButton("PNG 🖼️", callback_data="convert_png"),
        types.InlineKeyboardButton("PDF 📄", callback_data="convert_pdf")
    )
    bot.reply_to(message, TEXTS[lang]['choose_format'], reply_markup=markup)

def perform_conversion(chat_id, user_id, target_fmt, lang, status_msg_id):
    file_id = user_files.get(user_id)
    input_path = f"input_{user_id}"
    output_path = f"output_{user_id}.{target_fmt}"

    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(input_path, 'wb') as f:
            f.write(downloaded_file)

        img = Image.open(input_path)
        if img.mode in ("RGBA", "P") and target_fmt in ['jpg', 'pdf']:
            img = img.convert("RGB")

        if target_fmt == 'pdf':
            img.save(output_path, "PDF", resolution=100.0)
            with open(output_path, 'rb') as f:
                bot.send_document(chat_id, f, caption=TEXTS[lang]['success'])
        else:
            fmt_name = "JPEG" if target_fmt == "jpg" else "PNG"
            img.save(output_path, fmt_name)
            with open(output_path, 'rb') as f:
                bot.send_photo(chat_id, f, caption=TEXTS[lang]['success'])

        bot.delete_message(chat_id, status_msg_id)

    except Exception as e:
        bot.edit_message_text(TEXTS[lang]['error'], chat_id, status_msg_id)
        print(f"Error: {e}")

    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
        user_files.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('convert_'))
def convert_callback(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    target_fmt = call.data.split('_')[1]

    if user_id not in user_files:
        alert_text = "الملف انتهت صلاحيته، يرجى إعادة إرساله." if lang == 'ar' else "The file has expired, please resend it."
        bot.answer_callback_query(call.id, alert_text, show_alert=True)
        return

    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, TEXTS[lang]['converting'])
    perform_conversion(call.message.chat.id, user_id, target_fmt, lang, msg.message_id)

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, TEXTS['ar']['admin_menu'], parse_mode="Markdown", reply_markup=admin_main_markup())

def send_users_list(chat_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT user_id, lang, banned FROM users ORDER BY joined_at DESC')
    rows = c.fetchall()
    conn.close()

    if not rows:
        bot.send_message(chat_id, "لا يوجد مستخدمون مسجلون بعد.", reply_markup=admin_main_markup())
        return

    lines = [f"{uid} | {lg} | {'محظور' if bnd else 'نشط'}" for uid, lg, bnd in rows]
    content = "\n".join(lines)

    if len(rows) <= 30:
        bot.send_message(chat_id, f"👥 *قائمة المستخدمين ({len(rows)})*\n\n`{content}`",
                          parse_mode="Markdown", reply_markup=admin_main_markup())
    else:
        file_path = "users_list.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        with open(file_path, "rb") as f:
            bot.send_document(chat_id, f, caption=f"👥 إجمالي المستخدمين: {len(rows)}")
        os.remove(file_path)
        bot.send_message(chat_id, "تم إرسال القائمة كملف نصي أعلاه ⬆️", reply_markup=admin_main_markup())

def process_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    users = get_all_users()
    count = 0
    for uid in users:
        try:
            bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            count += 1
        except Exception:
            pass
    bot.send_message(message.chat.id, TEXTS['ar']['broadcast_sent'].format(count), reply_markup=admin_main_markup())

def process_ban(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.strip())
        set_banned(target_id, True)
        bot.send_message(message.chat.id, f"✅ تم حظر المستخدم `{target_id}` بنجاح.",
                          parse_mode="Markdown", reply_markup=admin_main_markup())
        try:
            bot.send_message(target_id, TEXTS[get_user_lang(target_id)]['banned'])
        except Exception:
            pass
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إرسال آيدي رقمي صحيح.", reply_markup=admin_main_markup())

def process_unban(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.strip())
        set_banned(target_id, False)
        bot.send_message(message.chat.id, f"✅ تم إلغاء حظر المستخدم `{target_id}` بنجاح.",
                          parse_mode="Markdown", reply_markup=admin_main_markup())
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إرسال آيدي رقمي صحيح.", reply_markup=admin_main_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id)
        return

    action = call.data.split('_', 1)[1]
    bot.answer_callback_query(call.id)

    if action == "stats":
        total, banned, today = get_stats()
        maintenance = "🟢 مفعّل" if get_maintenance() else "🔴 متوقف"
        text = (
            f"📊 *إحصائيات البوت*\n\n"
            f"👥 إجمالي المستخدمين: `{total}`\n"
            f"🚫 المستخدمون المحظورون: `{banned}`\n"
            f"🆕 مستخدمون جدد اليوم: `{today}`\n"
            f"🛠 وضع الصيانة: {maintenance}"
        )
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=admin_main_markup())

    elif action == "broadcast":
        msg = bot.send_message(call.message.chat.id, TEXTS['ar']['broadcast_prompt'])
        bot.register_next_step_handler(msg, process_broadcast)

    elif action == "ban":
        msg = bot.send_message(call.message.chat.id, "أرسل آيدي المستخدم الذي تريد حظره:")
        bot.register_next_step_handler(msg, process_ban)

    elif action == "unban":
        msg = bot.send_message(call.message.chat.id, "أرسل آيدي المستخدم الذي تريد إلغاء حظره:")
        bot.register_next_step_handler(msg, process_unban)

    elif action == "users":
        send_users_list(call.message.chat.id)

    elif action == "maintenance":
        new_state = not get_maintenance()
        set_maintenance(new_state)
        state_text = "تم تفعيل وضع الصيانة 🔴" if new_state else "تم إيقاف وضع الصيانة 🟢"
        bot.send_message(call.message.chat.id, state_text, reply_markup=admin_main_markup())

    elif action == "close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

def setup_commands():
    commands = [
        types.BotCommand("start", "بدء استخدام البوت"),
        types.BotCommand("help", "طريقة استخدام البوت"),
        types.BotCommand("convert", "تحويل الصور والملفات"),
        types.BotCommand("jpg", "تحويل الصورة إلى JPG"),
        types.BotCommand("png", "تحويل الصورة إلى PNG"),
        types.BotCommand("pdf", "تحويل الصورة إلى PDF"),
        types.BotCommand("settings", "إعدادات البوت"),
        types.BotCommand("about", "معلومات عن البوت"),
        types.BotCommand("admin", "لوحة تحكم المسؤول"),
    ]
    bot.set_my_commands(commands)

if __name__ == '__main__':
    setup_commands()
    keep_alive()  # تشغيل الخادم الوهمي قبل البوت
    print("Bot started successfully...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

