import os
from fastapi import FastAPI, Request
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from OCR import pipeline   # your OCR function

# --- Config ---
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "changeme")  # any random string
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render sets this automatically

# --- Telegram Application ---
application = Application.builder().token(TOKEN).build()

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me an image, and I'll return the recognized text as a file.")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    detected_text = pipeline(file_path, bw=True)

    txt_file_path = f"downloads/{photo.file_id}.txt"
    with open(txt_file_path, "w", encoding="utf-8") as f:
        f.write(detected_text.strip())

    with open(txt_file_path, "rb") as f:
        await update.message.reply_document(document=InputFile(f, filename="result.txt"))

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.PHOTO, handle_image))

# --- FastAPI app ---
app = FastAPI()

@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await application.initialize()
    if not BASE_URL:
        raise RuntimeError("RENDER_EXTERNAL_URL not set")
    await application.bot.set_webhook(
        url=f"{BASE_URL}/webhook/{WEBHOOK_SECRET}",
        drop_pending_updates=True
    )
    await application.start()

@app.on_event("shutdown")
async def on_shutdown():
    await application.stop()
    await application.shutdown()

@app.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        return {"ok": False}
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
