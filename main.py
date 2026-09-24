import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# --- CONFIGURATION ---
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"      # আপনার বটের টোকেন দিন
ADMIN_ID = 8808647263                            # আপনার নিজের টেলিগ্রাম ইউজারের numeric ID দিন
OFFICIAL_CHANNEL = "@ClickEarnProOfficial"       # আপনার বটের অফিশিয়াল মাস্ট-জয়েন চ্যানেল আইডি
SUPPORT_PHONE = "01720616501"                   # এডমিন সাপোর্ট নম্বর
DOLLAR_RATE = 120.0                             # ১ ডলার = ১২০ টাকা
WITHDRAW_FEE = 0.02                             # ফিক্সড উইথড্র ফি $0.02
REFERRAL_REWARD_ON_WITHDRAW = 0.01              # উইথড্রকালে রেফারার বোনাস $0.01

# --- MULTI-LANGUAGE DICTIONARY ---
LANG_TEXTS = {
    'bn': {
        'welcome': "👋 স্বাগতম! আমাদের বট ব্যবহার করতে অবশ্যই আগে অফিশিয়াল চ্যানেলে জয়েন করুন:",
        'tasks': "📋 টাস্ক সমূহ", 'balance': "💰 মাই ব্যালেন্স", 'withdraw': "💳 উইথড্র",
        'referral': "👥 রেফার", 'lang': "🌐 ভাষা (Language)", 'support': "📞 সাপোর্ট",
        'cancel': "❌ Cancel", 'cancelled': "👌 অ্যাকশন বাতিল করা হয়েছে।",
        'must_join': "⚠️ আগে আমাদের অফিশিয়াল চ্যানেলে জয়েন করে 'Check' বাটনে চাপ দিন!",
        'blocked': "⛔ আপনার একাউন্টটি সাময়িকভাবে স্থগিত করা হয়েছে। শুধুমাত্র সাপোর্টে যোগাযোগ করতে পারবেন।"
    },
    'en': {
        'welcome': "👋 Welcome! You must join our Official Channel to use the bot:",
        'tasks': "📋 Tasks", 'balance': "💰 Balance", 'withdraw': "💳 Withdraw",
        'referral': "👥 Referral", 'lang': "🌐 Language", 'support': "📞 Support",
        'cancel': "❌ Cancel", 'cancelled': "👌 Action cancelled.",
        'must_join': "⚠️ Please join our official channel first and click Check!",
        'blocked': "⛔ Your account is suspended. You can only contact Support."
    },
    'es': {'welcome': "👋 ¡Bienvenido! Únete al canal oficial:", 'tasks': "📋 Tareas", 'balance': "💰 Saldo", 'withdraw': "💳 Retirar", 'referral': "👥 Referidos", 'lang': "🌐 Idioma", 'support': "📞 Soporte", 'cancel': "❌ Cancel", 'cancelled': "👌 Cancelado.", 'must_join': "⚠️ ¡Únete al canal primero!", 'blocked': "⛔ Cuenta suspendida."},
    'pt': {'welcome': "👋 Bem-vindo! Junte-se ao canal oficial:", 'tasks': "📋 Tarefas", 'balance': "💰 Saldo", 'withdraw': "💳 Sacar", 'referral': "👥 Referência", 'lang': "🌐 Idioma", 'support': "📞 Suporte", 'cancel': "❌ Cancel", 'cancelled': "👌 Cancelado.", 'must_join': "⚠️ Junte-se ao canal primeiro!", 'blocked': "⛔ Conta suspensa."},
    'hi': {'welcome': "👋 स्वागत है! बोट का उपयोग करने के लिए ऑफिशियल चैनल ज्वाइन करें:", 'tasks': "📋 कार्य (Tasks)", 'balance': "💰 बैलेंस", 'withdraw': "💳 निकालें", 'referral': "👥 रेफ़रल", 'lang': "🌐 भाषा", 'support': "📞 सहायता", 'cancel': "❌ Cancel", 'cancelled': "👌 रद्द किया गया।", 'must_join': "⚠️ कृपया पहले चैनल ज्वाइन करें!", 'blocked': "⛔ आपका खाता निलंबित कर दिया गया है।"},
    'ur': {'welcome': "👋 خوش آمدید! بوٹ استعمال کرنے کے لیے آفیشل چینل جوائن کریں:", 'tasks': "📋 ٹاسکس", 'balance': "💰 بیلنس", 'withdraw': "💳 نکالیں", 'referral': "👥 ریفرل", 'lang': "🌐 زبان", 'support': "📞 سپورٹ", 'cancel': "❌ Cancel", 'cancelled': "👌 منسوخ کر دیا گیا۔", 'must_join': "⚠️ پہلے آفیشل چینل جوائن کریں!", 'blocked': "⛔ آپ کا اکاؤنٹ معطل کر دیا گیا ہے۔"}
}

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("earning_bot.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        balance REAL DEFAULT 0.0,
                        language TEXT DEFAULT 'bn',
                        is_blocked INTEGER DEFAULT 0,
                        referred_by INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        link TEXT,
                        reward REAL,
                        channel_id TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (
                        user_id INTEGER,
                        task_id INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- DATABASE HELPER FUNCTIONS ---
def get_user(user_id):
    conn = sqlite3.connect("earning_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, language, is_blocked, referred_by FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_balance(user_id, amount):
    conn = sqlite3.connect("earning_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- CHECK MUST JOIN CHANNEL ---
async def check_channel_member(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        member = await context.bot.get_chat_member(chat_id=OFFICIAL_CHANNEL, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except Exception:
        return True

# --- MAIN MENU BUILDER ---
def get_main_menu(lang='bn'):
    t = LANG_TEXTS.get(lang, LANG_TEXTS['bn'])
    keyboard = [
        [InlineKeyboardButton(t['tasks'], callback_data="view_tasks")],
        [InlineKeyboardButton(t['balance'], callback_data="my_balance"), InlineKeyboardButton(t['withdraw'], callback_data="withdraw_menu")],
        [InlineKeyboardButton(t['referral'], callback_data="referral"), InlineKeyboardButton(t['lang'], callback_data="change_lang")],
        [InlineKeyboardButton(t['support'], url=f"https://t.me/+88{SUPPORT_PHONE}"), InlineKeyboardButton(t['cancel'], callback_data="universal_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = f"@{user.username}" if user.username else user.first_name

    args = context.args
    ref_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None

    conn = sqlite3.connect("earning_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, ref_by))
    conn.commit()
    conn.close()

    u_data = get_user(user_id)
    if u_data and u_data[2] == 1: # SILENT BLOCK CHECK
        keyboard = [[InlineKeyboardButton("📞 Support", url=f"https://t.me/+88{SUPPORT_PHONE}")]]
        await update.message.reply_text("⛔ Your account is suspended.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Check mandatory official channel
    is_joined = await check_channel_member(context, user_id)
    if not is_joined:
        keyboard = [
            [InlineKeyboardButton("📢 Join Official Channel", url=f"https://t.me/{OFFICIAL_CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("✅ Check / Verify", callback_data="check_mandatory")]
        ]
        await update.message.reply_text(LANG_TEXTS['bn']['must_join'], reply_markup=InlineKeyboardMarkup(keyboard))
        return

    lang = u_data[1] if u_data else 'bn'
    await update.message.reply_text(LANG_TEXTS[lang]['welcome'], reply_markup=get_main_menu(lang))

# --- CALLBACK HANDLER ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    u_data = get_user(user_id)
    if u_data and u_data[2] == 1: # SILENT BLOCK (Ignores all clicks)
        return

    lang = u_data[1] if u_data else 'bn'
    t = LANG_TEXTS.get(lang, LANG_TEXTS['bn'])

    if query.data == "universal_cancel":
        await query.edit_message_text(t['cancelled'], reply_markup=get_main_menu(lang))
        return

    if query.data == "check_mandatory":
        if await check_channel_member(context, user_id):
            await query.edit_message_text(t['welcome'], reply_markup=get_main_menu(lang))
        else:
            await query.answer(t['must_join'], show_alert=True)
        return

    # VIEW TASKS (Taskly UI Style with Cancel)
    if query.data == "view_tasks":
        conn = sqlite3.connect("earning_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE task_id NOT IN (SELECT task_id FROM completed_tasks WHERE user_id = ?)", (user_id,))
        tasks = cursor.fetchall()
        conn.close()

        if not tasks:
            await query.edit_message_text("❌ No available tasks right now.", reply_markup=get_main_menu(lang))
            return

        keyboard = []
        for task in tasks:
            t_id, title, link, reward, _ = task
            keyboard.append([InlineKeyboardButton(f"📢 {title} (${reward:.4f})", callback_data=f"dotask_{t_id}")])
        
        keyboard.append([InlineKeyboardButton(t['cancel'], callback_data="universal_cancel")])
        await query.edit_message_text("👇 Select a task to complete:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("dotask_"):
        t_id = int(query.data.split("_")[1])
        conn = sqlite3.connect("earning_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (t_id,))
        task = cursor.fetchone()
        conn.close()

        if task:
            _, title, link, reward, ch_id = task
            # AUTO STRICT VERIFY LOGIC
            is_valid = True
            if ch_id and ch_id != "none":
                try:
                    m = await context.bot.get_chat_member(chat_id=ch_id, user_id=user_id)
                    if m.status in ['left', 'kicked']:
                        is_valid = False
                except Exception:
                    is_valid = False

            if not is_valid:
                keyboard = [
                    [InlineKeyboardButton("🔗 Join Channel", url=link)],
                    [InlineKeyboardButton("✅ Verify Again", callback_data=f"dotask_{t_id}")],
                    [InlineKeyboardButton(t['cancel'], callback_data="universal_cancel")]
                ]
                await query.edit_message_text("❌ Strict Verification Failed! You have not joined the channel yet.", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                conn = sqlite3.connect("earning_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)", (user_id, t_id))
                conn.commit()
                conn.close()

                update_balance(user_id, reward)
                await query.edit_message_text(f"🎉 Task Completed! Added ${reward:.4f} to your balance.", reply_markup=get_main_menu(lang))

    # WITHDRAW WITH STRICT ZERO-LOSS RE-VERIFICATION
    elif query.data == "withdraw_menu":
        balance = u_data[0] if u_data else 0.0
        
        # Zero-loss check: Verify if user left previously completed channels
        conn = sqlite3.connect("earning_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, channel_id, reward FROM tasks WHERE task_id IN (SELECT task_id FROM completed_tasks WHERE user_id = ?)", (user_id,))
        completed = cursor.fetchall()
        
        cheated_penalty = 0.0
        for tid, ch_id, rew in completed:
            if ch_id and ch_id != "none":
                try:
                    m = await context.bot.get_chat_member(chat_id=ch_id, user_id=user_id)
                    if m.status in ['left', 'kicked']:
                        cheated_penalty += rew
                        cursor.execute("DELETE FROM completed_tasks WHERE user_id = ? AND task_id = ?", (user_id, tid))
                except Exception:
                    pass
        conn.commit()
        conn.close()

        if cheated_penalty > 0:
            update_balance(user_id, -cheated_penalty)
            await query.answer(f"⚠️ Penalty! You left channels. Deducted ${cheated_penalty:.2f}", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("🔶 Binance (Min $0.20)", callback_data="withdraw_binance")],
            [InlineKeyboardButton("📱 bKash (Min $1.00)", callback_data="withdraw_bikash")],
            [InlineKeyboardButton(t['cancel'], callback_data="universal_cancel")]
        ]
        await query.edit_message_text(f"💳 Balance: ${balance:.2f}\nWithdraw Fee: $0.02", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data in ["withdraw_binance", "withdraw_bikash"]:
        is_bin = query.data == "withdraw_binance"
        min_lim = 0.20 if is_bin else 1.00
        balance = u_data[0]
        
        if balance < min_lim:
            await query.answer(f"❌ Minimum withdraw is ${min_lim:.2f}", show_alert=True)
            return

        net = balance - WITHDRAW_FEE
        if u_data[3]: # Referral reward trigger
            update_balance(u_data[3], REFERRAL_REWARD_ON_WITHDRAW)

        update_balance(user_id, -balance)
        msg = f"✅ Withdraw Submitted!\nMethod: {'Binance' if is_bin else 'bKash'}\nTotal: ${balance:.2f}\nFee: $0.02\nYou get: " + (f"${net:.2f}" if is_bin else f"{net*DOLLAR_RATE:.2f} BDT")
        await query.edit_message_text(msg, reply_markup=get_main_menu(lang))

    # LANGUAGE SELECTION MENU
    elif query.data == "change_lang":
        keyboard = [
            [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="setlang_bn"), InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
            [InlineKeyboardButton("🇪🇸 Español", callback_data="setlang_es"), InlineKeyboardButton("🇵🇹 Português", callback_data="setlang_pt")],
            [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="setlang_hi"), InlineKeyboardButton("🇵🇰 اردو", callback_data="setlang_ur")],
            [InlineKeyboardButton(t['cancel'], callback_data="universal_cancel")]
        ]
        await query.edit_message_text("🌐 Select Language / ভাষা নির্বাচন করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("setlang_"):
        new_l = query.data.split("_")[1]
        conn = sqlite3.connect("earning_bot.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (new_l, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Language Updated!", reply_markup=get_main_menu(new_l))

# --- ADMIN COMMANDS & SUSPICIOUS DETECTOR ---
async def admin_addtask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        data = " ".join(context.args).split("|")
        conn = sqlite3.connect("earning_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (title, link, reward, channel_id) VALUES (?, ?, ?, ?)",
                       (data[0].strip(), data[1].strip(), float(data[2].strip()), data[3].strip()))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Task added successfully!")
    except Exception:
        await update.message.reply_text("Format: `/addtask Title | Link | Reward | @channel_id`", parse_mode="Markdown")

async def admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    target_id = int(context.args[0])
    conn = sqlite3.connect("earning_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"⛔ User {target_id} has been silently blocked!")

async def admin_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    target_id = int(context.args[0])
    conn = sqlite3.connect("earning_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ User {target_id} unblocked!")

async def admin_suspicious(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = sqlite3.connect("earning_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users WHERE username IS NULL OR username = ''")
    sus_users = cursor.fetchall()
    conn.close()

    msg = "⚠️ **Suspicious Accounts (No Username):**\n\n"
    for uid, uname in sus_users:
        msg += f"🆔 `{uid}` | 🔴 Risk: High (No Username)\n/block {uid}\n\n"
    await update.message.reply_text(msg if sus_users else "✅ No suspicious users detected.", parse_mode="Markdown")

# --- MAIN RUNNER ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtask", admin_addtask))
    app.add_handler(CommandHandler("block", admin_block))
    app.add_handler(CommandHandler("unblock", admin_unblock))
    app.add_handler(CommandHandler("suspicious", admin_suspicious))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.run_polling()

if __name__ == "__main__":
    main()
