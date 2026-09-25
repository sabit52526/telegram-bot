Telegram Earning Bot
=====================
Stack: python-telegram-bot==20.7, Flask==3.0.0, gunicorn, sqlite3
Designed to run 24/7 on Render's free web-service tier via a small
Flask keep-alive server running alongside the bot's polling loop.

Run locally:      python bot.py
Deploy on Render: see README.md (uses `python bot.py` as the start
                   command; gunicorn is only needed if you switch the
                   Flask app to be the primary served app / add webhooks).
"""

import os
import logging
import sqlite3
import threading
from datetime import datetime
from contextlib import contextmanager

from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8808647263
SUPPORT_USERNAME = "+880 17 206 16501"
REFERRAL_BONUS = 0.002
DB_PATH = os.getenv("DB_PATH", "bot_database.db")
KEEP_ALIVE_PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("earning_bot")

# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #


@contextmanager
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL NOT NULL DEFAULT 0,
                referred_by INTEGER,
                referral_count INTEGER NOT NULL DEFAULT 0,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                reward REAL NOT NULL,
                link TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS withdrawals (
                withdrawal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                method_details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ip_log (
                user_id INTEGER PRIMARY KEY,
                device_signature TEXT,
                flagged INTEGER NOT NULL DEFAULT 0
            )
            """
        )


