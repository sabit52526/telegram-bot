import telebot
from telebot import types
import sqlite3
import threading
import time

# --- CONFIGURATION ---
BOT_TOKEN = "8967409217:AAE-G3g_y1TodUFZzF-gU_S1163NhC23vtg"  # এখানে আপনার আসল Bot Token বসাবেন
ADMIN_ID =  8808647263            # এখানে আপনার নিজের Numeric Telegram User ID বসাবেন
SUPPORT_NUMBER = "01720616501"

bot = telebot.TeleBot(BOT_TOKEN)

# --- MULTI-LANGUAGE DICTIONARY ---
LANG = {
    'BN': {
        'welcome': "টাস্ক অ্যান্ড আর্ন বোটে আপনাকে স্বাগতম!",
        'profile': "👤 **ইউজার প্রোফাইল**\n\n🆔 ইউআইডি (UID): `{user_id}`\n💰 ব্যালেন্স: ${balance:.4f}\n🌐 ভাষা: বাংলা",
        'balance': "💵 আপনার বর্তমান ব্যালেন্স: ${balance:.4f}",
        'support': f"📞 অফিশিয়াল সাপোর্ট টেলিগ্রাম: {SUPPORT_NUMBER}",
        'lang_changed': "🌐 ভাষা পরিবর্তন করে 'বাংলা' করা হয়েছে!",
        'min_withdraw': "❌ সর্বনিম্ন উইথড্র পরিমাণ $0.20!\nআপনার ব্যালেন্স: ${balance:.4f}",
        'enter_withdraw': "সর্বনিম্ন উইথড্র: $0.20\nউইথড্র ফি: $0.02\n\nআপনি কত ডলার উইথড্র করতে চান তা লিখুন:",
        'no_tasks': "❌ বর্তমানে কোনো নতুন টাস্ক খালি নেই!",
        'btn_task': '📋 টাস্ক',
        'btn_balance': '💰 ব্যালেন্স',
        'btn_profile': '👤 প্রোফাইল',
        'btn_withdraw': '💸 উইথড্র',
        'btn_lang': '🌐 ভাষা (Language)',
        'btn_support': '💬 সাপোর্ট'
    },
    'EN': {
        'welcome': "Welcome to Task & Earn Bot!",
        'profile': "👤 **User Profile**\n\n🆔 UID: `{user_id}`\n💰 Balance: ${balance:.4f}\n🌐 Language: English",
        'balance': "💵 Current Balance: ${balance:.4f}",
        'support': f"📞 Official Support Telegram: {SUPPORT_NUMBER}",
        'lang_changed': "🌐 Language changed to 'English'!",
        'min_withdraw': "❌ Minimum withdrawal amount is $0.20!\nYour balance:${balance:.4f}",
        'enter_withdraw': "Minimum Withdraw: $0.20\nWithdrawal Fee: $0.02\n\nEnter the amount you want to withdraw:",
        'no_tasks': "❌ Currently no new tasks available!",
        'btn_task': '📋 Task',
        'btn_balance': '💰 Balance',
        'btn_profile': '👤 Profile',
        'btn_withdraw': '💸 Withdraw',
        'btn_lang': '🌐 Language (ভাষা)',
        'btn_support': '💬 Support'
    }
}

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            language TEXT DEFAULT 'BN',
            is_blocked INTEGER DEFAULT 0,
            is_suspicious INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            channel_link TEXT,
            reward REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            user_id INTEGER,
            task_id INTEGER,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, task_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def get_db():
    return sqlite3.connect('bot_database.db')

def is_user_blocked(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] == 1 if row else False

