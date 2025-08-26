from fastapi import FastAPI, Request
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os
import asyncio
from OCR import pipeline   # <-- your OCR pipeline

TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://your-app.onrender.com/webhook

# ---- Telegram App ----
telegram_app = Application.builder().token(TOKEN).build()

# ---- Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me an image, and I'll return the recognized text as a file.")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    file_path = f"downloads/{photo.file_id}.jpg"
    os.makedirs("downloads", exist_ok=True)
    await file.download_to_drive(file_path)

    detected_text = pipeline(file_path, bw=True)

    txt_file_path = f"downloads/{photo.file_id}.txt"
    with open(txt_file_path, "w", encoding="utf-8") as f:
        f.write(detected_text.strip())

    with open(txt_file_path, "rb") as f:
        await update.message.reply_document(document=InputFile(f, filename="result.txt"))

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_image))

# ---- FastAPI App ----
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Set webhook on startup
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await telegram_app.bot.set_webhook(webhook_url)
    print(f"Webhook set to {webhook_url}")

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
