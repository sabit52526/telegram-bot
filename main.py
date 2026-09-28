import os
import sqlite3
import time
import logging
from threading import Thread
import telebot
from telebot import types
from flask import Flask

# ================= RENDER FREE WEB SERVICE KEEP-ALIVE =================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web_server, daemon=True).start()

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8808647263
OFFICIAL_CHANNEL = "@ClickEarnProOfficial"
SUPPORT_USERNAME = "@ClickEarnSupport"
MIN_WITHDRAW = 0.20
WITHDRAW_FEE = 0.02
TEN_DAYS_SEC = 10 * 86400  # 10 days in seconds

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
logging.basicConfig(level=logging.INFO)

USER_STATES = {}

# ================= DATABASE SETUP =================
def get_db():
    conn = sqlite3.connect("bot.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            pending_balance REAL DEFAULT 0.0,
            referrer_id INTEGER,
            lang TEXT DEFAULT 'bn',
            is_banned INTEGER DEFAULT 0,
            has_withdrawn_once INTEGER DEFAULT 0,
            joined_at INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_bn TEXT,
            title_en TEXT,
            reward REAL,
            link TEXT,
            task_type TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            reward REAL,
            matures_at INTEGER,
            status TEXT DEFAULT 'pending',
            warning_at INTEGER DEFAULT 0
        )
    ''')

    try:
        cursor.execute("ALTER TABLE user_tasks ADD COLUMN warning_at INTEGER DEFAULT 0")
    except Exception:
        pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            method TEXT,
            address TEXT,
            amount REAL,
            fee REAL,
            net_amount REAL,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ================= BILINGUAL DICTIONARY =================
TEXTS = {
    'bn': {
        'welcome': "👋 **স্বাগতম!**\n\nসহজ কাজ করে টাকা আয় করুন। বোটে কাজ শুরু করতে প্রথমে আমাদের অফিশিয়াল চ্যানেলে জয়েন করুন।",
        'must_join': "⚠️ বোটে কাজ করতে আমাদের অফিশিয়াল চ্যানেলে জয়েন করা বাধ্যতামূলক!",
        'btn_join': "📢 অফিশিয়াল চ্যানেল",
        'btn_verify': "✅ ভেরিফাই করুন",
        'verified_success': "🎉 আপনাকে ধন্যবাদ! ভেরিফিকেশন সফল হয়েছে।",
        'not_joined': "❌ আপনি এখনও চ্যানেলে জয়েন করেননি! জয়েন করে ভেরিফাই বাটনে চাপুন।",
        'btn_balance': "💰 ব্যালেন্স",
        'btn_tasks': "📋 কাজ",
        'btn_withdraw': "📥 উত্তোলন",
        'btn_profile': "👤 প্রোফাইল",
        'btn_referrals': "👥 আমার রেফারেল",
        'btn_lang': "🌐 ভাষা / Language",
        'btn_support': "📞 সাপোর্ট / Support",
        'btn_cancel': "❌ Cancel",
        'action_cancelled': "👍 কাজ বাতিল করা হয়েছে।",
        'balance_info': "💰 **আপনার ওয়ালেট বিবরণ:**\n\nMain Balance: `${balance:.4f}`\nPending Balance: `${pending:.4f}`\n\n*(১০ দিন পেন্ডিং থাকার পর জয়েন টাস্কের টাকা মেইন ব্যালেন্সে যুক্ত হবে)*",
        'profile_info': "👤 **আপনার প্রোফাইল:**\n\n🆔 User ID: `{user_id}`\n🌐 বর্তমান ভাষা: {lang_name}\n📅 জয়েন তারিখ: {date}",
        'referral_info': "👥 **রেফারেল প্রোগ্রাম:**\n\n🔗 **আপনার রেফারেল লিংক:**\n`https://t.me/{bot_username}?start={user_id}`\n\n📊 মোট রেফারেল: {ref_count} জন\n\n💡 **নিয়ম:** আপনি যাকে রেফার করবেন, সে ১ম বার উইথড্র দিলে কেটে নেওয়া $0.02 ফি সরাসরি আপনার ব্যালেন্সে যোগ হবে!",
        'lang_select': "🌐 **আপনার পছন্দের ভাষা নির্বাচন করুন / Select Language:**",
        'lang_changed': "✅ ভাষা পরিবর্তন করা হয়েছে।",
        'tasks_title': "📋 **এভেলেবল কাজসমূহ (নিচের বাটন থেকে নির্বাচন করুন):**",
        'no_tasks': "❌ বর্তমানে কোনো কাজ নেই! নতুন কাজ আসলে জানিয়ে দেওয়া হবে।",
        'withdraw_select_method': "📥 **উইথড্র মেথড সিলেক্ট করুন:**",
        'withdraw_min_error': "❌ সর্বনিম্ন উইথড্র অ্যামাউন্ট ${min:.2f}। আপনার ব্যালেন্স: ${bal:.4f}",
        'withdraw_enter_addr': "🔹 আপনার {method} ওয়ালেট এড্রেসটি লিখে পাঠান:",
        'withdraw_enter_amount': "🔹 কত ডলার উইথড্র করতে চান লিখুন (সর্বনিম্ন ${min:.2f}):",
        'withdraw_success': "✅ **উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে!**\n\n💰 মোট উত্তোলনের পরিমাণ: `${amount:.4f}`\n🔻 ফি বা কমিশন কাটা হয়েছে: `${fee:.4f}`\n📥 আপনি পাবেন: `${net:.4f}`\n\nএডমিন প্যানেল থেকে রিভিউ করে পেমেন্ট সম্পন্ন করা হবে।",
        'insufficient_balance': "❌ আপনার একাউন্টে পর্যাপ্ত মেইন ব্যালেন্স নেই!",
        'banned_msg': "🚫 আপনার একাউন্টটি সাময়িকভাবে ব্লক করা হয়েছে।",
        'support_msg': "📞 **এডমিন সাপোর্ট:**\n\nযেকোনো সমস্যায় আমাদের অফিশিয়াল সাপোর্টে যোগাযোগ করুন:\n👉 {support_username}",
        
        'admin_menu': "⚙️ **ADMIN PANEL**\n\nনিচের যেকোনো অপশন বেছে নিন:",
        'admin_btn_users': "👥 ইউজার্স লিস্ট",
        'admin_btn_withdraws': "📥 পেন্ডিং উইথড্র",
        'admin_btn_add_task': "➕ টাস্ক এড করুন",
        'admin_btn_del_task': "❌ টাস্ক মুছে ফেলুন",
        'admin_btn_broadcast': "📢 ব্রডকাস্ট",
        'admin_btn_stats': "📊 স্ট্যাটস",
        'admin_btn_bonus': "🎁 বোনাস দিন",
        'admin_btn_ban': "🚫 ব্লক / আনব্লক"
    },
    'en': {
        'welcome': "👋 **Welcome!**\n\nEarn money by completing simple tasks. Please join our official channel to get started.",
        'must_join': "⚠️ You must join our official channel to use this bot!",
        'btn_join': "📢 Official Channel",
        'btn_verify': "✅ Verify",
        'verified_success': "🎉 Thank you! Verification successful.",
        'not_joined': "❌ You have not joined the channel yet! Please join and click verify.",
        'btn_balance': "💰 Balance",
        'btn_tasks': "📋 Tasks",
        'btn_withdraw': "📥 Withdraw",
        'btn_profile': "👤 Profile",
        'btn_referrals': "👥 My Referrals",
        'btn_lang': "🌐 Language / ভাষা",
        'btn_support': "📞 Support / সাপোর্ট",
        'btn_cancel': "❌ Cancel",
        'action_cancelled': "👍 Action cancelled.",
        'balance_info': "💰 **Your Wallet Details:**\n\nMain Balance: `${balance:.4f}`\nPending Balance: `${pending:.4f}`\n\n*(Pending task rewards unlock after 10 days)*",
        'profile_info': "👤 **Your Profile:**\n\n🆔 User ID: `{user_id}`\n🌐 Language: {lang_name}\n📅 Joined: {date}",
        'referral_info': "👥 **Referral Program:**\n\n🔗 **Your Referral Link:**\n`https://t.me/{bot_username}?start={user_id}`\n\n📊 Total Referrals: {ref_count}\n\n💡 **Rule:** When your referee makes their 1st withdrawal, the $0.02 fee deducted from them will automatically be added to your balance!",
        'lang_select': "🌐 **Select your preferred language:**",
        'lang_changed': "✅ Language updated successfully.",
        'tasks_title': "📋 **Available Tasks (Select from buttons below):**",
        'no_tasks': "❌ No tasks available right now! Check back later.",
        'withdraw_select_method': "📥 **Select Withdrawal Method:**",
        'withdraw_min_error': "❌ Minimum withdrawal is ${min:.2f}. Your balance:${bal:.4f}",
        'withdraw_enter_addr': "🔹 Enter your {method} wallet address:",
        'withdraw_enter_amount': "🔹 Enter withdrawal amount (Min ${min:.2f}):",
        'withdraw_success': "✅ **Withdrawal Request Submitted!**\n\n💰 Total Requested: `${amount:.4f}`\n🔻 Fee Deducted: `${fee:.4f}`\n📥 Net Received: `${net:.4f}`\n\nAdmin will review and process your request soon.",
        'insufficient_balance': "❌ Insufficient main balance!",
        'banned_msg': "🚫 Your account has been suspended.",
        'support_msg': "📞 **Admin Support:**\n\nContact our official support for any issues:\n👉 {support_username}",
        
        'admin_menu': "⚙️ **ADMIN PANEL**\n\nSelect an option below:",
        'admin_btn_users': "👥 Users List",
        'admin_btn_withdraws': "📥 Pending Withdraws",
        'admin_btn_add_task': "➕ Add Task",
        'admin_btn_del_task': "❌ Delete Task",
        'admin_btn_broadcast': "📢 Broadcast",
        'admin_btn_stats': "📊 Stats",
        'admin_btn_bonus': "🎁 Give Bonus",
        'admin_btn_ban': "🚫 Block / Unblock"
    }
}

# ================= HELPER FUNCTIONS =================
def get_user_lang(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['lang'] if row else 'bn'

def extract_channel_handle(link):
    if not link:
        return None
    clean_link = link.strip()
    if "?" in clean_link:
        clean_link = clean_link.split("?")[0]
    clean_link = clean_link.rstrip('/')
    
    if "t.me/" in clean_link:
        parts = clean_link.split("t.me/")[-1].split("/")
        handle = parts[0]
        if handle.startswith("+") or handle.startswith("joinchat"):
            return None
        if not handle.startswith("@"):
            return f"@{handle}"
        return handle
    elif clean_link.startswith("@"):
        return clean_link
    elif not clean_link.startswith("http"):
        return f"@{clean_link}"
    return None

# SMART VERIFICATION LOGIC FIX
def is_user_joined(user_id, channel_username):
    if not channel_username:
        return True
    try:
        member = bot.get_chat_member(channel_username, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        elif member.status in ['left', 'kicked']:
            return False
        return False
    except Exception as e:
        err_str = str(e).lower()
        # Telegaram explicitly confirms user is not in the chat
        if "user_not_participant" in err_str or "user not found" in err_str:
            return False
        # If bot lacks admin/access rights in third-party channels/groups, bypass restriction
        logging.warning(f"Verification bypassed for {user_id} in {channel_username}: {e}")
        return True

def check_user_access(user_id, chat_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    if row and row['is_banned']:
        if chat_id:
            try:
                bot.send_message(chat_id, t['banned_msg'])
            except Exception:
                pass
        return False

    if user_id == ADMIN_ID:
        return True

    if not is_user_joined(user_id, OFFICIAL_CHANNEL):
        if chat_id:
            try:
                markup = types.InlineKeyboardMarkup()
                btn1 = types.InlineKeyboardButton(t['btn_join'], url=f"https://t.me/{OFFICIAL_CHANNEL.replace('@','')}")
                btn2 = types.InlineKeyboardButton(t['btn_verify'], callback_data="verify_official_join")
                markup.add(btn1)
                markup.add(btn2)
                bot.send_message(chat_id, t['must_join'], reply_markup=markup)
            except Exception:
                pass
        return False

    return True

def get_main_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton(t['btn_balance']),
        types.KeyboardButton(t['btn_tasks']),
        types.KeyboardButton(t['btn_withdraw']),
        types.KeyboardButton(t['btn_profile']),
        types.KeyboardButton(t['btn_referrals']),
        types.KeyboardButton(t['btn_support']),
        types.KeyboardButton(t['btn_lang'])
    )
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ Admin Panel"))
    return markup

def get_cancel_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton(t['btn_cancel']))
    return markup

def get_admin_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton(t['admin_btn_users']),
        types.KeyboardButton(t['admin_btn_withdraws']),
        types.KeyboardButton(t['admin_btn_add_task']),
        types.KeyboardButton(t['admin_btn_del_task']),
        types.KeyboardButton(t['admin_btn_broadcast']),
        types.KeyboardButton(t['admin_btn_stats']),
        types.KeyboardButton(t['admin_btn_bonus']),
        types.KeyboardButton(t['admin_btn_ban']),
        types.KeyboardButton("🔙 Main Menu")
    )
    return markup

# ================= USER & FORCE JOIN HANDLERS =================
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row['is_banned']:
        lang = get_user_lang(user_id)
        bot.send_message(user_id, TEXTS[lang]['banned_msg'])
        conn.close()
        return

    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        ref_candidate = int(args[1])
        if ref_candidate != user_id:
            referrer_id = ref_candidate

    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, referrer_id, joined_at) VALUES (?, ?, ?)",
            (user_id, referrer_id, int(time.time()))
        )
        conn.commit()

    conn.close()
    
    if not check_user_access(user_id, message.chat.id):
        return

    lang = get_user_lang(user_id)
    bot.send_message(user_id, TEXTS[lang]['welcome'], reply_markup=get_main_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "verify_official_join")
def verify_official_join(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    if is_user_joined(user_id, OFFICIAL_CHANNEL):
        bot.answer_callback_query(call.id, t['verified_success'])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, t['welcome'], reply_markup=get_main_keyboard(user_id))
    else:
        bot.answer_callback_query(call.id, t['not_joined'], show_alert=True)

# ================= MAIN MENU ROUTING =================
@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    clean_text = text.lower()

    if not check_user_access(user_id, chat_id):
        return

    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    if "cancel" in clean_text or "বাতিল" in clean_text:
        USER_STATES.pop(user_id, None)
        bot.send_message(user_id, t['action_cancelled'], reply_markup=get_main_keyboard(user_id))
        return

    if text.startswith("📌 "):
        handle_selected_task_button(user_id, text)
        return

    if user_id in USER_STATES:
        process_user_state(message)
        return

    if "ব্যালেন্স" in text or "balance" in clean_text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance, pending_balance FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        msg = t['balance_info'].format(balance=u['balance'], pending=u['pending_balance'])
        bot.send_message(user_id, msg)

    elif "প্রোফাইল" in text or "profile" in clean_text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT joined_at FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        date_str = time.strftime('%Y-%m-%d', time.localtime(u['joined_at'])) if u else "N/A"
        lang_name = "বাংলা" if lang == 'bn' else "English"
        msg = t['profile_info'].format(user_id=user_id, lang_name=lang_name, date=date_str)
        bot.send_message(user_id, msg)

    elif "রেফারেল" in text or "referral" in clean_text:
        bot_info = bot.get_me()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE referrer_id = ?", (user_id,))
        count = cursor.fetchone()['cnt']
        conn.close()
        msg = t['referral_info'].format(bot_username=bot_info.username, user_id=user_id, ref_count=count)
        bot.send_message(user_id, msg)

    elif "সাপোর্ট" in text or "support" in clean_text:
        msg = t['support_msg'].format(support_username=SUPPORT_USERNAME)
        bot.send_message(user_id, msg)

    elif "ভাষা" in text or "language" in clean_text:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🇧🇩 বাংলা", callback_data="set_lang_bn"),
            types.InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")
        )
        bot.send_message(user_id, t['lang_select'], reply_markup=markup)

    elif "কাজ" in text or "tasks" in clean_text or "task" in clean_text:
        show_tasks_keyboard(user_id)

    elif "উত্তোলন" in text or "withdraw" in clean_text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()['balance']
        conn.close()

        if bal < MIN_WITHDRAW:
            bot.send_message(user_id, t['withdraw_min_error'].format(min=MIN_WITHDRAW, bal=bal))
            return

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("USDT (BEP-20)", callback_data="withdraw_meth_USDT (BEP-20)"),
            types.InlineKeyboardButton("Bkash / Nagad", callback_data="withdraw_meth_Bkash/Nagad")
        )
        bot.send_message(user_id, t['withdraw_select_method'], reply_markup=markup)

    elif "admin panel" in clean_text and user_id == ADMIN_ID:
        bot.send_message(user_id, t['admin_menu'], reply_markup=get_admin_keyboard(user_id))

    elif "main menu" in clean_text or "প্রধান মেনু" in text:
        bot.send_message(user_id, t['welcome'], reply_markup=get_main_keyboard(user_id))

    elif user_id == ADMIN_ID:
        handle_admin_buttons(message)

# ================= LANGUAGE TOGGLE CALLBACK =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def set_language_callback(call):
    user_id = call.from_user.id
    if not check_user_access(user_id, call.message.chat.id):
        return

    new_lang = call.data.split("_")[2]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, user_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, TEXTS[new_lang]['lang_changed'])
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(user_id, TEXTS[new_lang]['welcome'], reply_markup=get_main_keyboard(user_id))

# ================= TASKS SYSTEM =================
def show_tasks_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE status = 'active'")
    all_tasks = cursor.fetchall()
    
    cursor.execute("SELECT task_id FROM user_tasks WHERE user_id = ? AND status IN ('pending', 'warning', 'completed')", (user_id,))
    completed_task_ids = [row['task_id'] for row in cursor.fetchall()]
    conn.close()

    available_tasks = [task for task in all_tasks if task['id'] not in completed_task_ids]

    if not available_tasks:
        bot.send_message(user_id, t['no_tasks'], reply_markup=get_main_keyboard(user_id))
        return

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for task in available_tasks:
        title = task['title_bn'] if lang == 'bn' else task['title_en']
        btn_text = f"📌 {title} (${task['reward']:.4f})"
        markup.add(types.KeyboardButton(btn_text))
    
    markup.add(types.KeyboardButton(t['btn_cancel']))
    bot.send_message(user_id, t['tasks_title'], reply_markup=markup)

def handle_selected_task_button(user_id, button_text):
    lang = get_user_lang(user_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE status = 'active'")
    tasks = cursor.fetchall()
    conn.close()

    matched_task = None
    for task in tasks:
        title_bn = f"📌 {task['title_bn']} (${task['reward']:.4f})"
        title_en = f"📌 {task['title_en']} (${task['reward']:.4f})"
        if button_text in [title_bn, title_en]:
            matched_task = task
            break

    if matched_task:
        title = matched_task['title_bn'] if lang == 'bn' else matched_task['title_en']
        msg = f"📌 **{title}**\n\n💰 Reward: `${matched_task['reward']:.4f}`\n\n👉 Click below to complete task:"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Open Task Link", url=matched_task['link']))
        markup.add(types.InlineKeyboardButton("✅ Claim Reward", callback_data=f"claim_task_{matched_task['id']}"))
        bot.send_message(user_id, msg, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("claim_task_"))
def claim_task_callback(call):
    user_id = call.from_user.id
    if not check_user_access(user_id, call.message.chat.id):
        return

    task_id = int(call.data.split("_")[2])
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, status FROM user_tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
    existing_task = cursor.fetchone()

    if existing_task and existing_task['status'] in ['pending', 'warning', 'completed']:
        bot.answer_callback_query(call.id, "❌ Task already claimed!", show_alert=True)
        conn.close()
        return

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return

    channel_handle = extract_channel_handle(task['link'])
    if channel_handle and not is_user_joined(user_id, channel_handle):
        bot.answer_callback_query(call.id, f"❌ আপনি টাস্কের চ্যানেলে ({channel_handle}) জয়েন করেননি! আগে জয়েন করুন।", show_alert=True)
        conn.close()
        return

    matures_at = int(time.time()) + TEN_DAYS_SEC

    if existing_task and existing_task['status'] == 'penalized':
        cursor.execute(
            "UPDATE user_tasks SET reward = ?, matures_at = ?, status = 'pending', warning_at = 0 WHERE id = ?",
            (task['reward'], matures_at, existing_task['id'])
        )
    else:
        cursor.execute(
            "INSERT INTO user_tasks (user_id, task_id, reward, matures_at, status) VALUES (?, ?, ?, ?, 'pending')",
            (user_id, task_id, task['reward'], matures_at)
        )

    cursor.execute("UPDATE users SET pending_balance = pending_balance + ? WHERE user_id = ?", (task['reward'], user_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "✅ Task completed! Reward added to Pending Balance (Unlocks in 10 days).", show_alert=True)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_tasks_keyboard(user_id)

# ================= REJOIN VERIFY CALLBACK =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("rejoin_verify_"))
def handle_rejoin_verify(call):
    user_id = call.from_user.id
    if not check_user_access(user_id, call.message.chat.id):
        return

    ut_id = int(call.data.split("_")[2])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ut.id, ut.status, t.title_bn, t.title_en, t.link 
        FROM user_tasks ut 
        JOIN tasks t ON ut.task_id = t.id 
        WHERE ut.id = ? AND ut.user_id = ?
    ''', (ut_id, user_id))
    task = cursor.fetchone()

    if not task:
        bot.answer_callback_query(call.id, "❌ Task record not found!", show_alert=True)
        conn.close()
        return

    if task['status'] != 'warning':
        bot.answer_callback_query(call.id, "ℹ️ এই ওয়ার্নিংটি এখন আর কার্যকর নেই।", show_alert=True)
        conn.close()
        return

    channel_handle = extract_channel_handle(task['link'])
    if channel_handle and is_user_joined(user_id, channel_handle):
        cursor.execute("UPDATE user_tasks SET status = 'pending', warning_at = 0 WHERE id = ?", (ut_id,))
        conn.commit()
        conn.close()
        
        lang = get_user_lang(user_id)
        title = task['title_bn'] if lang == 'bn' else task['title_en']
        bot.answer_callback_query(call.id, "✅ রি-জয়েন সফল হয়েছে! আপনার ব্যালেন্স কাটা হয়নি।", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, f"✅ **ধন্যবাদ!** আপনি **{title}** চ্যানেলে সফলভাবে রি-জয়েন করেছেন। আপনার ব্যালেন্স অপরিবর্তিত আছে।")
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনও চ্যানেলে রি-জয়েন করেননি! আগে জয়েন করে বাটনে চাপুন।", show_alert=True)
        conn.close()

