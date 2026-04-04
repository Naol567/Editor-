import os
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import yt_dlp

# የቦትህን Token እዚህ ጋር ተካው
TOKEN = "YOUR_BOT_TOKEN_HERE"

async def process_video(input_path, output_path):
    # ያንተ "Glow & High Quality" ፕሮምፕት
    prompt = (
        "scale=1080:-2:flags=lanczos,"
        "unsharp=5:5:1.2:5:5:0.0,"
        "eq=saturation=1.6:contrast=1.2:brightness=0.03"
    )
    command = [
        'ffmpeg', '-i', input_path,
        '-vf', prompt,
        '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
        '-c:a', 'copy', output_path
    ]
    subprocess.run(command)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "tiktok.com" in url or "instagram.com" in url:
        sent_message = await update.message.reply_text("ቪዲዮውን በማውረድ ላይ ነኝ... ⏳")
        
        ydl_opts = {'outtmpl': 'input_video.mp4', 'format': 'bestvideo+bestaudio/best'}
        
        try:
            # ቪዲዮውን ማውረድ
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await sent_message.edit_text("ጥራቱን በመጨመር ላይ ነኝ (4K Edit)... ✨")
            
            # ጥራቱን መጨመር
            await process_video('input_video.mp4', 'output_4k.mp4')
            
            # መላክ
            await update.message.reply_video(video=open('output_4k.mp4', 'rb'), caption="ባለ 4K ጥራት ቪዲዮህ ዝግጁ ነው! 🔥")
            
            # ፋይሎችን ማጽዳት (Storage እንዳይሞላ)
            os.remove('input_video.mp4')
            os.remove('output_4k.mp4')
            
        except Exception as e:
            await update.message.reply_text(f"ስህተት ተከስቷል፦ {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("ቦቱ እየሰራ ነው...")
    app.run_polling()
