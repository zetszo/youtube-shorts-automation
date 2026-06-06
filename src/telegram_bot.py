import asyncio
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Fix import path: bot lives in src/, project root is one level up
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

import config
import script_gen
import voiceover
import footage
import video_editor
import thumbnail
import uploader

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS = [int(x) for x in os.environ.get("TELEGRAM_USER_ID", "0").split(",") if x.strip()]

HISTORY_FILE = _ROOT / "output" / "history.json"
LOG_FILE = _ROOT / "output" / "log.json"

# Track running generation to allow cancellation
_running_tasks = {}  # chat_id -> asyncio.Task

def _load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {"seasons": {}, "current_season": 1, "total": 0, "all_done": False}

def _get_progress_text():
    h = _load_history()
    lines = ["📊 التقدم:"]
    for sid in sorted(config.SEASONS.keys()):
        s = config.SEASONS[sid]
        completed = len(h.get("seasons", {}).get(str(sid), {}).get("completed", []))
        total = len(s["episodes"])
        bar = "█" * (completed * 20 // max(total, 1)) + "░" * (20 - completed * 20 // max(total, 1))
        if completed >= total:
            status = "✅"
        elif h.get("current_season") == sid:
            status = "▶️"
        else:
            status = "⏳"
        lines.append(f"{status} {s['name'][:35]}: {bar} {completed}/{total}")
    lines.append(f"\n✅ إجمالي: {h.get('total', 0)} فيديو")
    return "\n".join(lines)

def _get_episodes_list(season_id: int):
    """Return list of (episode_id, topic, done) for a season."""
    h = _load_history()
    s = config.SEASONS.get(season_id)
    if not s:
        return []
    completed = set(h.get("seasons", {}).get(str(season_id), {}).get("completed", []))
    return [(ep[0], ep[1], ep[0] in completed) for ep in s["episodes"]]

async def _check_auth(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not ALLOWED_USERS or update.effective_user.id in ALLOWED_USERS:
        return True
    await update.message.reply_text("⚠️ لا يوجد تصريح لك لاستخدام هذا البوت.")
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    txt = (
        "بسم الله الرحمن الرحيم 🕋\n\n"
        "أهلاً بك في بوت إنتاج الفيديوهات الإسلامية!\n\n"
        "الأوامر المتاحة:\n"
        "/status - عرض التقدم\n"
        "/generate - توليد الحلقة التالية\n"
        "/generate <رقم> - توليد حلقة محددة\n"
        "/eps [1|2|3] - عرض حلقات الموسم\n"
        "/season - اختيار الموسم\n"
        "/preview - آخر فيديو\n"
        "/upload - رفع لليوتيوب\n"
        "/cancel - إلغاء التوليد الجاري\n"
        "/retry - إعادة المحاولة لآخر فاشل\n"
        "/log - آخر 5 أسطر من السجل\n"
        "/help - المساعدة"
    )
    await update.message.reply_text(txt)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    await update.message.reply_text(_get_progress_text())

async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return

    chat_id = update.effective_chat.id
    if chat_id in _running_tasks and not _running_tasks[chat_id].done():
        await update.message.reply_text("⚠️ يوجد توليد قيد التشغيل حالياً! استخدم /cancel لإلغائه.")
        return

    # Parse optional episode argument: /generate <topic_id>
    specific_ep = None
    if context.args:
        specific_ep = " ".join(context.args)

    msg = await update.message.reply_text(f"⏳ جارٍ التوليد{f' للحلقة: {specific_ep}' if specific_ep else ' للحلقة التالية'}...")

    async def _run_with_progress(specific_ep):
        nonlocal msg
        try:
            # Stage 1: Script
            await msg.edit_text("📝 المرحلة 1/4: توليد النص...")
            sd = script_gen.generate_script(specific_ep)
            ep = sd.get("episode_id", sd.get("topic_id", "?"))
            await msg.edit_text(f"📝 ✅ النص جاهز: {ep} ({len(sd['story'].split())} كلمة)")

            # Stage 2: Voiceover
            await msg.edit_text("🎙️ المرحلة 2/4: توليد الصوت...")
            voiceover.generate_voiceover(sd)
            await msg.edit_text(f"🎙️ ✅ الصوت جاهز ({len(sd.get('word_timings',[]))} كلمة موقوتة)")

            # Stage 3: Footage
            await msg.edit_text("🎬 المرحلة 3/4: تحميل الفيديوهات الخلفية...")
            clips = footage.download_footage(sd)
            await msg.edit_text(f"🎬 ✅ {len(clips)} فيديو خلفي")

            # Stage 4: Video
            await msg.edit_text("🎞️ المرحلة 4/4: مونتاج الفيديو (قد يستغرق دقائق)...")
            video_editor.create_video(sd, clips)
            await msg.edit_text("🎞️ ✅ الفيديو جاهز!")

            # Thumbnail (optional)
            try:
                thumb = thumbnail.generate_thumbnail(sd.get("topic", ""))
                sd["thumbnail_file"] = thumb
            except Exception:
                pass

            # Result
            season_info = sd.get("season_name", "")
            ep_num = sd.get("episode_num", 0)
            ep_total = sd.get("total_eps", 0)
            video_path = sd.get("video_file", "")
            story_len = len(sd.get("story", "").split())

            txt = (
                f"✅ تم التوليد بنجاح!\n\n"
                f"📌 {ep}\n"
                f"📚 {season_info}\n"
                f"📰 الحلقة {ep_num}/{ep_total}\n"
                f"🎬 {story_len} كلمة"
            )
            await msg.edit_text(txt)

            if video_path and os.path.exists(video_path):
                await msg.reply_text("🎬 جاري إرسال الفيديو...")
                try:
                    sz = os.path.getsize(video_path) / (1024*1024)
                    if sz > 50:
                        await msg.reply_text(f"⚠️ الفيديو كبير ({sz:.0f}MB). لا يمكن إرساله عبر تيلجرام.")
                    else:
                        with open(video_path, "rb") as f:
                            await msg.reply_video(f, caption=sd.get("topic", ""))
                except Exception as e:
                    await msg.reply_text(f"⚠️ فشل إرسال الفيديو: {e}")

            return sd
        except Exception as e:
            tb = traceback.format_exc()
            await msg.edit_text(f"❌ فشل التوليد:\n{e}")
            # Save error log
            log_path = _ROOT / "output" / "bot_error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now()}] {e}\n{tb}\n\n")
            return {"error": str(e)}

    task = asyncio.create_task(_run_with_progress(specific_ep))
    _running_tasks[chat_id] = task
    try:
        await task
    except asyncio.CancelledError:
        await msg.edit_text("⛔ تم إلغاء التوليد.")
    finally:
        if chat_id in _running_tasks and _running_tasks[chat_id] is task:
            del _running_tasks[chat_id]

async def eps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    sid = 1
    if context.args:
        try:
            sid = int(context.args[0])
        except ValueError:
            pass
    if sid not in config.SEASONS:
        await update.message.reply_text(f"⚠️ الموسم {sid} غير موجود. استخدم 1 و 2 أو 3.")
        return

    episodes = _get_episodes_list(sid)
    if not episodes:
        await update.message.reply_text("⚠️ لا توجد حلقات في هذا الموسم.")
        return

    s = config.SEASONS[sid]
    h = _load_history()
    completed = set(h.get("seasons", {}).get(str(sid), {}).get("completed", []))
    current = h.get("current_season")

    lines = [f"📚 {s['name']} - {len(episodes)} حلقة:"]
    for eid, topic, _ in episodes:
        done = "✅" if eid in completed else "⬜"
        lines.append(f"{done} {eid}: {topic[:50]}")
    lines.append(f"\n▶️ الموسم النشط: S{current}")

    # Send in chunks of 20
    full = "\n".join(lines)
    if len(full) > 4000:
        for i in range(0, len(lines), 40):
            chunk = "\n".join(lines[i:i+40])
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(full)

async def season_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    keyboard = [
        [InlineKeyboardButton(f"S1: {config.SEASONS[1]['name'][:30]}", callback_data="season_1")],
        [InlineKeyboardButton(f"S2: {config.SEASONS[2]['name'][:30]}", callback_data="season_2")],
        [InlineKeyboardButton(f"S3: {config.SEASONS[3]['name'][:30]}", callback_data="season_3")],
    ]
    await update.message.reply_text("اختر الموسم:", reply_markup=InlineKeyboardMarkup(keyboard))

async def season_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("season_", ""))
    h = _load_history()
    h["current_season"] = sid
    if str(sid) not in h["seasons"]:
        h["seasons"][str(sid)] = {"completed": [], "status": "active"}
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")
    await query.edit_message_text(f"✅ تم تحديث الموسم إلى:\n{config.SEASONS[sid]['name']}")

