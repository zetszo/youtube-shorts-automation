import asyncio
import json
import os
import sys
import traceback
from datetime import datetime
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config
import script_gen
import voiceover
import footage
import video_editor
import thumbnail
import uploader

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS = [int(x) for x in os.environ.get("TELEGRAM_USER_ID", "0").split(",") if x.strip()]

HISTORY_FILE = "output/history.json"

def _load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"seasons": {}, "current_season": 1, "total": 0, "all_done": False}

def _get_progress_text():
    h = _load_history()
    lines = ["\U0001f4ca \u0627\u0644\u062a\u0642\u062f\u0645:"]
    for sid in sorted(config.SEASONS.keys()):
        s = config.SEASONS[sid]
        completed = len(h.get("seasons", {}).get(str(sid), {}).get("completed", []))
        total = len(s["episodes"])
        bar = "\u2588" * (completed * 20 // max(total, 1)) + "\u2591" * (20 - completed * 20 // max(total, 1))
        if completed >= total:
            status = "\u2705"
        elif h.get("current_season") == sid:
            status = "\u25b6\ufe0f"
        else:
            status = "\u23f3"
        lines.append(f"{status} {s['name'][:35]}: {bar} {completed}/{total}")
    lines.append(f"\n\u2705 \u0625\u062c\u0645\u0627\u0644\u064a: {h.get('total', 0)} \u0641\u064a\u062f\u064a\u0648")
    return "\n".join(lines)

async def _check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not ALLOWED_USERS or update.effective_user.id in ALLOWED_USERS:
        return True
    await update.message.reply_text("\u26a0\ufe0f \u0644\u0627 \u064a\u0648\u062c\u062f \u062a\u0635\u0631\u064a\u062d \u0644\u0643 \u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0647\u0630\u0627 \u0627\u0644\u0628\u0648\u062a.")
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    txt = (
        "\u0628\u0633\u0645 \u0627\u0644\u0644\u0647 \u0627\u0644\u0631\u062d\u0645\u0646 \u0627\u0644\u0631\u062d\u064a\u0645 \U0001f54b\n\n"
        "\u0623\u0647\u0644\u0627\u064b \u0628\u0643 \u0641\u064a \u0628\u0648\u062a \u0625\u0646\u062a\u0627\u062c \u0627\u0644\u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a\u0629!\n\n"
        "\u0627\u0644\u0623\u0648\u0627\u0645\u0631 \u0627\u0644\u0645\u062a\u0627\u062d\u0629:\n"
        "/status - \u0639\u0631\u0636 \u0627\u0644\u062a\u0642\u062f\u0645\n"
        "/generate - \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u062d\u0644\u0642\u0629 \u0627\u0644\u062a\u0627\u0644\u064a\u0629\n"
        "/season - \u0627\u062e\u062a\u064a\u0627\u0631 \u0627\u0644\u0645\u0648\u0633\u0645\n"
        "/preview - \u0622\u062e\u0631 \u0641\u064a\u062f\u064a\u0648\n"
        "/upload - \u0631\u0641\u0639 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628\n"
        "/help - \u0627\u0644\u0645\u0633\u0627\u0639\u062f\u0629"
    )
    await update.message.reply_text(txt)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    await update.message.reply_text(_get_progress_text())

async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    msg = await update.message.reply_text("\u23f3 \u062c\u0627\u0631 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u062d\u0644\u0642\u0629 \u0627\u0644\u062a\u0627\u0644\u064a\u0629...")

    def _run():
        try:
            sd = script_gen.generate_script()
            voiceover.generate_voiceover(sd)
            clips = footage.download_footage(sd)
            video_editor.create_video(sd, clips)
            try:
                thumb = thumbnail.generate_thumbnail(sd.get("topic", ""))
                sd["thumbnail_file"] = thumb
            except Exception:
                pass
            return sd
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _run)

    if "error" in result:
        await msg.edit_text(f"\u274c \u0641\u0634\u0644: {result['error']}")
        return

    ep = result.get("episode_id", result.get("topic_id", ""))
    season_info = result.get("season_name", "")
    ep_num = result.get("episode_num", 0)
    ep_total = result.get("total_eps", 0)
    video_path = result.get("video_file", "")
    story_len = len(result.get("story", "").split())

    txt = (
        "\u2705 \u062a\u0645 \u0627\u0644\u062a\u0648\u0644\u064a\u062f \u0628\u0646\u062c\u0627\u062d!\n\n"
        "\U0001F4cd " + ep + "\n"
        "\U0001f4da " + season_info + "\n"
        "\U0001f4f0 \u0627\u0644\u062d\u0644\u0642\u0629 " + str(ep_num) + "/" + str(ep_total) + "\n"
        "\U0001f3ac " + str(story_len) + " \u0643\u0644\u0645\u0629"
    )
    await msg.edit_text(txt)

    if video_path and os.path.exists(video_path):
        await msg.reply_text("\U0001f3ac \u062c\u0627\u0631 \u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0641\u064a\u062f\u064a\u0648...")
        try:
            with open(video_path, "rb") as f:
                await msg.reply_video(f, caption=result.get("topic", ""))
        except Exception as e:
            await msg.reply_text(f"\u26a0\ufe0f \u0641\u0634\u0644 \u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0641\u064a\u062f\u064a\u0648: {e}")