def get_user(user_id: int):
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def create_user(user_id: int, username: str, first_name: str, referred_by: int = None):
    with db_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO users
               (user_id, username, first_name, balance, referred_by,
                referral_count, is_blocked, joined_at)
               VALUES (?, ?, ?, 0, ?, 0, 0, ?)""",
            (user_id, username, first_name, referred_by, datetime.utcnow().isoformat()),
        )

        # Reward the referrer, once, only on first creation of this user.
        if referred_by and referred_by != user_id:
            referrer = conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?", (referred_by,)
            ).fetchone()
            if referrer:
                conn.execute(
                    "UPDATE users SET balance = balance + ?, referral_count = referral_count + 1 "
                    "WHERE user_id = ?",
                    (REFERRAL_BONUS, referred_by),
                )


def update_balance(user_id: int, amount: float):
    with db_conn() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id)
        )


def set_blocked(user_id: int, blocked: bool):
    with db_conn() as conn:
        conn.execute(
            "UPDATE users SET is_blocked = ? WHERE user_id = ?", (1 if blocked else 0, user_id)
        )


def add_task(title: str, reward: float, link: str):
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO tasks (title, reward, link, created_at) VALUES (?, ?, ?, ?)",
            (title, reward, link, datetime.utcnow().isoformat()),
        )


def list_tasks():
    with db_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY task_id DESC").fetchall()]


def list_users():
    with db_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY balance DESC").fetchall()]


def list_suspicious_users():
    """
    Heuristic only: flags users that share the same first_name+username
    combo as another account, or that were referred by an account which
    itself has an unusually high referral count. This is NOT proof of
    fraud -- an admin should manually review before blocking anyone.
    """
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT u1.* FROM users u1
            WHERE u1.referred_by IN (
                SELECT referred_by FROM users
                WHERE referred_by IS NOT NULL
                GROUP BY referred_by
                HAVING COUNT(*) >= 5
            )
            OR u1.referral_count >= 10
            ORDER BY u1.referral_count DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def create_withdrawal(user_id: int, amount: float, details: str):
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO withdrawals (user_id, amount, method_details, status, created_at) "
            "VALUES (?, ?, ?, 'pending', ?)",
            (user_id, amount, details, datetime.utcnow().isoformat()),
        )
        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id)
        )


# --------------------------------------------------------------------------- #
# Keyboards
# --------------------------------------------------------------------------- #

def admin_menu_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add Task", callback_data="admin_add_task")],
            [InlineKeyboardButton("🎁 Give Bonus", callback_data="admin_give_bonus")],
            [InlineKeyboardButton("📊 View Users", callback_data="admin_view_users")],
            [InlineKeyboardButton("⚠️ Suspicious Users", callback_data="admin_suspicious")],
            [
                InlineKeyboardButton("🚫 Block User", callback_data="admin_block"),
                InlineKeyboardButton("✅ Unblock User", callback_data="admin_unblock"),
            ],
        ]
    )


def user_menu_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💰 Balance", callback_data="user_balance"),
                InlineKeyboardButton("📋 Tasks", callback_data="user_tasks"),
            ],
            [
                InlineKeyboardButton("👤 Profile", callback_data="user_profile"),
                InlineKeyboardButton("👥 Referrals", callback_data="user_referrals"),
            ],
            [
                InlineKeyboardButton("💳 Withdraw", callback_data="user_withdraw"),
                InlineKeyboardButton("🛠 Support", callback_data="user_support"),
            ],
        ]
    )


def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="global_cancel")]])


def back_to_menu_kb(is_admin_user: bool):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
    )


# --------------------------------------------------------------------------- #
# Conversation states
# --------------------------------------------------------------------------- #

(
    ADD_TASK_TITLE,
    ADD_TASK_REWARD,
    ADD_TASK_LINK,
    GIVE_BONUS_ID,
    GIVE_BONUS_AMOUNT,
    BLOCK_ID,
    UNBLOCK_ID,
    WITHDRAW_AMOUNT,
    WITHDRAW_DETAILS,
) = range(9)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def send_admin_dashboard(update_or_query, edit: bool = False):
    text = "🛠 <b>Admin Dashboard</b>\n\nManage tasks, users, and bonuses below."
    if edit:
        await update_or_query.edit_message_text(text, reply_markup=admin_menu_kb(), parse_mode=ParseMode.HTML)
    else:
        await update_or_query.message.reply_text(text, reply_markup=admin_menu_kb(), parse_mode=ParseMode.HTML)


async def send_user_dashboard(update_or_query, edit: bool = False):
    text = "🏠 <b>Main Menu</b>\n\nChoose an option below to get started."
    if edit:
        await update_or_query.edit_message_text(text, reply_markup=user_menu_kb(), parse_mode=ParseMode.HTML)
    else:
        await update_or_query.message.reply_text(text, reply_markup=user_menu_kb(), parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------- #
# /start and generic entry points
# --------------------------------------------------------------------------- #


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # wipe any stale conversation state
    user = update.effective_user
    referred_by = None
    if context.args:
        try:
            candidate = int(context.args[0])
            if candidate != user.id:
                referred_by = candidate
        except (ValueError, IndexError):
            pass

    existing = get_user(user.id)
    if existing is None:
        create_user(user.id, user.username or "", user.first_name or "", referred_by)
        existing = get_user(user.id)

    if existing["is_blocked"]:
        await update.message.reply_text(
            "🚫 আপনার অ্যাকাউন্টটি ব্লক করা হয়েছে। সহায়তার জন্য "
            f"{SUPPORT_USERNAME} এ যোগাযোগ করুন।"
        )
        return

    if is_admin(user.id):
        await send_admin_dashboard(update)
    else:
        await send_user_dashboard(update)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("চলমান প্রক্রিয়াটি বাতিল করা হয়েছে।")
    if is_admin(update.effective_user.id):
        await send_admin_dashboard(update)
    else:
        await send_user_dashboard(update)
    return ConversationHandler.END


async def global_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback used inside conversations when the user taps '❌ Cancel'."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    if is_admin(update.effective_user.id):
        await send_admin_dashboard(query, edit=True)
    else:
        await send_user_dashboard(query, edit=True)
    return ConversationHandler.END


async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if is_admin(update.effective_user.id):
        await send_admin_dashboard(query, edit=True)
    else:
        await send_user_dashboard(query, edit=True)


async def auto_cancel_and_reroute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Registered as a fallback inside every conversation. If the user taps
    ANY menu button while a conversation is active, this ends the current
    conversation (no more waiting for the old input) and immediately hands
    the tap to the normal menu dispatcher so the new action starts right
    away instead of looping or getting stuck.
    """
    context.user_data.clear()
    query = update.callback_query
    if query:
        data = query.data
        if data in ROUTES:
            await ROUTES[data](update, context)
        else:
            await query.answer()
    return ConversationHandler.END


# --------------------------------------------------------------------------- #
# Admin: Add Task conversation
# --------------------------------------------------------------------------- #


async def admin_add_task_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "📝 নতুন টাস্কের <b>শিরোনাম (Title)</b> লিখুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    return ADD_TASK_TITLE


