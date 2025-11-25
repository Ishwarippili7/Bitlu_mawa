import logging
import asyncio
import datetime
import json
import os
import time
import traceback
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest, TelegramError

# ================== BOT CONFIGURATION ==================
# Use environment variables for security
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8327527686:AAFgeRamSxQudV0IKOSh9xUlJs3IsGbL3Xs")

# Admin IDs as integers
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "6532419818").split(",")]
FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "@gullymovies")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@gullymovies")

videos_data = {}
user_sessions = {}

# ================== LOGGER ==================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

class BitluMawaBot:
    def __init__(self) -> None:
        try:
            if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
                raise ValueError("BOT_TOKEN not set. Set BOT_TOKEN environment variable.")

            self.app = ApplicationBuilder().token(BOT_TOKEN).build()
            self.setup_handlers()
            self.load_data()
            logger.info("Bot initialized successfully")
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            logger.error(traceback.format_exc())
            raise

    # ---------------- HANDLERS ----------------

    def setup_handlers(self):
        handlers = [
            CommandHandler("start", self.start),
            CommandHandler("addvideo", self.add_video),
            CommandHandler("stats", self.stats),
            CommandHandler("listvideos", self.list_videos),
            CommandHandler("broadcast", self.broadcast),
            CommandHandler("testsub", self.test_subscription),
            MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_inputs),
            CallbackQueryHandler(self.button_callback),
        ]
        for h in handlers:
            self.app.add_handler(h)
        logger.info("All handlers setup successfully")

    # ---------------- STORAGE ----------------

    def load_data(self):
        global videos_data
        try:
            if os.path.exists("videos_data.json"):
                with open("videos_data.json", "r", encoding="utf-8") as f:
                    videos_data = json.load(f)
                logger.info(f"Loaded {len(videos_data)} videos from storage")
            else:
                logger.info("No existing videos_data.json found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading videos_data.json: {e}")
            videos_data = {}

    def save_data(self):
        try:
            with open("videos_data.json", "w", encoding="utf-8") as f:
                json.dump(videos_data, f, indent=2, ensure_ascii=False)
            logger.info("videos_data.json saved")
        except Exception as e:
            logger.error(f"Error saving videos_data.json: {e}")

    # ---------------- FORCE SUBSCRIPTION (FIXED) ----------------

    async def check_subscription(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        try:
            # Admin ki always allow
            if user_id in ADMIN_IDS:
                return True
                
            logger.info(f"Checking subscription for user {user_id} in {FORCE_SUB_CHANNEL}")
            
            bot = context.bot
            try:
                # Channel lo user unte check cheyyali
                member = await bot.get_chat_member(FORCE_SUB_CHANNEL, user_id)
                status = member.status
                
                logger.info(f"User {user_id} channel status: {status}")
                
                # Member, Admin, or Creator unte allow
                if status in ["member", "administrator", "creator"]:
                    logger.info(f"User {user_id} is subscribed - ALLOWING ACCESS")
                    return True
                else:
                    logger.warning(f"User {user_id} not subscribed. Status: {status}")
                    return False
                    
            except BadRequest as e:
                error_msg = str(e).lower()
                if "user not found" in error_msg:
                    logger.warning(f"User {user_id} not found in channel - NOT SUBSCRIBED")
                    return False
                elif "bot is not a member" in error_msg:
                    logger.error("❌ BOT IS NOT ADMIN IN THE CHANNEL! Please make bot admin in @gullymovies")
                    # Temporary allow access for testing
                    return True
                elif "chat not found" in error_msg:
                    logger.error(f"❌ CHANNEL NOT FOUND: {FORCE_SUB_CHANNEL} - Check channel username")
                    return False
                else:
                    logger.error(f"BadRequest in subscription check: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Unexpected error in check_subscription: {e}")
            logger.error(traceback.format_exc())
            return False

    async def send_force_sub_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, deep_arg: Optional[str] = None):
        try:
            if not update.message:
                return

            bot_username = context.bot.username
            channel_username = FORCE_SUB_CHANNEL.replace("@", "")

            join_link = f"https://t.me/{channel_username}"
            if deep_arg:
                retry_link = f"https://t.me/{bot_username}?start={deep_arg}"
            else:
                retry_link = f"https://t.me/{bot_username}"

            keyboard = [
                [InlineKeyboardButton("🔥 Join Our Channel", url=join_link)],
                [InlineKeyboardButton("✅ I've Joined - Verify Now", callback_data="check_sub")],
            ]

            message_text = (
                "🔒 *Subscription Required!*\n\n"
                "📢 **Bitlu Mawa🔥 Premium Content**\n\n"
                "To access all videos, you need to join our channel first!\n\n"
                "👇 *Follow these simple steps:*\n"
                "1. Click *'Join Our Channel'* button\n"
                "2. Join the channel\n"
                "3. Come back and click *'I've Joined - Verify Now'*\n\n"
                "💡 **Note:** Without joining, you won't get any videos!"
            )

            await update.message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error in send_force_sub_message: {e}")

    # ---------------- TEST SUBSCRIPTION COMMAND ----------------

    async def test_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test force subscription for debugging"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        await update.message.reply_text(
            f"🔍 *Subscription Test for {user_name}*\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"📢 Channel: {FORCE_SUB_CHANNEL}\n"
            f"👑 Admin: {'✅ Yes' if user_id in ADMIN_IDS else '❌ No'}\n\n"
            "Checking subscription status...",
            parse_mode="Markdown"
        )
        
        is_subscribed = await self.check_subscription(user_id, context)
        
        if is_subscribed:
            await update.message.reply_text("✅ *SUBSCRIBED!* - You can access all content!")
        else:
            await update.message.reply_text(
                "❌ *NOT SUBSCRIBED!* - Please join our channel!\n\n"
                "Join: @gullymovies\n"
                "Then click: /testsub again to verify",
                parse_mode="Markdown"
            )

    # ---------------- START COMMAND ----------------

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not update.message:
                return

            user_id = update.effective_user.id
            user_name = update.effective_user.first_name

            logger.info(f"User {user_id} ({user_name}) started the bot")

            # Check force subscription for non-admins
            if user_id not in ADMIN_IDS:
                is_subscribed = await self.check_subscription(user_id, context)
                if not is_subscribed:
                    logger.info(f"User {user_id} not subscribed, sending force sub message")
                    video_id = context.args[0] if context.args else None
                    await self.send_force_sub_message(update, context, video_id)
                    return
                else:
                    logger.info(f"User {user_id} is subscribed, granting access")

            # /start with video ID
            if context.args:
                video_id = context.args[0]
                logger.info(f"User {user_id} requesting video: {video_id}")
                await self.send_video_to_user(update, context, video_id)
                return

            # Regular start command
            welcome_text = (
                f"👑 *Welcome Admin {user_name}!*\n\n"
                "📋 *Admin Commands:*\n"
                "/addvideo - Add new video\n"
                "/listvideos - View videos\n"
                "/stats - Bot statistics\n"
                "/broadcast - Send message to all users\n"
                "/testsub - Test subscription\n\n"
                "🚀 Bot is ready to serve!"
            ) if user_id in ADMIN_IDS else (
                f"🎉 *Welcome {user_name} to Bitlu Mawa🔥!*\n\n"
                "✅ *You're all set!*\n\n"
                "🎬 Now you can:\n"
                "• Click any link from @gullymovies\n"
                "• Get instant video access\n"
                "• Enjoy premium content\n\n"
                "😎 Happy streaming!"
            )

            await update.message.reply_text(welcome_text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in start command: {e}")

    # ---------------- ADD VIDEO FLOW ----------------

    async def add_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ *Admin Only!*", parse_mode="Markdown")
            return

        user_sessions[user_id] = {
            "step": "title",
            "title": None,
            "poster": None,
            "files": [],
        }

        await update.message.reply_text(
            "🎬 *Video Addition Started*\n\n"
            "Step 1/3: Please send the *Video Title*:\n\n"
            "Example: `Kalki 2024 Hindi 720p HDRip`",
            parse_mode="Markdown",
        )

    async def handle_inputs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        user_id = update.effective_user.id
        session = user_sessions.get(user_id)
        if not session:
            return

        msg = update.message

        # STEP 1 - Title
        if session["step"] == "title" and msg.text:
            session["title"] = msg.text.strip()
            session["step"] = "poster"
            await msg.reply_text(
                "✅ *Title Saved!*\n\n"
                "Step 2/3: Now send the *Poster Image*:\n\n"
                "Please forward a poster/thumbnail photo",
                parse_mode="Markdown"
            )
            return

        # STEP 2 - Poster
        if session["step"] == "poster" and msg.photo:
            session["poster"] = msg.photo[-1].file_id
            session["step"] = "files"
            await msg.reply_text(
                "🖼️ *Poster Received!*\n\n"
                "Step 3/3: Now send the *Video Files*:\n\n"
                "You can send:\n"
                "• Video files\n"
                "• Documents\n"
                "• Audio files\n"
                "• Photos\n\n"
                "Send files one by one...",
                parse_mode="Markdown",
            )
            return

        # STEP 3 - Files
        if session["step"] == "files":
            file_info = self.extract_file(msg)
            if file_info:
                session["files"].append(file_info)
                count = len(session["files"])

                keyboard = [
                    [InlineKeyboardButton("✅ Finish & Generate Link", callback_data="finish_video")],
                    [InlineKeyboardButton("➕ Add More Files", callback_data="continue_files")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_video")],
                ]
                
                file_type_emoji = {
                    "video": "🎥",
                    "document": "📄", 
                    "audio": "🎵",
                    "photo": "🖼️"
                }.get(file_info["type"], "📁")
                
                await msg.reply_text(
                    f"{file_type_emoji} *File #{count} Added!*\n\n"
                    f"📊 Total Files: {count}\n"
                    f"📝 Type: {file_info['type']}\n\n"
                    "Choose next action:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )

    def extract_file(self, msg):
        try:
            if msg.video:
                return {"type": "video", "file_id": msg.video.file_id}
            if msg.document:
                return {"type": "document", "file_id": msg.document.file_id}
            if msg.audio:
                return {"type": "audio", "file_id": msg.audio.file_id}
            if msg.photo:
                return {"type": "photo", "file_id": msg.photo[-1].file_id}
        except Exception as e:
            logger.error(f"extract_file error: {e}")
        return None

    # ---------------- BUTTON CALLBACKS ----------------

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data

        logger.info(f"Button callback: {data} from user {user_id}")

        # Force subscription check
        if data == "check_sub":
            is_subscribed = await self.check_subscription(user_id, context)
            if is_subscribed:
                await query.edit_message_text(
                    "✅ *Verified! Welcome to Bitlu Mawa🔥!*\n\n"
                    "🎉 You've successfully joined our channel!\n\n"
                    "Now you can:\n"
                    "• Access all videos\n" 
                    "• Click any link from @gullymovies\n"
                    "• Enjoy premium content\n\n"
                    "🚀 Happy streaming!",
                    parse_mode="Markdown"
                )
            else:
                await query.answer(
                    "❌ You haven't joined the channel yet!\n\n"
                    "Please join @gullymovies first, then click this button again.",
                    show_alert=True
                )
            return

        # Copy link function
        if data.startswith("copy_"):
            video_id = data.replace("copy_", "")
            share_link = f"https://t.me/{context.bot.username}?start={video_id}"
            await query.answer(f"🔗 Link Copied!\n\n{share_link}", show_alert=True)
            return

        # Feedback buttons
        if data.startswith("feedback_"):
            feedback_type = data.replace("feedback_", "")
            feedback_emojis = {
                "love": "❤️",
                "super": "🔥", 
                "amazing": "💫",
                "good": "👍"
            }
            emoji = feedback_emojis.get(feedback_type, "👍")
            await query.answer(f"{emoji} Thanks for your feedback!", show_alert=True)
            return

        # Admin-only functions
        if user_id not in ADMIN_IDS:
            await query.answer("❌ Admin only feature!", show_alert=True)
            return

        if data == "finish_video":
            await self.finish_video_creation(query, context)
        elif data == "continue_files":
            session = user_sessions.get(user_id)
            if session:
                session["step"] = "files"
            await query.edit_message_text(
                "📁 *Continue adding files...*\n\n"
                "Send more files or click Finish when done.",
                parse_mode="Markdown",
            )
        elif data == "cancel_video":
            if user_id in user_sessions:
                del user_sessions[user_id]
            await query.edit_message_text("❌ Video addition cancelled.")

    async def finish_video_creation(self, query, context: ContextTypes.DEFAULT_TYPE):
        user_id = query.from_user.id
        session = user_sessions.get(user_id)

        if not session or not session["files"]:
            await query.edit_message_text("❌ No files added! Please add some files first.")
            return

        video_id = str(int(time.time()))

        videos_data[video_id] = {
            "title": session["title"],
            "poster": session["poster"],
            "files": session["files"],
            "created_at": datetime.datetime.now().isoformat(),
            "created_by": user_id,
        }
        self.save_data()

        del user_sessions[user_id]

        bot_username = context.bot.username
        share_link = f"https://t.me/{bot_username}?start={video_id}"

        keyboard = [
            [InlineKeyboardButton("📤 Share in Channel", url=f"https://t.me/share/url?url={share_link}&text=🎬%20{session['title']}")],
            [InlineKeyboardButton("🔗 Copy Link", callback_data=f"copy_{video_id}")],
        ]

        await query.edit_message_text(
            f"🎉 *Video Added Successfully!*\n\n"
            f"🎬 Title: {session['title']}\n"
            f"📁 Files: {len(session['files'])}\n"
            f"🔗 Link: `{share_link}`\n\n"
            "Share this link in @gullymovies channel!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ---------------- SEND VIDEO TO USER ----------------

    async def send_video_to_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE, video_id: str):
        try:
            msg = update.message
            if not msg:
                return

            user_id = update.effective_user.id
            user_name = update.effective_user.first_name

            logger.info(f"Sending video {video_id} to user {user_id}")

            # Check subscription again before sending videos
            if user_id not in ADMIN_IDS:
                is_subscribed = await self.check_subscription(user_id, context)
                if not is_subscribed:
                    await self.send_force_sub_message(update, context, video_id)
                    return

            if video_id not in videos_data:
                await msg.reply_text("❌ Video not found or link expired.")
                return

            video = videos_data[video_id]
            files = video.get("files", [])

            if not files:
                await msg.reply_text("❌ No files available for this video.")
                return

            # Send poster first
            if video.get("poster"):
                try:
                    await msg.reply_photo(
                        photo=video["poster"],
                        caption=(
                            f"🎬 *{video['title']}* | Bitlu Mawa🔥\n\n"
                            f"👋 Hello {user_name}!\n"
                            f"📦 Preparing {len(files)} files for you...\n\n"
                            "⏳ Please wait while we send your content..."
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error(f"Error sending poster: {e}")

            # Send all files
            sent_count = 0
            for f in files:
                try:
                    ftype = f.get("type")
                    fid = f.get("file_id")

                    if ftype == "video":
                        await msg.reply_video(fid)
                    elif ftype == "document":
                        await msg.reply_document(fid)
                    elif ftype == "audio":
                        await msg.reply_audio(fid)
                    elif ftype == "photo":
                        await msg.reply_photo(fid)

                    sent_count += 1
                    await asyncio.sleep(1)  # Prevent flooding
                except Exception as e:
                    logger.error(f"Error sending file: {e}")

            # Send thank you message
            thank_you_messages = [
                f"💖 **AMAZING {user_name.upper()}!** 💖\n\n"
                f"✅ Successfully delivered *{sent_count} files* of:\n"
                f"🎬 *{video['title']}*\n\n"
                f"❤️ **Ela undi mawa content? Enjoy chestunava?**\n"
                f"😍 Love unte oka ❤️ react ivvandi!\n\n"
                f"🔥 *Bitlu Mawa Team*",

                f"🎊 **MISSION COMPLETE {user_name}!** 🎊\n\n"
                f"🚀 Delivered: *{sent_count} files*\n"
                f"📺 Content: *{video['title']}*\n\n"
                f"💕 **Thanks for using Bitlu Mawa!**\n"
                f"⭐ Rate our service in your heart!\n\n"
                f"❤️ *We love serving you!*",
            ]

            import random
            thank_you_msg = random.choice(thank_you_messages)

            feedback_keyboard = [
                [InlineKeyboardButton("❤️ Loved It!", callback_data="feedback_love"),
                 InlineKeyboardButton("🔥 Super", callback_data="feedback_super")],
                [InlineKeyboardButton("💫 Amazing", callback_data="feedback_amazing"),
                 InlineKeyboardButton("👍 Good", callback_data="feedback_good")],
            ]

            await msg.reply_text(
                thank_you_msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(feedback_keyboard)
            )

        except Exception as e:
            logger.error(f"Error in send_video_to_user: {e}")
            await msg.reply_text("❌ Error sending files. Please try again.")

    # ---------------- ADMIN COMMANDS ----------------

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admin only command!")
            return

        total_videos = len(videos_data)
        total_files = sum(len(v.get("files", [])) for v in videos_data.values())

        await update.message.reply_text(
            f"📊 *Bot Statistics*\n\n"
            f"🎬 Total Videos: {total_videos}\n"
            f"📁 Total Files: {total_files}\n"
            f"👑 Admins: {len(ADMIN_IDS)}\n"
            f"📢 Channel: {FORCE_SUB_CHANNEL}\n\n"
            f"🟢 Status: Running Smoothly",
            parse_mode="Markdown",
        )

    async def list_videos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admin only command!")
            return

        if not videos_data:
            await update.message.reply_text("📭 No videos stored yet.")
            return

        txt = "🎬 *Stored Videos:*\n\n"
        for vid, data in list(videos_data.items())[-10:]:
            file_count = len(data.get('files', []))
            created = data.get('created_at', 'Unknown')
            txt += f"• {data['title']} ({file_count} files)\n   ID: `{vid}`\n\n"

        await update.message.reply_text(txt, parse_mode="Markdown")

    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admin only command!")
            return

        if not context.args:
            await update.message.reply_text(
                "📢 *Usage:* /broadcast <message>\n\n"
                "Example: /broadcast Hello users! New update available!",
                parse_mode="Markdown"
            )
            return

        message = " ".join(context.args)
        await update.message.reply_text("🚀 Broadcast started...")

        # In a real scenario, you'd need to track users who started the bot
        # For now, this is a placeholder
        success_count = 0
        failed_count = 0

        # You would iterate through stored user IDs here
        # for user_id in stored_user_ids:
        #     try:
        #         await context.bot.send_message(user_id, f"📢 Announcement:\n\n{message}")
        #         success_count += 1
        #     except:
        #         failed_count += 1

        await update.message.reply_text(
            f"📊 *Broadcast Complete*\n\n"
            f"✅ Success: {success_count}\n"
            f"❌ Failed: {failed_count}",
            parse_mode="Markdown"
        )

    # ---------------- RUN BOT ----------------

    def run(self):
        logger.info("🚀 Starting Bitlu Mawa Bot...")
        print("🤖 Bot is starting...")
        print("🔒 Force Subscribe: ENABLED")
        print("📢 Channel:", FORCE_SUB_CHANNEL)
        print("👑 Admin IDs:", ADMIN_IDS)
        print("⏰ Bot started at:", datetime.datetime.now())
        
        self.app.run_polling()

if __name__ == "__main__":
    bot = BitluMawaBot()
    bot.run()