async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    videos = sorted((_ROOT / "output" / "final_videos").glob("*.mp4"), key=os.path.getmtime, reverse=True)
    if not videos:
        await update.message.reply_text("❌ لا يوجد فيديوهات بعد.")
        return
    try:
        sz = videos[0].stat().st_size / (1024*1024)
        caption = f"🎬 آخر فيديو منتج ({sz:.0f}MB)"
        if sz > 50:
            await update.message.reply_text(f"⚠️ الفيديو كبير ({sz:.0f}MB). لا يمكن إرساله عبر تيلجرام.")
            return
        with open(videos[0], "rb") as f:
            await update.message.reply_video(f, caption=caption)
    except Exception as e:
        await update.message.reply_text(f"⚠️ {e}")

async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    videos = sorted((_ROOT / "output" / "final_videos").glob("*.mp4"), key=os.path.getmtime, reverse=True)
    if not videos:
        await update.message.reply_text("❌ لا يوجد فيديو للرفع.")
        return
    msg = await update.message.reply_text("⏳ جاري الرفع لليوتيوب...")
    try:
        scripts = sorted((_ROOT / "output" / "scripts").glob("*.json"), key=os.path.getmtime, reverse=True)
        sd = {}
        if scripts:
            sd = json.loads(scripts[0].read_text(encoding="utf-8"))
        sd["video_file"] = str(videos[0])
        url = uploader.upload_video(sd)
        await msg.edit_text(f"✅ تم الرفع!\n{url}")
    except Exception as e:
        await msg.edit_text(f"❌ فشل الرفع: {e}")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    chat_id = update.effective_chat.id
    task = _running_tasks.get(chat_id)
    if task and not task.done():
        task.cancel()
        await update.message.reply_text("⛔ جاري إلغاء التوليد...")
    else:
        await update.message.reply_text("ℹ️ لا يوجد توليد قيد التشغيل.")