# ================= WITHDRAW SYSTEM =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("withdraw_meth_"))
def select_withdraw_method(call):
    user_id = call.from_user.id
    if not check_user_access(user_id, call.message.chat.id):
        return

    method = call.data.split("_")[2]
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    USER_STATES[user_id] = {'step': 'withdraw_addr', 'method': method}
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(user_id, t['withdraw_enter_addr'].format(method=method), reply_markup=get_cancel_keyboard(user_id))

def process_user_state(message):
    user_id = message.from_user.id
    state = USER_STATES.get(user_id)
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    text = message.text.strip()

    if state['step'] == 'withdraw_addr':
        state['address'] = text
        state['step'] = 'withdraw_amount'
        bot.send_message(user_id, t['withdraw_enter_amount'].format(min=MIN_WITHDRAW), reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'withdraw_amount':
        try:
            amount = float(text)
        except ValueError:
            bot.send_message(user_id, "❌ Valid number input করুন:")
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance, has_withdrawn_once, referrer_id FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()

        if amount < MIN_WITHDRAW or amount > u['balance']:
            bot.send_message(user_id, t['insufficient_balance'], reply_markup=get_main_keyboard(user_id))
            USER_STATES.pop(user_id, None)
            conn.close()
            return

        fee = WITHDRAW_FEE
        net_amount = amount - fee

        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute(
            "INSERT INTO withdrawals (user_id, method, address, amount, fee, net_amount, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, state['method'], state['address'], amount, fee, net_amount, int(time.time()))
        )

        if u['has_withdrawn_once'] == 0:
            cursor.execute("UPDATE users SET has_withdrawn_once = 1 WHERE user_id = ?", (user_id,))
            referrer_id = u['referrer_id']
            if referrer_id:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (WITHDRAW_FEE, referrer_id))
                try:
                    ref_msg = f"🎉 **Referral Bonus Received!**\n\nYour referred user (ID: `{user_id}`) made their 1st withdrawal! `${WITHDRAW_FEE:.4f}` fee bonus added to your balance."
                    bot.send_message(referrer_id, ref_msg)
                except Exception:
                    pass

        conn.commit()
        conn.close()

        success_msg = t['withdraw_success'].format(amount=amount, fee=fee, net=net_amount)
        bot.send_message(user_id, success_msg, reply_markup=get_main_keyboard(user_id))
        USER_STATES.pop(user_id, None)

    elif state['step'] == 'admin_add_task_bn':
        state['title_bn'] = text
        state['step'] = 'admin_add_task_en'
        bot.send_message(user_id, "🔹 Enter Task Title in English:", reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'admin_add_task_en':
        state['title_en'] = text
        state['step'] = 'admin_add_task_link'
        bot.send_message(user_id, "🔹 Enter Task Link (e.g. https://t.me/yourchannel):", reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'admin_add_task_link':
        state['link'] = text
        state['step'] = 'admin_add_task_reward'
        bot.send_message(user_id, "🔹 Enter Task Reward Amount ($):", reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'admin_add_task_reward':
        try:
            reward = float(text)
        except ValueError:
            bot.send_message(user_id, "❌ Enter a valid numeric amount:")
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title_bn, title_en, reward, link, task_type) VALUES (?, ?, ?, ?, 'telegram')",
            (state['title_bn'], state['title_en'], reward, state['link'])
        )
        conn.commit()
        conn.close()
        bot.send_message(user_id, "✅ Task added successfully!", reply_markup=get_admin_keyboard(user_id))
        USER_STATES.pop(user_id, None)

    elif state['step'] == 'admin_broadcast':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        sent, failed = 0, 0
        for u in users:
            try:
                bot.send_message(u['user_id'], text)
                sent += 1
            except Exception:
                failed += 1

        bot.send_message(user_id, f"✅ Broadcast Complete!\n\nSent: {sent}\nFailed: {failed}", reply_markup=get_admin_keyboard(user_id))
        USER_STATES.pop(user_id, None)

    elif state['step'] == 'admin_bonus_id':
        if not text.isdigit():
            bot.send_message(user_id, "❌ Valid User ID (numeric) লিখুন:")
            return
        state['target_id'] = int(text)
        state['step'] = 'admin_bonus_amount'
        bot.send_message(user_id, "🔹 কত ডলার বোনাস দিতে চান লিখুন (যেমন: 0.50):", reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'admin_bonus_amount':
        try:
            amount = float(text)
        except ValueError:
            bot.send_message(user_id, "❌ সঠিক সংখ্যা বসান (যেমন: 0.50):")
            return
        
        target_id = state['target_id']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (target_id,))
        if not cursor.fetchone():
            bot.send_message(user_id, f"❌ User ID `{target_id}` ডাটাবেজে পাওয়া যায়নি!", reply_markup=get_admin_keyboard(user_id))
            conn.close()
            USER_STATES.pop(user_id, None)
            return
        
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        conn.close()

        try:
            bot.send_message(target_id, f"🎉 **এডমিন আপনাকে ${amount:.4f} ডলার বোনাস দিয়েছেন!**")
        except Exception:
            pass

        bot.send_message(user_id, f"✅ User ID `{target_id}` কে `${amount:.4f}` ডলার বোনাস দেওয়া হয়েছে।", reply_markup=get_admin_keyboard(user_id))
        USER_STATES.pop(user_id, None)

    elif state['step'] == 'admin_toggle_ban_id':
        if not text.isdigit():
            bot.send_message(user_id, "❌ Valid User ID (numeric) লিখুন:")
            return
        
        target_id = int(text)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (target_id,))
        row = cursor.fetchone()
        
        if not row:
            bot.send_message(user_id, f"❌ User ID `{target_id}` ডাটাবেজে পাওয়া যায়নি!", reply_markup=get_admin_keyboard(user_id))
            conn.close()
            USER_STATES.pop(user_id, None)
            return

        new_ban_status = 0 if row['is_banned'] else 1
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (new_ban_status, target_id))
        conn.commit()
        conn.close()

        status_str = "ব্লক (Banned)" if new_ban_status else "আনব্লক (Unbanned)"
        bot.send_message(user_id, f"✅ User ID `{target_id}` সফলভাবে **{status_str}** করা হয়েছে।", reply_markup=get_admin_keyboard(user_id))
        USER_STATES.pop(user_id, None)

