import telebot
from telebot import types
import sqlite3
import threading
import time

# --- CONFIGURATION ---
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # লাইন ৮: আপনার Bot Token
ADMIN_ID = 8808647263              # লাইন ৯: আপনার Numeric Telegram User ID (কোটেশন ছাড়া)
SUPPORT_NUMBER = "01720616501"

# অফিশিয়াল গ্রুপ/চ্যানেল কনফিগারেশন (বোটকে এই গ্রুপে Admin বানাতে হবে)
OFFICIAL_CHANNEL = "@ClickEarnProOfficial" 
OFFICIAL_LINK = "https://t.me/ClickEarnProOfficial"

bot = telebot.TeleBot(BOT_TOKEN)

# --- HELPER FUNCTIONS ---
def is_admin(user_id):
    try:
        return int(user_id) == int(ADMIN_ID)
    except:
        return False

# অফিশিয়াল গ্রুপে ইউজার জয়েন করেছে কিনা চেক করা
def check_force_sub(user_id):
    if is_admin(user_id):
        return True
    try:
        member = bot.get_chat_member(OFFICIAL_CHANNEL, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"Force Sub Check Error: {e}")
        return False

# জয়েন না থাকলে সেন্ড করার মেসেজ
def send_force_sub_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_join = types.InlineKeyboardButton("📢 Join Official Group", url=OFFICIAL_LINK)
    btn_check = types.InlineKeyboardButton("✅ Verify / চেষ্টা করুন", callback_data="check_subscription")
    markup.add(btn_join)
    markup.add(btn_check)
    
    msg = (
        "⚠️ **বোটটি ব্যবহার করতে আপনাকে অবশ্যই আমাদের অফিশিয়াল গ্রুপে জয়েন করতে হবে!**\n\n"
        "নিচের '📢 Join Official Group' বাটনে ক্লিক করে অফিশিয়াল গ্রুপে জয়েন করুন এবং '✅ Verify' বাটনে চাপ দিন।"
    )
    bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)