async def retry_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retry the last failed episode."""
    if not await _check_auth(update, context):
        return
    log_path = _ROOT / "output" / "bot_error.log"
    if not log_path.exists():
        await update.message.reply_text("ℹ️ لا يوجد أخطاء سابقة لإعادة المحاولة.")
        return
    await update.message.reply_text("🔄 إعادة المحاولة...")
    # Just run generate again
    await generate_cmd(update, context)

async def log_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    log_path = _ROOT / "output" / "bot_error.log"
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")[-5:]
        await update.message.reply_text("📋 آخر أخطاء:\n" + "\n".join(lines))
    else:
        await update.message.reply_text("ℹ️ لا توجد أخطاء مسجلة.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update, context):
        return
    txt = (
        "🤖 بوت إنتاج الفيديوهات الإسلامية\n\n"
        "/start - القائمة الرئيسية\n"
        "/status - عرض تقدم المواسم\n"
        "/generate - توليد الحلقة التالية\n"
        "/generate <id> - توليد حلقة محددة (مثلاً /generate prophet_adam)\n"
        "/eps [1|2|3] - عرض حلقات الموسم\n"
        "/season - تحديد الموسم\n"
        "/preview - معاينة آخر فيديو\n"
        "/upload - رفع آخر فيديو لليوتيوب\n"
        "/cancel - إلغاء التوليد الجاري\n"
        "/retry - إعادة محاولة آخر فاشل\n"
        "/log - آخر أخطاء\n\n"
        "🔑 تحتاج إلى تعيين متغيرات البيئة:\n"
        "TELEGRAM_BOT_TOKEN - توكن البوت\n"
        "TELEGRAM_USER_ID - ايدي المستخدم المسموح"
    )
    await update.message.reply_text(txt)

def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN غير مضبوط!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(CommandHandler("eps", eps_cmd))
    app.add_handler(CommandHandler("season", season_cmd))
    app.add_handler(CommandHandler("preview", preview_cmd))
    app.add_handler(CommandHandler("upload", upload_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("retry", retry_cmd))
    app.add_handler(CommandHandler("log", log_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(season_callback, pattern="^season_"))

    print("✅ بوت تليجرام شغال! اضغط Ctrl+C للإيقاف")
    app.run_polling()

if __name__ == "__main__":
    main()