# ================= ADMIN PANEL HANDLERS =================
def handle_admin_buttons(message):
    user_id = message.from_user.id
    text = message.text.strip()
    clean_text = text.lower()

    if "ইউজার্স" in text or "users" in clean_text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, balance, is_banned FROM users LIMIT 20")
        users = cursor.fetchall()
        conn.close()

        msg = "👥 **BOT USERS LIST (Top 20):**\n\n"
        markup = types.InlineKeyboardMarkup()
        for u in users:
            status = "🚫 Banned" if u['is_banned'] else "✅ Active"
            msg += f"• ID: `{u['user_id']}` | Bal: `${u['balance']:.4f}` | {status}\n"
            markup.add(types.InlineKeyboardButton(f"💬 Direct Chat (ID: {u['user_id']})", url=f"tg://user?id={u['user_id']}"))

        bot.send_message(user_id, msg, reply_markup=markup)

    elif "উইথড্র" in text or "withdraws" in clean_text or "pending" in clean_text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM withdrawals WHERE status = 'pending'")
        withdraws = cursor.fetchall()
        conn.close()

        if not withdraws:
            bot.send_message(user_id, "✅ No pending withdrawal requests!")
            return

        for w in withdraws:
            w_msg = f"📥 **WITHDRAWAL REQUEST #{w['id']}**\n\n🆔 User ID: `{w['user_id']}`\n💳 Method: {w['method']}\n🏠 Address: `{w['address']}`\n💰 Total: `${w['amount']:.4f}`\n🔻 Fee: `${w['fee']:.4f}`\n📥 Net Pay: `${w['net_amount']:.4f}`"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"app_w_{w['id']}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_w_{w['id']}")
            )
            bot.send_message(user_id, w_msg, reply_markup=markup)

    elif "টাস্ক এড" in text or "add task" in clean_text:
        USER_STATES[user_id] = {'step': 'admin_add_task_bn'}
        bot.send_message(user_id, "🔹 Enter Task Title in Bangla:", reply_markup=get_cancel_keyboard(user_id))

    elif "টাস্ক মুছে" in text or "delete task" in clean_text or "del task" in clean_text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE status = 'active'")
        tasks = cursor.fetchall()
        conn.close()

        if not tasks:
            bot.send_message(user_id, "❌ মুছে ফেলার মতো কোনো সক্রিয় টাস্ক নেই!")
            return

        msg = "🗑️ **মুছে ফেলার জন্য টাস্ক নির্বাচন করুন:**"
        markup = types.InlineKeyboardMarkup()
        for t in tasks:
            markup.add(types.InlineKeyboardButton(f"❌ Delete #{t['id']}: {t['title_bn']}", callback_data=f"delete_task_{t['id']}"))
        bot.send_message(user_id, msg, reply_markup=markup)

    elif "ব্রডকাস্ট" in text or "broadcast" in clean_text:
        USER_STATES[user_id] = {'step': 'admin_broadcast'}
        bot.send_message(user_id, "📢 Enter message to broadcast to ALL users:", reply_markup=get_cancel_keyboard(user_id))

    elif "স্ট্যাটস" in text or "stats" in clean_text:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        u_cnt = cursor.fetchone()['total_users']
        cursor.execute("SELECT SUM(amount) as total_w FROM withdrawals WHERE status = 'approved'")
        w_sum = cursor.fetchone()['total_w'] or 0.0
        conn.close()

        stats_msg = f"📊 **BOT LIVE STATISTICS:**\n\n👥 Total Users: {u_cnt}\n💸 Total Paid Withdrawals: `${w_sum:.4f}`"
        bot.send_message(user_id, stats_msg)

    elif "বোনাস" in text or "bonus" in clean_text:
        USER_STATES[user_id] = {'step': 'admin_bonus_id'}
        bot.send_message(user_id, "🔹 যে ইউজারকে বোনাস দিতে চান তার **User ID** লিখুন:", reply_markup=get_cancel_keyboard(user_id))

    elif "ব্লক" in text or "ban" in clean_text or "unblock" in clean_text:
        USER_STATES[user_id] = {'step': 'admin_toggle_ban_id'}
        bot.send_message(user_id, "🔹 যে ইউজারকে ব্লক বা আনব্লক করতে চান তার **User ID** লিখুন:", reply_markup=get_cancel_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_task_"))
def handle_delete_task(call):
    if not check_user_access(call.from_user.id, call.message.chat.id):
        return
    task_id = int(call.data.split("_")[2])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 'deleted' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "✅ Task deleted successfully!")
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(("app_w_", "rej_w_")))
def handle_withdraw_approval(call):
    if not check_user_access(call.from_user.id, call.message.chat.id):
        return

    action, _, w_id = call.data.split("_")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (w_id,))
    w = cursor.fetchone()

    if action == "app":
        cursor.execute("UPDATE withdrawals SET status = 'approved' WHERE id = ?", (w_id,))
        bot.send_message(w['user_id'], f"🎉 Your withdrawal request of `${w['net_amount']:.4f}` has been approved!")
        bot.answer_callback_query(call.id, "Approved!")
    else:
        cursor.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (w_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (w['amount'], w['user_id']))
        bot.send_message(w['user_id'], f"❌ Your withdrawal request of `${w['amount']:.4f}` was rejected. Amount refunded to balance.")
        bot.answer_callback_query(call.id, "Rejected & Refunded!")

    conn.commit()
    conn.close()
    bot.delete_message(call.message.chat.id, call.message.message_id)