# --- MULTI-LANGUAGE DICTIONARY ---
LANG = {
    'BN': {
        'welcome': "টাস্ক অ্যান্ড আর্ন বোটে আপনাকে স্বাগতম!",
        'profile': "👤 **ইউজার প্রোফাইল**\n\n🆔 ইউআইডি (UID): `{user_id}`\n💰 ব্যালেন্স: ${balance:.4f}\n🌐 ভাষা: বাংলা",
        'balance': "💵 আপনার বর্তমান ব্যালেন্স: ${balance:.4f}",
        'support': f"📞 অফিশিয়াল সাপোর্ট টেলিগ্রাম: {SUPPORT_NUMBER}",
        'lang_changed': "🌐 ভাষা পরিবর্তন করে 'বাংলা' করা হয়েছে!",
        'min_withdraw': "❌ সর্বনিম্ন উইথড্র পরিমাণ $0.20!\nআপনার বর্তমান ব্যালেন্স: ${balance:.4f}",
        'enter_withdraw_amount': "💸 **উইথড্র প্রসেস**\n\n• সর্বনিম্ন উইথড্র: $0.20\n• উইথড্র ফি: $0.02\n\nআপনি কত ডলার ($) উইথড্র করতে চান লিখুন:",
        'enter_withdraw_address': "💳 **USDT (BEP20 / Binance)** ওয়ালেট এড্রেসটি সেন্ড করুন:",
        'withdraw_success': "✅ আপনার উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে!\n\n💰 পরিমাণ: ${amount:.2f}\n🏷️ ফি: $0.02\n💳 ওয়ালেট (BEP20): `{address}`\n\nএডমিন শীঘ্রই পেমেন্ট এপ্রুভ করবেন।",
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
        'min_withdraw': "❌ Minimum withdrawal amount is $0.20!\nYour current balance:${balance:.4f}",
        'enter_withdraw_amount': "💸 **Withdrawal Process**\n\n• Minimum Withdraw: $0.20\n• Withdrawal Fee: $0.02\n\nEnter the amount ($) you want to withdraw:",
        'enter_withdraw_address': "💳 Send your **USDT (BEP20 / Binance)** Wallet Address:",
        'withdraw_success': "✅ Your withdrawal request has been submitted!\n\n💰 Amount: ${amount:.2f}\n🏷️ Fee: $0.02\n💳 Wallet (BEP20): `{address}`\n\nAdmin will review and approve soon.",
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            fee REAL DEFAULT 0.02,
            address TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

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
    if is_admin(user_id):
        markup.add('⚙️ Admin Panel')
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('➕ Add Task', '📊 View Users')
    markup.add('🎁 Give Bonus', '⚠️ Suspicious Users')
    markup.add('💸 Withdraw Requests', '📜 Withdraw History')
    markup.add('✉️ Message User', '🚫 Block User', '✅ Unblock User')
    markup.add('🔙 User Panel')
    return markup

# --- BACKGROUND MONITORING (10 Days Channel Leave Detection) ---
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
                            "❌ আপনি চ্যানেল থেকে লিভ নিয়েছেন!\n"
                            f"আপনার অ্যাকাউন্ট থেকে ${reward:.2f} কেটে নেওয়া হয়েছে।\n\n"
                            "⚠️ সর্তকতা: পুনরায় এমন করলে অ্যাকাউন্ট ব্যান করা হবে।"
                        )
                        bot.send_message(user_id, msg)
                except Exception:
                    pass
            conn.close()
        except Exception as e:
            print(f"Monitoring Error: {e}")

threading.Thread(target=monitor_channel_leavers, daemon=True).start()

# --- COMMANDS ---
@bot.message_handler(commands=['start', 'admin'])
def start_cmd(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id):
        return
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    # অফিশিয়াল গ্রুপ জয়েন ভেরিফিকেশন
    if not check_force_sub(user_id):
        send_force_sub_msg(user_id)
        return

    if message.text == '/admin' and is_admin(user_id):
        bot.send_message(user_id, "⚙️ **এডমিন প্যানেলে স্বাগতম:**", parse_mode='Markdown', reply_markup=get_admin_keyboard())
    else:
        lang = get_user_lang(user_id)
        bot.send_message(user_id, LANG[lang]['welcome'], reply_markup=get_user_keyboard(user_id))

# --- CALLBACK HANDLER FOR FORCE SUB CHECK ---
@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def handle_check_subscription(call):
    user_id = call.from_user.id
    if check_force_sub(user_id):
        bot.answer_callback_query(call.id, "✅ ধন্যবাদ! আপনি সফলভাবে জয়েন করেছেন।", show_alert=True)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        lang = get_user_lang(user_id)
        bot.send_message(user_id, LANG[lang]['welcome'], reply_markup=get_user_keyboard(user_id))
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো অফিশিয়াল গ্রুপে জয়েন করেননি! আগে জয়েন করুন।", show_alert=True)

# --- MAIN MESSAGE HANDLER ---
@bot.message_handler(func=lambda msg: not is_user_blocked(msg.from_user.id))
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text

    # অফিশিয়াল গ্রুপে জয়েন না থাকলে মেসেজ আটকে দিবে
    if not check_force_sub(user_id):
        send_force_sub_msg(user_id)
        return

    lang = get_user_lang(user_id)
    t = LANG[lang]

    # ADMIN TOGGLE BUTTONS
    if text == '⚙️ Admin Panel' and is_admin(user_id):
        bot.send_message(user_id, "⚙️ **এডমিন প্যানেলে স্বাগতম:**", parse_mode='Markdown', reply_markup=get_admin_keyboard())
        return
    elif text == '🔙 User Panel' and is_admin(user_id):
        bot.send_message(user_id, "👤 **ইউজার প্যানেলে ফিরে এসেছেন:**", reply_markup=get_user_keyboard(user_id))
        return

    # USER PANEL COMMANDS
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

    elif text in ['🌐 Language (Language)', '🌐 Language (ভাষা)', '🌐 Language', '🌐 ভাষা (Language)']:
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
            msg = bot.send_message(user_id, t['enter_withdraw_amount'], parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_withdraw_amount)

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

    # ADMIN PANEL COMMANDS
    elif is_admin(user_id):
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
                res += f"• UID: `{uid}` | Bal: ${bal:.4f} | Status: {status}\n"
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
                res += f"• UID: `{uid}` | Bal: ${bal:.4f}\n"
            bot.send_message(user_id, res, parse_mode='Markdown')

        elif text == '💸 Withdraw Requests':
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, amount, fee, address, created_at FROM withdrawals WHERE status = 'PENDING'")
            pending = cursor.fetchall()
            conn.close()

            if not pending:
                bot.send_message(user_id, "✅ কোনো পেন্ডিং উইথড্র রিকোয়েস্ট নেই।")
                return

            for req_id, uid, amt, fee, addr, created in pending:
                markup = types.InlineKeyboardMarkup()
                btn_app = types.InlineKeyboardButton("✅ Approve", callback_data=f"wd_app_{req_id}")
                btn_rej = types.InlineKeyboardButton("❌ Reject", callback_data=f"wd_rej_{req_id}")
                markup.add(btn_app, btn_rej)

                msg_text = (
                    f"💸 **উইথড্র রিকোয়েস্ট ID: #{req_id}**\n\n"
                    f"🆔 User UID: `{uid}`\n"
                    f"💰 Amount: ${amt:.2f}\n"
                    f"🏷️ Fee: ${fee:.2f}\n"
                    f"💳 USDT (BEP20 / Binance): `{addr}`\n"
                    f"📅 Date: {created}"
                )
                bot.send_message(user_id, msg_text, parse_mode='Markdown', reply_markup=markup)

        elif text == '📜 Withdraw History':
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, amount, address, created_at FROM withdrawals WHERE status = 'APPROVED' ORDER BY id DESC LIMIT 15")
            history = cursor.fetchall()
            conn.close()

            if not history:
                bot.send_message(user_id, "📜 কোনো এপ্রুভড উইথড্র হিস্ট্রি নেই।")
                return

            res = "📜 **এপ্রুভড উইথড্র হিস্ট্রি:**\n\n"
            for req_id, uid, amt, addr, created in history:
                res += f"• ID: #{req_id} | UID: `{uid}` | ${amt:.2f}\n  Address: `{addr}`\n  Time: {created}\n\n"
            bot.send_message(user_id, res[:4000], parse_mode='Markdown')

        elif text == '🎁 Give Bonus':
            msg = bot.send_message(user_id, "১. যাকে বোনাস দিতে চান তার **Numeric UID** টি পাঠান:")
            bot.register_next_step_handler(msg, process_bonus_step1)

        elif text == '✉️ Message User':
            msg = bot.send_message(user_id, "মেসেজ পাঠাতে ইউজারের **Numeric UID** টি লিখুন:")
            bot.register_next_step_handler(msg, process_msg_step1)

        elif text == '🚫 Block User':
            msg = bot.send_message(user_id, "ব্লক করতে ইউজারের **Numeric User ID** দিন:")
            bot.register_next_step_handler(msg, process_block_user)

        elif text == '✅ Unblock User':
            msg = bot.send_message(user_id, "আনব্লক করতে ইউজারের **Numeric User ID** দিন:")
            bot.register_next_step_handler(msg, process_unblock_user)

# --- WITHDRAW STEP 1: AMOUNT ---
def process_withdraw_amount(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    t = LANG[lang]
    try:
        amount = float(message.text.strip())
        fee = 0.02
        if amount < 0.20:
            bot.send_message(user_id, "❌ সর্বনিম্ন $0.20 উইথড্র করা যাবে!")
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()[0]
        conn.close()

        if bal < (amount + fee):
            bot.send_message(user_id, f"❌ পর্যাপ্ত ব্যালেন্স নেই! প্রয়োজন: ${amount + fee:.2f} (ফি $0.02 সহ)")
            return

        msg = bot.send_message(user_id, t['enter_withdraw_address'], parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_withdraw_address, amount)
    except ValueError:
        bot.send_message(user_id, "❌ সঠিক সংখ্যার পরিমাণ দিন!")

# --- WITHDRAW STEP 2: ADDRESS ---
def process_withdraw_address(message, amount):
    user_id = message.from_user.id
    address = message.text.strip()
    fee = 0.02
    lang = get_user_lang(user_id)
    t = LANG[lang]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    bal = cursor.fetchone()[0]

    if bal < (amount + fee):
        bot.send_message(user_id, "❌ পর্যাপ্ত ব্যালেন্স নেই!")
        conn.close()
        return

    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount + fee, user_id))
    cursor.execute("INSERT INTO withdrawals (user_id, amount, fee, address, status) VALUES (?, ?, ?, ?, 'PENDING')",
                   (user_id, amount, fee, address))
    conn.commit()
    conn.close()

    bot.send_message(user_id, t['withdraw_success'].format(amount=amount, address=address), parse_mode='Markdown')
    if ADMIN_ID:
        bot.send_message(ADMIN_ID, f"🔔 **নতুন উইথড্র রিকোয়েস্ট এসেছে!**\n\n🆔 User UID: `{user_id}`\n💰 Amount: ${amount:.2f}\n💳 USDT (BEP20): `{address}`", parse_mode='Markdown')