async def season_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    keyboard = [
        [InlineKeyboardButton(f"S1: {config.SEASONS[1]['name'][:30]}", callback_data="season_1")],
        [InlineKeyboardButton(f"S2: {config.SEASONS[2]['name'][:30]}", callback_data="season_2")],
        [InlineKeyboardButton(f"S3: {config.SEASONS[3]['name'][:30]}", callback_data="season_3")],
    ]
    await update.message.reply_text("\u0627\u062e\u062a\u0631 \u0627\u0644\u0645\u0648\u0633\u0645:", reply_markup=InlineKeyboardMarkup(keyboard))

async def season_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("season_", ""))
    h = _load_history()
    h["current_season"] = sid
    if str(sid) not in h["seasons"]:
        h["seasons"][str(sid)] = {"completed": [], "status": "active"}
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)
    await query.edit_message_text(f"\u2705 \u062a\u0645 \u062a\u062d\u062f\u064a\u062b \u0627\u0644\u0645\u0648\u0633\u0645 \u0625\u0644\u0649:\n{config.SEASONS[sid]['name']}")

async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    import glob
    videos = sorted(glob.glob("output/final_videos/*.mp4"), key=os.path.getmtime, reverse=True)
    if not videos:
        await update.message.reply_text("\u274c \u0644\u0627 \u064a\u0648\u062c\u062f \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a \u0628\u0639\u062f.")
        return
    try:
        with open(videos[0], "rb") as f:
            await update.message.reply_video(f, caption="\U0001f3ac \u0622\u062e\u0631 \u0641\u064a\u062f\u064a\u0648 \u0645\u0646\u062a\u062c")
    except Exception as e:
        await update.message.reply_text(f"\u26a0\ufe0f {e}")

async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    import glob
    videos = sorted(glob.glob("output/final_videos/*.mp4"), key=os.path.getmtime, reverse=True)
    if not videos:
        await update.message.reply_text("\u274c \u0644\u0627 \u064a\u0648\u062c\u062f \u0641\u064a\u062f\u064a\u0648 \u0644\u0644\u0631\u0641\u0639.")
        return
    msg = await update.message.reply_text("\u23f3 \u062c\u0627\u0631 \u0627\u0644\u0631\u0641\u0639 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628...")
    try:
        scripts = sorted(glob.glob("output/scripts/*.json"), key=os.path.getmtime, reverse=True)
        sd = {}
        if scripts:
            with open(scripts[0], encoding="utf-8") as f:
                sd = json.load(f)
        sd["video_file"] = videos[0]
        url = uploader.upload_video(sd)
        await msg.edit_text(f"\u2705 \u062a\u0645 \u0627\u0644\u0631\u0641\u0639!\n{url}")
    except Exception as e:
        await msg.edit_text(f"\u274c \u0641\u0634\u0644 \u0627\u0644\u0631\u0641\u0639: {e}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    txt = (
        "\U0001f916 \u0628\u0648\u062a \u0625\u0646\u062a\u0627\u062c \u0627\u0644\u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a\u0629\n\n"
        "/start - \u0627\u0644\u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629\n"
        "/status - \u0639\u0631\u0636 \u062a\u0642\u062f\u0645 \u0627\u0644\u0645\u0648\u0627\u0633\u0645\n"
        "/generate - \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u062d\u0644\u0642\u0629 \u0627\u0644\u062a\u0627\u0644\u064a\u0629\n"
        "/season - \u062a\u062d\u062f\u064a\u062f \u0627\u0644\u0645\u0648\u0633\u0645\n"
        "/preview - \u0645\u0639\u0627\u064a\u0646\u0629 \u0622\u062e\u0631 \u0641\u064a\u062f\u064a\u0648\n"
        "/upload - \u0631\u0641\u0639 \u0622\u062e\u0631 \u0641\u064a\u062f\u064a\u0648 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628\n\n"
        "\U0001f511 \u062a\u062d\u062a\u0627\u062c \u0625\u0644\u0649 \u062a\u0639\u064a\u064a\u0646 \u0645\u062a\u063a\u064a\u0631\u0627\u062a \u0627\u0644\u0628\u064a\u0626\u0629:\n"
        "TELEGRAM_BOT_TOKEN - \u062a\u0648\u0643\u0646 \u0627\u0644\u0628\u0648\u062a\n"
        "TELEGRAM_USER_ID - \u0627\u064a\u062f\u064a \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0645\u0633\u0645\u0648\u062d"
    )
    await update.message.reply_text(txt)

def main():
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN \u063a\u064a\u0631 \u0645\u0636\u0628\u0648\u0637!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(CommandHandler("season", season_cmd))
    app.add_handler(CommandHandler("preview", preview_cmd))
    app.add_handler(CommandHandler("upload", upload_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(season_callback, pattern="^season_"))

    print("\u2705 \u0628\u0648\u062a \u062a\u0644\u064a\u062c\u0631\u0627\u0645 \u0634\u063a\u0627\u0644! \u0627\u0636\u063a\u0637 Ctrl+C \u0644\u0644\u0625\u064a\u0642\u0627\u0641")
    app.run_polling()

if __name__ == "__main__":
    main()