async def admin_add_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["task_title"] = update.message.text.strip()
    await update.message.reply_text(
        "💵 এই টাস্কের <b>রিওয়ার্ড ($)</b> লিখুন (যেমন: 0.25):",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    return ADD_TASK_REWARD


async def admin_add_task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        reward = float(text)
        if reward <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ একটি বৈধ সংখ্যা লিখুন (যেমন: 0.25)।", reply_markup=cancel_kb()
        )
        return ADD_TASK_REWARD
    context.user_data["task_reward"] = reward
    await update.message.reply_text(
        "🔗 টাস্কের <b>লিংক</b> দিন:", parse_mode=ParseMode.HTML, reply_markup=cancel_kb()
    )
    return ADD_TASK_LINK


async def admin_add_task_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    title = context.user_data.get("task_title")
    reward = context.user_data.get("task_reward")
    add_task(title, reward, link)
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ টাস্ক যোগ করা হয়েছে!\n\n<b>{title}</b>\nReward: ${reward:.2f}\nLink: {link}",
        parse_mode=ParseMode.HTML,
    )
    await send_admin_dashboard(update)
    return ConversationHandler.END


# --------------------------------------------------------------------------- #
# Admin: Give Bonus conversation
# --------------------------------------------------------------------------- #


async def admin_give_bonus_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "🎁 যে ইউজারকে বোনাস দিতে চান তার <b>User ID</b> লিখুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    return GIVE_BONUS_ID


async def admin_give_bonus_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ একটি বৈধ User ID (সংখ্যা) লিখুন।", reply_markup=cancel_kb())
        return GIVE_BONUS_ID
    if get_user(target_id) is None:
        await update.message.reply_text(
            "⚠️ এই User ID খুঁজে পাওয়া যায়নি। আবার চেষ্টা করুন অথবা বাতিল করুন।",
            reply_markup=cancel_kb(),
        )
        return GIVE_BONUS_ID
    context.user_data["bonus_target"] = target_id
    await update.message.reply_text(
        "💵 কত <b>($)</b> বোনাস দিতে চান তা লিখুন:", parse_mode=ParseMode.HTML, reply_markup=cancel_kb()
    )
    return GIVE_BONUS_AMOUNT


async def admin_give_bonus_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ একটি বৈধ সংখ্যা লিখুন।", reply_markup=cancel_kb())
        return GIVE_BONUS_AMOUNT
    target_id = context.user_data.get("bonus_target")
    update_balance(target_id, amount)
    context.user_data.clear()
    await update.message.reply_text(f"✅ ${amount:.2f} বোনাস User ID {target_id}-কে দেওয়া হয়েছে।")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 অভিনন্দন! অ্যাডমিন আপনাকে ${amount:.2f} বোনাস দিয়েছেন।",
        )
    except Exception as e:
        logger.warning("Could not notify user %s: %s", target_id, e)
    await send_admin_dashboard(update)
    return ConversationHandler.END


# --------------------------------------------------------------------------- #
# Admin: View Users / Suspicious Users (no conversation needed)
# --------------------------------------------------------------------------- #


async def admin_view_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    users = list_users()
    if not users:
        text = "কোনো ইউজার নিবন্ধিত নেই।"
    else:
        lines = [f"📊 <b>মোট ইউজার:</b> {len(users)}\n"]
        for u in users[:50]:
            status = "🚫" if u["is_blocked"] else "✅"
            uname = f"@{u['username']}" if u["username"] else "—"
            lines.append(f"{status} <code>{u['user_id']}</code> {uname} — ${u['balance']:.2f}")
        if len(users) > 50:
            lines.append(f"\n...এবং আরও {len(users) - 50} জন ইউজার")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_to_menu_kb(True))


async def admin_suspicious_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    users = list_suspicious_users()
    if not users:
        text = "⚠️ বর্তমানে কোনো সন্দেহজনক ইউজার পাওয়া যায়নি।"
    else:
        lines = ["⚠️ <b>সন্দেহজনক ইউজার তালিকা</b>", "(একাধিক রেফারেল প্যাটার্নের ভিত্তিতে — যাচাই করে সিদ্ধান্ত নিন)\n"]
        for u in users[:50]:
            uname = f"@{u['username']}" if u["username"] else "—"
            lines.append(
                f"🔎 <code>{u['user_id']}</code> {uname} — রেফারেল: {u['referral_count']}, ব্যালেন্স: ${u['balance']:.2f}"
            )
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_to_menu_kb(True))