# --- WITHDRAW APPROVE / REJECT CALLBACKS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('wd_app_', 'wd_rej_')))
def handle_withdraw_callback(call):
    if not is_admin(call.from_user.id):
        return

    action, req_id = call.data.split('_')[1], int(call.data.split('_')[2])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, fee, address, status FROM withdrawals WHERE id = ?", (req_id,))
    req = cursor.fetchone()

    if not req or req[4] != 'PENDING':
        bot.answer_callback_query(call.id, "এই রিকোয়েস্টটি ইতোমধ্যেই প্রসেস করা হয়েছে!", show_alert=True)
        conn.close()
        return

    uid, amt, fee, addr, status = req

    if action == 'app':
        cursor.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (req_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ Payment Approved!", show_alert=True)
        bot.edit_message_text(f"✅ **APPROVED** (ID: #{req_id})\nUser: `{uid}` | Amount: ${amt:.2f}\nWallet: `{addr}`", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.send_message(uid, f"🎉 **আপনার উইথড্র পেমেন্ট সফল হয়েছে!**\n\n💰 পরিমাণ: ${amt:.2f}\n💳 ওয়ালেট: `{addr}`", parse_mode='Markdown')

    elif action == 'rej':
        cursor.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (req_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt + fee, uid))
        conn.commit()
        bot.answer_callback_query(call.id, "❌ Payment Rejected & Balance Refunded!", show_alert=True)
        bot.edit_message_text(f"❌ **REJECTED** (ID: #{req_id})\nUser: `{uid}` | Amount: ${amt:.2f}\nBalance Refunded.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.send_message(uid, f"❌ **আপনার উইথড্র রিকোয়েস্টটি রিজেক্ট করা হয়েছে!**\n\n${amt + fee:.2f} ডলার আপনার ব্যালেন্সে রিফান্ড করা হয়েছে।", parse_mode='Markdown')

    conn.close()

# --- BONUS TWO STEP HANDLERS ---
def process_bonus_step1(message):
    try:
        target_id = int(message.text.strip())
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (target_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            bot.send_message(ADMIN_ID, f"❌ UID `{target_id}` এর কোনো ইউজার পাওয়া যায়নি!", parse_mode='Markdown')
            return

        msg = bot.send_message(ADMIN_ID, f"২. ইউজার `{target_id}` কে কত ডলার বোনাস দিতে চান তা লিখুন:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_bonus_step2, target_id)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ সঠিক Numeric User ID দিন!")

def process_bonus_step2(message, target_id):
    try:
        amount = float(message.text.strip())
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        conn.close()

        bot.send_message(ADMIN_ID, f"✅ ইউজার `{target_id}` কে ${amount:.2f} বোনাস দেওয়া হয়েছে!", parse_mode='Markdown')
        bot.send_message(target_id, f"🎉 **অভিনন্দন!** আপনি এডমিন থেকে ${amount:.2f} বোনাস পেয়েছেন!", parse_mode='Markdown')
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ সঠিক সংখ্যার পরিমাণ লিখুন!")

# --- MESSAGE USER TWO STEP HANDLERS ---
def process_msg_step1(message):
    try:
        target_id = int(message.text.strip())
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (target_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            bot.send_message(ADMIN_ID, f"❌ UID `{target_id}` এর কোনো ইউজার পাওয়া যায়নি!", parse_mode='Markdown')
            return

        msg = bot.send_message(ADMIN_ID, f"ইউজার `{target_id}` কে যে মেসেজ পাঠাতে চান তা লিখুন:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_msg_step2, target_id)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ সঠিক Numeric User ID দিন!")

def process_msg_step2(message, target_id):
    sms_text = message.text
    try:
        bot.send_message(target_id, f"📩 **Message from Support/Admin:**\n\n{sms_text}", parse_mode='Markdown')
        bot.send_message(ADMIN_ID, f"✅ ইউজার `{target_id}` এর ইনবক্সে মেসেজ সফলভাবে পাঠানো হয়েছে!", parse_mode='Markdown')
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ মেসেজ পাঠানো যায়নি! (User bot block করে থাকতে পারে)। Error: {e}")

# --- TASK & USER MANAGEMENT HANDLERS ---
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
        bot.send_message(ADMIN_ID, "❌ ফরম্যাট ভুল হয়েছে! সঠিক ফরম্যাট: `Channel_ID Link Reward`")

def process_block_user(message):
    try:
        target_id = int(message.text.strip())
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"🚫 ইউজার `{target_id}` কে ব্লক করা হয়েছে।", parse_mode='Markdown')
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ সঠিক Numeric User ID দিন!")

def process_unblock_user(message):
    try:
        target_id = int(message.text.strip())
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, f"✅ ইউজার `{target_id}` কে আনব্লক করা হয়েছে।", parse_mode='Markdown')
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ সঠিক Numeric User ID দিন!")

# --- CALLBACK HANDLER FOR TASK VERIFICATION ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_'))
def handle_verification(call):
    user_id = call.from_user.id
    task_id = int(call.data.split('_')[1])

    if is_user_blocked(user_id):
        return

    if not check_force_sub(user_id):
        send_force_sub_msg(user_id)
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

# --- START BOT ---
print("Bot is running...")
bot.infinity_polling()
