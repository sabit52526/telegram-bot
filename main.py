import time
import sqlite3
import threading
import telebot
from telebot import types

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8967409217:AAH8_LX9fVuDCxdyNmEE9q-XCVydywFljKw"  # Ekhane apnar bot token boshaben
ADMIN_ID = 8808647263               # Apnar Admin ID
SUPPORT_NUMBER = "01720616501"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ==================== DATABASE SETUP ====================
def get_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            language TEXT DEFAULT 'bn',
            is_blocked INTEGER DEFAULT 0,
            is_suspicious INTEGER DEFAULT 0
        )
    ''')
    
    # Tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            channel_link TEXT,
            reward REAL
        )
    ''')
    
    # User completed tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            reward_given REAL,
            joined_timestamp INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ==================== HELPER FUNCTIONS ====================
def is_blocked(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res and res['is_blocked'] == 1

def register_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# ==================== KEYBOARDS ====================
def user_menu(lang='bn'):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == 'bn':
        markup.add("💼 Task", "💰 Balance")
        markup.add("👤 Profile", "🌐 Language")
        markup.add("💸 Withdraw", "📞 Support")
    else:
        markup.add("💼 Task", "💰 Balance")
        markup.add("👤 Profile", "🌐 Language")
        markup.add("💸 Withdraw", "📞 Support")
    return markup

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Add Task", "📊 View Users")
    markup.add("🎁 Give Bonus", "⚠️ Suspicious Users")
    markup.add("🚫 Block User", "✅ Unblock User")
    return markup

# ==================== USER HANDLERS ====================
@bot.message_handler(commands=['start', 'admin'])
def start_cmd(message):
    user_id = message.from_user.id
    register_user(user_id)
    
    if is_blocked(user_id):
        return

    if message.text == '/admin' and user_id == ADMIN_ID:
        bot.send_message(user_id, "<b>👨‍✈️ Admin Panel Activated:</b>", reply_markup=admin_menu())
        return

    user = get_user(user_id)
    welcome_msg = (
        "<b>Shagotom amader earning bot e!</b>\n\n"
        "Nicher menu theke apnar kankhito option select korun."
        if user['language'] == 'bn' else
        "<b>Welcome to our Earning Bot!</b>\n\n"
        "Select an option from the menu below."
    )
    bot.send_message(user_id, welcome_msg, reply_markup=user_menu(user['language']))

@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    if is_blocked(user_id):
        return

    register_user(user_id)
    text = message.text
    user = get_user(user_id)
    lang = user['language']

    # --- USER PANEL BUTTONS ---
    if text == "👤 Profile":
        msg = (
            f"<b>👤 Apnar Profile:</b>\n\n"
            f"<b>🆔 User UID:</b> <code>{user_id}</code>\n"
            f"<b>💵 Balance:</b> ${user['balance']:.2f}\n"
            f"<b>🌐 Language:</b> {'Bangla' if lang == 'bn' else 'English'}"
        )
        bot.send_message(user_id, msg)

    elif text == "💰 Balance":
        bot.send_message(user_id, f"💰 <b>Bortoman Balance:</b> ${user['balance']:.2f}")

    elif text == "📞 Support":
        msg = (
            f"📞 <b>Support Center:</b>\n\n"
            f"Jekono proyojone jogajog korun:\n"
            f"Telegram: <code>{SUPPORT_NUMBER}</code>"
        )
        bot.send_message(user_id, msg)

    elif text == "🌐 Language":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🇧🇩 Bangla", callback_data="lang_bn"),
            types.InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
        )
        bot.send_message(user_id, "Pochonder bhasha select korun / Select Language:", reply_markup=markup)

    elif text == "💸 Withdraw":
        if user['balance'] < 0.20:
            bot.send_message(user_id, "❌ <b>Nyunotomo withdraw $0.20।</b> Apnar porjapto balance nei.")
        else:
            msg = (
                f"💸 <b>Withdraw System</b>\n\n"
                f"• Sorbonimno withdraw: <b>$0.20</b>\n"
                f"• Proti withdraw fee: <b>$0.02</b>\n\n"
                f"Apnar poriman likhe reply din (Jemon: 0.50):"
            )
            bot_msg = bot.send_message(user_id, msg)
            bot.register_next_step_handler(bot_msg, process_withdraw)

    elif text == "💼 Task":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks WHERE task_id NOT IN (
                SELECT task_id FROM user_tasks WHERE user_id = ?
            )
        """, (user_id,))
        tasks = cursor.fetchall()
        conn.close()

        if not tasks:
            bot.send_message(user_id, "❌ Bortomane kono notun task nei!")
            return

        for task in tasks:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔗 Join Group/Channel", url=task['channel_link']))
            markup.add(types.InlineKeyboardButton("✅ Verify Join", callback_data=f"check_{task['task_id']}"))
            
            bot.send_message(
                user_id,
                f"📌 <b>Notun Task:</b>\n"
                f"💰 Reward: <b>${task['reward']:.2f}</b>\n\n"
                f"Nicher link e join kore Verify button e click korun.",
                reply_markup=markup
            )

    # --- ADMIN PANEL BUTTONS ---
    elif user_id == ADMIN_ID:
        if text == "➕ Add Task":
            msg = bot.send_message(user_id, "Channel/Group er Chat ID, Link, ebong Reward ebhabe din:\n<code>@channelid|https://t.me/example|0.05</code>")
            bot.register_next_step_handler(msg, process_add_task)

        elif text == "📊 View Users":
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            all_users = cursor.fetchall()
            conn.close()

            report = "<b>📊 User List:</b>\n\n"
            for u in all_users[:20]:
                report += f"• UID: <code>{u['user_id']}</code> | Balance: ${u['balance']:.2f} | Blocked: {u['is_blocked']}\n"
            bot.send_message(user_id, report)

        elif text == "⚠️ Suspicious Users":
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE is_suspicious = 1")
            s_users = cursor.fetchall()
            conn.close()

            if not s_users:
                bot.send_message(user_id, "✅ Kono shondehojonok user pawa jayni.")
            else:
                msg = "<b>⚠️ Shondehojonok User-gon:</b>\n\n"
                for u in s_users:
                    msg += f"• UID: <code>{u['user_id']}</code> | Balance: ${u['balance']:.2f}\n"
                bot.send_message(user_id, msg)

        elif text == "🚫 Block User":
            msg = bot.send_message(user_id, "Block korte chaoa user er **UID (Numerical ID)** din:")
            bot.register_next_step_handler(msg, process_block_user)

        elif text == "✅ Unblock User":
            msg = bot.send_message(user_id, "Unblock korte chaoa user er **UID (Numerical ID)** din:")
            bot.register_next_step_handler(msg, process_unblock_user)

        elif text == "🎁 Give Bonus":
            msg = bot.send_message(user_id, "User ID ebong Bonus ebhabe din:\n<code>USER_ID|AMOUNT</code> (Jemon: 123456|0.10)")
            bot.register_next_step_handler(msg, process_give_bonus)

# ==================== CALLBACK QUERY HANDLER ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    if is_blocked(user_id):
        return

    if call.data.startswith("lang_"):
        new_lang = call.data.split("_")[1]
        conn = get_db()
        conn.cursor().execute("UPDATE users SET language = ? WHERE user_id = ?", (new_lang, user_id))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Language Updated!")
        bot.send_message(user_id, "Language poribortito hoyeche!", reply_markup=user_menu(new_lang))

    elif call.data.startswith("check_"):
        task_id = int(call.data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task = cursor.fetchone()

        if not task:
            bot.answer_callback_query(call.id, "Task-ti pawa jayni!", show_alert=True)
            conn.close()
            return

        try:
            member = bot.get_chat_member(task['channel_id'], user_id)
            if member.status in ['creator', 'administrator', 'member']:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (task['reward'], user_id))
                cursor.execute("INSERT INTO user_tasks (user_id, task_id, reward_given, joined_timestamp) VALUES (?, ?, ?, ?)",
                               (user_id, task_id, task['reward'], int(time.time())))
                conn.commit()
                bot.answer_callback_query(call.id, "✅ Shofolbhabe verified hoyeche! Reward jog kora hoyeche.", show_alert=True)
                bot.delete_message(call.message.chat.id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "❌ Apni ekhono group e join korhenni!", show_alert=True)
        except Exception:
            bot.answer_callback_query(call.id, "❌ Verification bartho! Bot-ti oi group e Admin ache kina check korun.", show_alert=True)
        conn.close()

# ==================== NEXT STEP HANDLERS ====================
def process_add_task(message):
    try:
        channel_id, link, reward = message.text.split("|")
        conn = get_db()
        conn.cursor().execute("INSERT INTO tasks (channel_id, channel_link, reward) VALUES (?, ?, ?)",
                              (channel_id.strip(), link.strip(), float(reward.strip())))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Notun task shofolbhabe jukto kora hoyeche!")
    except Exception:
        bot.send_message(message.chat.id, "❌ Format bhul chilo! Kaj batil kora hoyeche.")

def process_block_user(message):
    try:
        uid = int(message.text.strip())
        conn = get_db()
        conn.cursor().execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🚫 User <code>{uid}</code> ke block kora hoyeche.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid User ID!")

def process_unblock_user(message):
    try:
        uid = int(message.text.strip())
        conn = get_db()
        conn.cursor().execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ User <code>{uid}</code> ke unblock kora hoyeche.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Invalid User ID!")

def process_give_bonus(message):
    try:
        uid, amt = message.text.split("|")
        uid, amt = int(uid.strip()), float(amt.strip())
        conn = get_db()
        conn.cursor().execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, uid))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🎁 User <code>{uid}</code> ke ${amt} bonus dewa hoyeche.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Bhul input!")

def process_withdraw(message):
    try:
        amt = float(message.text.strip())
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if amt < 0.20:
            bot.send_message(user_id, "❌ Sorbonimno withdraw $0.20 hote hobe.")
            return
        
        total_deduct = amt + 0.02
        if user['balance'] < total_deduct:
            bot.send_message(user_id, f"❌ Apnar porjapto balance nei. (Fee shoh mot lagbe ${total_deduct:.2f})")
            return
        
        conn = get_db()
        conn.cursor().execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_deduct, user_id))
        conn.commit()
        conn.close()

        bot.send_message(user_id, f"✅ Apnar ${amt:.2f} withdraw request shofolbhabe submit hoyeche! (Fee: $0.02)")
        bot.send_message(ADMIN_ID, f"🔔 **Notun Withdraw Request:**\nUID: <code>{user_id}</code>\nAmount: ${amt:.2f}")
    except Exception:
        bot.send_message(message.chat.id, "❌ Onko-ti shotikbhabe likhun.")

# ==================== AUTOMATED BACKEND LEAVE DETECTOR ====================
def background_leave_checker():
    """10 diner vetor user leave nile balance katar system"""
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # 10 days = 864000 seconds
            ten_days_ago = int(time.time()) - (10 * 86400)
            
            cursor.execute("""
                SELECT ut.id, ut.user_id, ut.task_id, ut.reward_given, t.channel_id 
                FROM user_tasks ut
                JOIN tasks t ON ut.task_id = t.task_id
                WHERE ut.joined_timestamp > ?
            """, (ten_days_ago,))
            
            records = cursor.fetchall()
            
            for row in records:
                try:
                    member = bot.get_chat_member(row['channel_id'], row['user_id'])
                    if member.status in ['left', 'kicked']:
                        cursor.execute("UPDATE users SET balance = balance - ?, is_suspicious = 1 WHERE user_id = ?", 
                                       (row['reward_given'], row['user_id']))
                        cursor.execute("DELETE FROM user_tasks WHERE id = ?", (row['id'],))
                        conn.commit()
                        
                        msg = (
                            f"⚠️ <b>Spam Warning!</b>\n\n"
                            f"You have left the group/channel, so <b>${row['reward_given']:.2f}</b> has been deducted from your balance.\n"
                            f"<i>Repeatedly doing this will cause your account to be permanently banned.</i>"
                        )
                        bot.send_message(row['user_id'], msg)
                except Exception:
                    pass
            
            conn.close()
        except Exception as e:
            print(f"Checker Error: {e}")
            
        time.sleep(1800)

threading.Thread(target=background_leave_checker, daemon=True).start()

# ==================== BOT START ====================
if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