def get_user_lang(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 'BN'

# --- KEYBOARDS ---
def get_user_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = LANG[lang]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(t['btn_task'], t['btn_balance'])
    markup.add(t['btn_profile'], t['btn_withdraw'])
    markup.add(t['btn_lang'], t['btn_support'])
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('➕ Add Task', '📊 View Users')
    markup.add('🎁 Give Bonus', '⚠️ Suspicious Users')
    markup.add('🚫 Block User', '✅ Unblock User')
    return markup

# --- BACKGROUND MONITORING (10 Days Leave Detection) ---
def monitor_channel_leavers():
    while True:
        try:
            time.sleep(3600)
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ut.user_id, ut.task_id, t.channel_id, t.reward 
                FROM user_tasks ut
                JOIN tasks t ON ut.task_id = t.task_id
                WHERE strftime('%s', 'now') - strftime('%s', ut.joined_at) <= 864000
            ''')
            records = cursor.fetchall()
            for user_id, task_id, channel_id, reward in records:
                try:
                    member = bot.get_chat_member(channel_id, user_id)
                    if member.status in ['left', 'kicked']:
                        cursor.execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (reward, user_id))
                        cursor.execute("DELETE FROM user_tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
                        cursor.execute("UPDATE users SET is_suspicious = 1 WHERE user_id = ?", (user_id,))
                        conn.commit()
                        
                        msg = (
                            "❌ আপনি চ্যানেল থেকে লিভ (Leave) নিয়েছেন!\n"
                            f"আপনার অ্যাকাউন্ট থেকে ${reward:.2f} কেটে নেওয়া হয়েছে।\n\n"
                            "⚠️ সর্তকতা: পুনরায় এমন করলে অ্যাকাউন্ট ব্লক করা হবে।"
                        )
                        bot.send_message(user_id, msg)
                except Exception:
                    pass
            conn.close()
        except Exception as e:
            print(f"Monitoring Error: {e}")

threading.Thread(target=monitor_channel_leavers, daemon=True).start()

# --- COMMANDS ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id):
        return
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    lang = get_user_lang(user_id)
    bot.send_message(user_id, LANG[lang]['welcome'], reply_markup=get_user_keyboard(user_id))

@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        bot.send_message(user_id, "⚙️ **এডমিন প্যানেলে স্বাগতম:**", parse_mode='Markdown', reply_markup=get_admin_keyboard())

# --- MAIN MESSAGE HANDLER ---
@bot.message_handler(func=lambda msg: not is_user_blocked(msg.from_user.id))
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text
    lang = get_user_lang(user_id)
    t = LANG[lang]

    # --- USER PANEL COMMANDS ---
    if text in ['👤 Profile', '👤 প্রোফাইল']:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()[0]
        conn.close()
        bot.send_message(user_id, t['profile'].format(user_id=user_id, balance=bal), parse_mode='Markdown')

    elif text in ['💰 Balance', '💰 ব্যালেন্স']:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()[0]
        conn.close()
        bot.send_message(user_id, t['balance'].format(balance=bal))

    elif text in ['💬 Support', '💬 সাপোর্ট']:
        bot.send_message(user_id, t['support'])

    elif text in ['🌐 Language (Language)', '🌐 Language (ভাষা)', '🌐 Language']:
        new_lang = 'EN' if lang == 'BN' else 'BN'
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (new_lang, user_id))
        conn.commit()
        conn.close()
        bot.send_message(user_id, LANG[new_lang]['lang_changed'], reply_markup=get_user_keyboard(user_id))

    elif text in ['💸 Withdraw', '💸 উইথড্র']:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()[0]
        conn.close()

        if bal < 0.20:
            bot.send_message(user_id, t['min_withdraw'].format(balance=bal))
        else:
            msg = bot.send_message(user_id, t['enter_withdraw'])
            bot.register_next_step_handler(msg, process_withdraw)

    elif text in ['📋 Task', '📋 টাস্ক']:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT task_id, channel_link, reward FROM tasks 
            WHERE task_id NOT IN (SELECT task_id FROM user_tasks WHERE user_id = ?)
        ''', (user_id,))
        available_tasks = cursor.fetchall()
        conn.close()

        if not available_tasks:
            bot.send_message(user_id, t['no_tasks'])
            return

        for task_id, link, reward in available_tasks:
            markup = types.InlineKeyboardMarkup()
            btn_join = types.InlineKeyboardButton("➡️ Join Channel", url=link)
            btn_verify = types.InlineKeyboardButton("✅ Verify Join", callback_data=f"verify_{task_id}")
            markup.add(btn_join)
            markup.add(btn_verify)
            
            task_msg = f"📌 **Task:** Join channel & earn ${reward:.3f}\n🔗 {link}" if lang == 'EN' else f"📌 **টাস্ক:** চ্যানেলে জয়েন করে আয় করুন ${reward:.3f}\n🔗 {link}"
            bot.send_message(user_id, task_msg, reply_markup=markup, parse_mode='Markdown')

    # --- ADMIN PANEL COMMANDS ---
    elif user_id == ADMIN_ID:
        if text == '➕ Add Task':
            msg = bot.send_message(user_id, "টাস্ক যোগ করতে এই ফরম্যাটে পাঠান:\n`Channel_ID Channel_Link Reward`\n\nউদাহরণ:\n`@mychannel https://t.me/mychannel 0.05`", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_add_task)

        elif text == '📊 View Users':
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, balance, is_blocked, is_suspicious FROM users")
            users = cursor.fetchall()
            conn.close()
            
            res = "📊 **ইউজার তালিকা:**\n\n"
            for uid, bal, block, susp in users:
                status = "Blocked" if block else ("Suspicious" if susp else "Active")
                res += f"• UID: `{uid}` | Bal: ${bal:.2f} | Status: {status}\n"
            bot.send_message(user_id, res[:4000], parse_mode='Markdown')

        elif text == '⚠️ Suspicious Users':
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, balance FROM users WHERE is_suspicious = 1")
            users = cursor.fetchall()
            conn.close()
            
            if not users:
                bot.send_message(user_id, "✅ কোনো সন্দেহভাজন ইউজার পাওয়া যায়নি।")
                return

            res = "⚠️ **সন্দেহভাজন ইউজার তালিকা:**\n\n"
            for uid, bal in users:
                res += f"• UID: `{uid}` | Bal: ${bal:.2f}\n"
            bot.send_message(user_id, res, parse_mode='Markdown')

        elif text == '🚫 Block User':
            msg = bot.send_message(user_id, "ব্লক করতে ইউজারের Numeric User ID দিন:")
            bot.register_next_step_handler(msg, process_block_user)

        elif text == '✅ Unblock User':
            msg = bot.send_message(user_id, "আনব্লক করতে ইউজারের Numeric User ID দিন:")
            bot.register_next_step_handler(msg, process_unblock_user)

        elif text == '🎁 Give Bonus':
            msg = bot.send_message(user_id, "ইউজার আইডি এবং বোনাসের পরিমাণ একসাথে লিখুন:\nউদাহরণ: `123456789 0.50`", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_give_bonus)