# ================= BACKGROUND THREAD FOR 10-DAY MATURITY =================
def auto_release_pending_rewards():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            now = int(time.time())
            
            cursor.execute("SELECT * FROM user_tasks WHERE status = 'pending' AND matures_at <= ?", (now,))
            matures = cursor.fetchall()

            for m in matures:
                cursor.execute("UPDATE users SET balance = balance + ?, pending_balance = pending_balance - ? WHERE user_id = ?", 
                               (m['reward'], m['reward'], m['user_id']))
                cursor.execute("UPDATE user_tasks SET status = 'completed' WHERE id = ?", (m['id'],))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error in auto_release_pending_rewards: {e}")
        time.sleep(60)

Thread(target=auto_release_pending_rewards, daemon=True).start()

# ================= BACKGROUND THREAD FOR TASK LEAVE MONITORING & 5-MIN GRACE TIMER =================
def check_task_leaving_and_penalty():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            now = int(time.time())
            
            cursor.execute('''
                SELECT ut.id as ut_id, ut.user_id, ut.task_id, ut.reward, ut.status as ut_status, 
                       t.title_bn, t.title_en, t.link 
                FROM user_tasks ut 
                JOIN tasks t ON ut.task_id = t.id 
                WHERE ut.status IN ('pending', 'completed') AND ut.matures_at > ?
            ''', (now,))
            active_tasks = cursor.fetchall()

            for ut in active_tasks:
                u_id = ut['user_id']
                channel_handle = extract_channel_handle(ut['link'])
                
                if channel_handle and not is_user_joined(u_id, channel_handle):
                    cursor.execute("UPDATE user_tasks SET status = 'warning', warning_at = ? WHERE id = ?", (now, ut['ut_id']))
                    conn.commit()
                    
                    u_lang = get_user_lang(u_id)
                    task_title = ut['title_bn'] if u_lang == 'bn' else ut['title_en']
                    warn_msg = (
                        f"⚠️ **সতর্কবার্তা / Warning!**\n\n"
                        f"আপনি **{task_title}** চ্যানেল থেকে বের হয়ে গেছেন!\n\n"
                        f"⏳ আপনার কাছে **৫ মিনিট** সময় আছে পুনরায় জয়েন করার জন্য।\n"
                        f"৫ মিনিটের মধ্যে রি-জয়েন না করলে ব্যালেন্স থেকে `${ut['reward']:.4f}` কেটে নেওয়া হবে।"
                    )
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔄 রি-জয়েন ভেরিফাই করুন", callback_data=f"rejoin_verify_{ut['ut_id']}"))
                    try:
                        bot.send_message(u_id, warn_msg, reply_markup=markup)
                    except Exception:
                        pass

            cursor.execute('''
                SELECT ut.id as ut_id, ut.user_id, ut.task_id, ut.reward, ut.warning_at, ut.status as ut_status,
                       t.title_bn, t.title_en, t.link 
                FROM user_tasks ut 
                JOIN tasks t ON ut.task_id = t.id 
                WHERE ut.status = 'warning'
            ''')
            warning_tasks = cursor.fetchall()

            for ut in warning_tasks:
                u_id = ut['user_id']
                channel_handle = extract_channel_handle(ut['link'])
                
                if channel_handle and is_user_joined(u_id, channel_handle):
                    cursor.execute("UPDATE user_tasks SET status = 'pending', warning_at = 0 WHERE id = ?", (ut['ut_id'],))
                    conn.commit()
                    u_lang = get_user_lang(u_id)
                    task_title = ut['title_bn'] if u_lang == 'bn' else ut['title_en']
                    try:
                        bot.send_message(u_id, f"✅ **ধন্যবাদ!** আপনি **{task_title}** চ্যানেলে সফলভাবে রি-জয়েন করেছেন। আপনার ব্যালেন্স অপরিবর্তিত রয়েছে।")
                    except Exception:
                        pass
                
                elif now - ut['warning_at'] >= 300:
                    reward = ut['reward']
                    cursor.execute("SELECT balance, pending_balance FROM users WHERE user_id = ?", (u_id,))
                    user_row = cursor.fetchone()
                    
                    if user_row:
                        bal = user_row['balance']
                        p_bal = user_row['pending_balance']
                        new_p_bal = max(0.0, p_bal - reward)
                        overflow = (reward - p_bal) if reward > p_bal else 0.0
                        new_bal = max(0.0, bal - overflow)
                        
                        cursor.execute("UPDATE users SET pending_balance = ?, balance = ? WHERE user_id = ?", 
                                       (new_p_bal, new_bal, u_id))
                    
                    cursor.execute("UPDATE user_tasks SET status = 'penalized' WHERE id = ?", (ut['ut_id'],))
                    conn.commit()

                    u_lang = get_user_lang(u_id)
                    task_title = ut['title_bn'] if u_lang == 'bn' else ut['title_en']
                    try:
                        bot.send_message(u_id, f"❌ **সময় পার হয়ে গেছে!** আপনি ৫ মিনিটের মধ্যে **{task_title}** চ্যানেলে রি-জয়েন না করায় `${reward:.4f}` ডলার কেটে নেওয়া হলো।")
                    except Exception:
                        pass

            conn.close()
        except Exception as e:
            logging.error(f"Error in task leaving penalty check: {e}")
        
        time.sleep(30)

Thread(target=check_task_leaving_and_penalty, daemon=True).start()

# ================= BOT RUNNER =================
if __name__ == "__main__":
    print("🤖 Bot started with updated smart verification logic...")
    bot.infinity_polling()
