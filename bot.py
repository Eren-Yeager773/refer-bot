import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

BOT_TOKEN = "AAHdqkOothoYM25lvzxM57XVsfRpDlflTuQ"
ADMIN_ID   = 8395622935  
POINTS_PER_REFER  = 1
MIN_WITHDRAW      = 5

def get_db():
    conn = sqlite3.connect("refer_bot.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            points      INTEGER DEFAULT 0,
            total_refer INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            points      INTEGER,
            bkash_num   TEXT,
            status      TEXT DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return user

def register_user(user_id, username, full_name, referred_by=None):
    conn = get_db()
    existing = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (user_id, username, full_name, referred_by) VALUES (?,?,?,?)",
            (user_id, username, full_name, referred_by)
        )
        if referred_by:
            conn.execute(
                "UPDATE users SET points=points+?, total_refer=total_refer+1 WHERE user_id=?",
                (POINTS_PER_REFER, referred_by)
            )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 আমার Profile", callback_data="profile"),
         InlineKeyboardButton("🔗 Refer Link",   callback_data="refer")],
        [InlineKeyboardButton("🏆 Leaderboard",  callback_data="leaderboard"),
         InlineKeyboardButton("💸 Withdraw",      callback_data="withdraw")],
        [InlineKeyboardButton("📋 আমার Withdrawals", callback_data="my_withdrawals")],
    ])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    args    = ctx.args
    ref_by  = int(args[0]) if args and args[0].isdigit() else None
    if ref_by == user.id:
        ref_by = None
    is_new = register_user(user.id, user.username or "", user.full_name, ref_by)
    if is_new and ref_by:
        try:
            await ctx.bot.send_message(
                ref_by,
                f"🎉 তোমার refer link দিয়ে *{user.full_name}* join করেছে!\n"
                f"তুমি *{POINTS_PER_REFER} পয়েন্ট* পেয়েছ! 🎊",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    welcome = (
        f"🤖 *স্বাগতম, {user.full_name}!*\n\n"
        f"এই bot-এ তুমি বন্ধুদের refer করে পয়েন্ট আয় করতে পারবে।\n"
        f"• প্রতি সফল refer = *{POINTS_PER_REFER} পয়েন্ট*\n"
        f"• ন্যূনতম withdraw = *{MIN_WITHDRAW} পয়েন্ট*\n\n"
        f"নিচের menu থেকে শুরু করো 👇"
    )
    if is_new and ref_by:
        welcome += f"\n\n✅ তুমি একটি refer link দিয়ে join করেছ!"
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    if data == "profile":
        u = get_user(uid)
        if not u:
            await query.edit_message_text("আগে /start দাও।")
            return
        text = (
            f"👤 *তোমার Profile*\n\n"
            f"🆔 ID: `{u['user_id']}`\n"
            f"📛 নাম: {u['full_name']}\n"
            f"⭐ পয়েন্ট: *{u['points']}*\n"
            f"👥 মোট Refer: *{u['total_refer']}*\n"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())

    elif data == "refer":
        bot_username = (await ctx.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={uid}"
        text = (
            f"🔗 *তোমার Refer Link:*\n\n"
            f"`{link}`\n\n"
            f"এই link বন্ধুদের পাঠাও। যতজন join করবে,\n"
            f"প্রতিজনের জন্য *{POINTS_PER_REFER} পয়েন্ট* পাবে! 🎁"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())

    elif data == "leaderboard":
        conn = get_db()
        rows = conn.execute(
            "SELECT full_name, total_refer, points FROM users ORDER BY total_refer DESC LIMIT 10"
        ).fetchall()
        conn.close()
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        text = "🏆 *Top Referrers*\n\n"
        for i, r in enumerate(rows):
            text += f"{medals[i]} {r['full_name']} — {r['total_refer']} refer ({r['points']} pts)\n"
        if not rows:
            text += "এখনো কোনো data নেই।"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())

    elif data == "withdraw":
        u = get_user(uid)
        if not u:
            await query.edit_message_text("আগে /start দাও।")
            return
        if u["points"] < MIN_WITHDRAW:
            await query.edit_message_text(
                f"❌ তোমার কাছে মাত্র *{u['points']} পয়েন্ট* আছে।\n"
                f"Withdraw করতে ন্যূনতম *{MIN_WITHDRAW} পয়েন্ট* লাগবে।",
                parse_mode="Markdown", reply_markup=main_menu_kb()
            )
            return
        ctx.user_data["awaiting_withdraw"] = True
        ctx.user_data["withdraw_points"] = u["points"]
        await query.edit_message_text(
            f"💸 *Withdraw Request*\n\n"
            f"তোমার পয়েন্ট: *{u['points']}*\n\n"
            f"তোমার *bKash/Nagad নম্বর* লেখো (reply করো):",
            parse_mode="Markdown"
        )

    elif data == "my_withdrawals":
        conn = get_db()
        rows = conn.execute(
            "SELECT points, bkash_num, status, requested_at FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (uid,)
        ).fetchall()
        conn.close()
        if not rows:
            text = "📋 তোমার কোনো withdrawal request নেই।"
        else:
            text = "📋 *তোমার শেষ ৫টি Withdrawal:*\n\n"
            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
            for r in rows:
                e = status_emoji.get(r["status"], "❓")
                text += f"{e} {r['points']} pts → {r['bkash_num']} [{r['status']}]\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())

    elif data.startswith("approve_") or data.startswith("reject_"):
        if uid != ADMIN_ID:
            await query.answer("তুমি admin না!", show_alert=True)
            return
        action, wid = data.split("_", 1)
        wid = int(wid)
        conn = get_db()
        w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
        if not w:
            await query.edit_message_text("Withdrawal খুঁজে পাওয়া যায়নি।")
            conn.close()
            return
        if action == "approve":
            conn.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (wid,))
            conn.commit()
            conn.close()
            await query.edit_message_text(f"✅ Withdrawal #{wid} Approved!")
            try:
                await ctx.bot.send_message(
                    w["user_id"],
                    f"✅ তোমার *{w['points']} পয়েন্ট* withdraw approved হয়েছে!\n"
                    f"নম্বর: {w['bkash_num']}\nশীঘ্রই payment পাবে। 🎉",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            conn.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wid,))
            conn.execute(
                "UPDATE users SET points=points+? WHERE user_id=?",
                (w["points"], w["user_id"])
            )
            conn.commit()
            conn.close()
            await query.edit_message_text(f"❌ Withdrawal #{wid} Rejected & পয়েন্ট ফেরত দেওয়া হয়েছে।")
            try:
                await ctx.bot.send_message(
                    w["user_id"],
                    f"❌ তোমার withdrawal request reject হয়েছে।\n"
                    f"*{w['points']} পয়েন্ট* তোমার account-এ ফেরত দেওয়া হয়েছে।",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if ctx.user_data.get("awaiting_withdraw"):
        bkash_num = update.message.text.strip()
        points    = ctx.user_data.get("withdraw_points", 0)
        conn = get_db()
        conn.execute("UPDATE users SET points=points-? WHERE user_id=?", (points, uid))
        conn.execute(
            "INSERT INTO withdrawals (user_id, points, bkash_num) VALUES (?,?,?)",
            (uid, points, bkash_num)
        )
        wid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        ctx.user_data["awaiting_withdraw"] = False
        await update.message.reply_text(
            f"✅ *Withdraw Request পাঠানো হয়েছে!*\n\n"
            f"পয়েন্ট: *{points}*\nনম্বর: {bkash_num}\n\nAdmin confirm করলে জানানো হবে।",
            parse_mode="Markdown", reply_markup=main_menu_kb()
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{wid}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{wid}"),
        ]])
        u = get_user(uid)
        try:
            await ctx.bot.send_message(
                ADMIN_ID,
                f"💸 *নতুন Withdraw Request!*\n\n"
                f"👤 User: {u['full_name']} (`{uid}`)\n"
                f"⭐ পয়েন্ট: *{points}*\n"
                f"📱 নম্বর: `{bkash_num}`\n"
                f"🆔 Request ID: #{wid}",
                parse_mode="Markdown", reply_markup=kb
            )
        except Exception:
            pass

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = get_db()
    total_users  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_points = conn.execute("SELECT SUM(points) FROM users").fetchone()[0] or 0
    pending_req  = conn.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'").fetchone()[0]
    conn.close()
    await update.message.reply_text(
        f"📊 *Bot Stats*\n\n"
        f"👥 মোট Users: *{total_users}*\n"
        f"⭐ মোট পয়েন্ট: *{total_points}*\n"
        f"⏳ Pending Withdrawals: *{pending_req}*",
        parse_mode="Markdown"
    )

async def add_points_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        target_id = int(ctx.args[0])
        pts       = int(ctx.args[1])
        conn = get_db()
        conn.execute("UPDATE users SET points=points+? WHERE user_id=?", (pts, target_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ {target_id} কে {pts} পয়েন্ট দেওয়া হয়েছে।")
    except Exception:
        await update.message.reply_text("Usage: /addpoints <user_id> <points>")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("stats",     admin_stats))
    app.add_handler(CommandHandler("addpoints", add_points_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("✅ Bot চালু হয়েছে...")
    app.run_polling()

if __name__ == "__main__":
    main()