# --- WITHDRAW PROCESS ---
def process_withdraw(message):
    user_id = message.from_user.id
    try:
        amount = float(message.text)
        fee = 0.02
        if amount < 0.20:
            bot.send_message(user_id, "❌ সর্বনিম্ন $0.20 উইথড্র করতে হবে!")
            return
            
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()[0]

        if bal < (amount + fee):
            bot.send_message(user_id, f"❌ পর্যাপ্ত ব্যালেন্স নেই! প্রয়োজন: ${amount + fee:.2f} (ফি $0.02 সহ)")
            conn.close()
            return

        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount + fee, user_id))
        conn.commit()
        conn.close()

        bot.send_message(user_id, f"✅ ${amount:.2f} উইথড্র রিকোয়েস্ট সফল হয়েছে! ($0.02 ফি কাটা হয়েছে)")
        bot.send_message(ADMIN_ID, f"🔔 **নতুন উইথড্র রিকোয়েস্ট**\nUser UID: `{user_id}`\nAmount: ${amount:.2f}", parse_mode='Markdown')
    except ValueError:
        bot.send_message(user_id, "❌ সঠিক সংখ্যার পরিমাণ দিন!")

# --- CALLBACK HANDLER FOR TASK VERIFICATION ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_'))
def handle_verification(call):
    user_id = call.from_user.id
    task_id = int(call.data.split('_')[1])

    if is_user_blocked(user_id):
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, reward FROM tasks WHERE task_id = ?", (task_id,))
    task = cursor.fetchone()

    if not task:
        bot.answer_callback_query(call.id, "টাস্কটি আর বিদ্যমান নেই!", show_alert=True)
        conn.close()
        return

    channel_id, reward = task

    try:
        member = bot.get_chat_member(channel_id, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            cursor.execute("INSERT INTO user_tasks (user_id, task_id) VALUES (?, ?)", (user_id, task_id))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
            conn.commit()
            
            bot.answer_callback_query(call.id, f"✅ ভেরিফাইড! ${reward:.3f} যুক্ত হয়েছে।", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "❌ ভেরিফাই করা যাচ্ছে না! বোটকে চ্যানেলে Admin বানিয়েছেন কি না নিশ্চিত করুন।", show_alert=True)
    
    conn.close()

# --- ADMIN FUNCTIONS ---
def process_add_task(message):
    try:
        parts = message.text.split()
        channel_id, link, reward = parts[0], parts[1], float(parts[2])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (channel_id, channel_link, reward) VALUES (?, ?, ?)", (channel_id, link, reward))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"✅ টাস্ক সফলভাবে যুক্ত হয়েছে! পুরস্কার: ${reward:.3f}")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ ফরম্যাট ভুল হয়েছে! ফরম্যাট: `Channel_ID Link Reward`")

def process_block_user(message):
    try:
        target_id = int(message.text)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"🚫 ইউজার {target_id} কে ব্লক করা হয়েছে।")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ সঠিক Numeric User ID দিন!")

def process_unblock_user(message):
    try:
        target_id = int(message.text)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"✅ ইউজার {target_id} কে আনব্লক করা হয়েছে।")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ সঠিক Numeric User ID দিন!")

def process_give_bonus(message):
    try:
        parts = message.text.split()
        target_id, amount = int(parts[0]), float(parts[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"🎁 ইউজার {target_id} কে ${amount:.2f} বোনাস দেওয়া হয়েছে!")
        bot.send_message(target_id, f"🎉 আপনি এডমিন থেকে ${amount:.2f} বোনাস পেয়েছেন!")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ ফরম্যাট ভুল! সঠিক নিয়ম: `UID Amount`")

# --- START BOT ---
print("Bot is running...")
bot.infinity_polling()