# --------------------------------------------------------------------------- #
# Admin: Block / Unblock conversations
# --------------------------------------------------------------------------- #


async def admin_block_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "🚫 যে ইউজারকে ব্লক করতে চান তার <b>User ID</b> লিখুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    return BLOCK_ID


async def admin_block_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ একটি বৈধ User ID লিখুন।", reply_markup=cancel_kb())
        return BLOCK_ID
    if get_user(target_id) is None:
        await update.message.reply_text("⚠️ এই User ID খুঁজে পাওয়া যায়নি।", reply_markup=cancel_kb())
        return BLOCK_ID
    set_blocked(target_id, True)
    context.user_data.clear()
    await update.message.reply_text(f"✅ User ID {target_id} ব্লক করা হয়েছে।")
    await send_admin_dashboard(update)
    return ConversationHandler.END


async def admin_unblock_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "✅ যে ইউজারকে আনব্লক করতে চান তার <b>User ID</b> লিখুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb(),
    )
    return UNBLOCK_ID


async def admin_unblock_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ একটি বৈধ User ID লিখুন।", reply_markup=cancel_kb())
        return UNBLOCK_ID
    if get_user(target_id) is None:
        await update.message.reply_text("⚠️ এই User ID খুঁজে পাওয়া যায়নি।", reply_markup=cancel_kb())
        return UNBLOCK_ID
    set_blocked(target_id, False)
    context.user_data.clear()
    await update.message.reply_text(f"✅ User ID {target_id} আনব্লক করা হয়েছে।")
    await send_admin_dashboard(update)
    return ConversationHandler.END


# --------------------------------------------------------------------------- #
# User: Balance / Tasks / Profile / Referrals / Support (no conversation)
# --------------------------------------------------------------------------- #


async def user_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = get_user(query.from_user.id)
    await query.edit_message_text(
        f"💰 আপনার বর্তমান ব্যালেন্স: <b>${u['balance']:.2f}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_menu_kb(False),
    )


async def user_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tasks = list_tasks()
    if not tasks:
        text = "📋 বর্তমানে কোনো টাস্ক নেই। পরে আবার চেক করুন।"
    else:
        lines = ["📋 <b>উপলব্ধ টাস্কসমূহ:</b>\n"]
        for t in tasks:
            lines.append(f"• <b>{t['title']}</b> — ${t['reward']:.2f}\n  🔗 {t['link']}\n")
        text = "\n".join(lines)
    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=back_to_menu_kb(False), disable_web_page_preview=True
    )


async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = get_user(query.from_user.id)
    uname = f"@{u['username']}" if u["username"] else "—"
    text = (
        f"👤 <b>প্রোফাইল</b>\n\n"
        f"নাম: {u['first_name']}\n"
        f"ইউজারনেম: {uname}\n"
        f"User ID: <code>{u['user_id']}</code>\n"
        f"ব্যালেন্স: ${u['balance']:.2f}\n"
        f"মোট রেফার: {u['referral_count']} জন"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_to_menu_kb(False))


async def user_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_username = context.bot.username
    u = get_user(query.from_user.id)
    link = f"https://t.me/{bot_username}?start={u['user_id']}"
    text = (
        f"👥 <b>রেফারেল প্রোগ্রাম</b>\n\n"
        f"আপনার রেফারেল লিংক:\n<code>{link}</code>\n\n"
        f"প্রতি সফল রেফারেলে আপনি পাবেন: <b>${REFERRAL_BONUS:.2f}</b>\n"
        f"মোট রেফার করেছেন: {u['referral_count']} জন"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_to_menu_kb(False))


async def user_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🛠 সহায়তার জন্য যোগাযোগ করুন: {SUPPORT_USERNAME}",
        reply_markup=back_to_menu_kb(False),
    )


# --------------------------------------------------------------------------- #
# User: Withdraw conversation
# --------------------------------------------------------------------------- #


async def user_withdraw_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = get_user(query.from_user.id)
    if u["is_blocked"]:
        await query.edit_message_text("🚫 আপনার অ্যাকাউন্ট ব্লক করা আছে, তাই উইথড্র করা যাবে না।")
        return ConversationHandler.END
    await query.edit_message_text(
        f"💳 আপনার ব্যালেন্স: ${u['balance']:.2f}\n\n"
        "কত টাকা উইথড্র করতে চান তা লিখুন ($):",
        reply_markup=cancel_kb(),
    )
    return WITHDRAW_AMOUNT


async def user_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    u = get_user(update.effective_user.id)
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ একটি বৈধ সংখ্যা লিখুন।", reply_markup=cancel_kb())
        return WITHDRAW_AMOUNT
    if amount > u["balance"]:
        await update.message.reply_text(
            f"⚠️ আপনার ব্যালেন্সে এত টাকা নেই। বর্তমান ব্যালেন্স: ${u['balance']:.2f}",
            reply_markup=cancel_kb(),
        )
        return WITHDRAW_AMOUNT
    context.user_data["withdraw_amount"] = amount
    await update.message.reply_text(
        "💼 আপনার পেমেন্ট মেথড ও ডিটেইলস লিখুন (যেমন: bKash 01XXXXXXXXX):",
        reply_markup=cancel_kb(),
    )
    return WITHDRAW_DETAILS


async def user_withdraw_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text.strip()
    amount = context.user_data.get("withdraw_amount")
    user_id = update.effective_user.id
    create_withdrawal(user_id, amount, details)
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ আপনার ${amount:.2f} উইথড্র রিকোয়েস্ট জমা হয়েছে এবং পর্যালোচনার অপেক্ষায় আছে।"
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💳 নতুন উইথড্র রিকোয়েস্ট\n\n"
                f"User: <code>{user_id}</code>\nAmount: ${amount:.2f}\nDetails: {details}"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning("Could not notify admin of withdrawal: %s", e)
    await send_user_dashboard(update)
    return ConversationHandler.END


# --------------------------------------------------------------------------- #
# Route table used by the auto-cancel fallback
# --------------------------------------------------------------------------- #

ROUTES = {
    "admin_view_users": admin_view_users,
    "admin_suspicious": admin_suspicious_users,
    "user_balance": user_balance,
    "user_tasks": user_tasks,
    "user_profile": user_profile,
    "user_referrals": user_referrals,
    "user_support": user_support,
    "back_to_menu": back_to_menu_callback,
}


# --------------------------------------------------------------------------- #
# Flask keep-alive server (for Render free-tier uptime pings)
# --------------------------------------------------------------------------- #

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "Telegram Earning Bot is running."


def run_flask():
    flask_app.run(host="0.0.0.0", port=KEEP_ALIVE_PORT)


# --------------------------------------------------------------------------- #
# Application wiring
# --------------------------------------------------------------------------- #


def build_application() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # Simple (non-conversation) callbacks
    for pattern, func in ROUTES.items():
        app.add_handler(CallbackQueryHandler(func, pattern=f"^{pattern}$"))
    app.add_handler(CallbackQueryHandler(global_cancel_callback, pattern="^global_cancel$"))

    common_fallbacks = [
        CommandHandler("cancel", cancel_command),
        CallbackQueryHandler(global_cancel_callback, pattern="^global_cancel$"),
        CallbackQueryHandler(auto_cancel_and_reroute),  # catches any other stray button
    ]

    add_task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_task_entry, pattern="^admin_add_task$")],
        states={
            ADD_TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_task_title)],
            ADD_TASK_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_task_reward)],
            ADD_TASK_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_task_link)],
        },
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    give_bonus_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_give_bonus_entry, pattern="^admin_give_bonus$")],
        states={
            GIVE_BONUS_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_give_bonus_id)],
            GIVE_BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_give_bonus_amount)],
        },
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    block_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_block_entry, pattern="^admin_block$")],
        states={BLOCK_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_block_id)]},
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    unblock_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_unblock_entry, pattern="^admin_unblock$")],
        states={UNBLOCK_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unblock_id)]},
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_withdraw_entry, pattern="^user_withdraw$")],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_withdraw_amount)],
            WITHDRAW_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_withdraw_details)],
        },
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    for conv in (add_task_conv, give_bonus_conv, block_conv, unblock_conv, withdraw_conv):
        app.add_handler(conv)

    return app


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")

    init_db()

    # Keep-alive web server in a background thread so Render sees an open port.
    threading.Thread(target=run_flask, daemon=True).start()

    application = build_application()
    logger.info("Bot starting (polling mode)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
