import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    """
    ቪዲዮው ላይ High-End Glow እና Sharpness የሚጨምር Advanced FFmpeg ትዕዛዝ።
    """
    # ይህ ማጣሪያ (Filter) ቪዲዮውን ደራርቦ ብርሃኑን ያጎላል (Bloom Effect)
    video_filters = (
        "scale=720:-2:flags=lanczos," # ጥራት ያለው Scale
        "split[main][blur];" # ቪዲዮውን ለሁለት መክፈል
        "[blur]scale=iw/2:ih/2,boxblur=10:1,scale=iw*2:ih*2[bloomed];" # አንዱን ማደብዘዝ (Glow ለመፍጠር)
        "[main][bloomed]blend=all_mode='screen':all_opacity=0.3," # ሁለቱን ማቀላቀል
        "unsharp=5:5:2.0:5:5:0.0," # በጣም ጠንካራ Sharpness
        "eq=saturation=1.8:contrast=1.3:brightness=0.04" # ደማቅ ቀለም
    )
    
    command = [
        'ffmpeg', '-y', 
        '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',
        '-crf', '18', # ከፍተኛ ጥራት
        '-c:a', 'copy', 
        output_path
    ]
    
    try:
        # ለዚህ ስራ እስከ 180 ሰከንድ (3 ደቂቃ) ታገሰው
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode == 0:
            return True
        logging.error(f"FFmpeg Error: {result.stderr}")
        return False
    except Exception as e:
        logging.error(f"Error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    if any(site in url for site in ["tiktok.com", "instagram.com", "youtube.com", "shorts", "reels"]):
        status_msg = await update.message.reply_text("🎬 High-End ኤዲቲንግ እየሰራሁ ነው... ⏳")
        
        chat_id = update.message.chat_id
        input_file = f"in_{chat_id}.mp4"
        output_file = f"out_{chat_id}.mp4"
        
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'overwrites': True,
            'quiet': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ Glow እና 4K Sharpness እየጨመርኩ ነው... 🚀")
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("✅ ኤዲቲንግ ተጠናቀቀ! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="Premium 4K Glow Edit 🔥")
            else:
                await status_msg.edit_text("⚠️ RAM እጥረት ስላለ ይሄን ከባድ ኤዲቲንግ መስራት አልተቻለም።")
            
        except Exception as e:
            await update.message.reply_text(f"❌ ስህተት: {str(e)[:100]}")
        
        finally:
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("ቦቱ ስራ ጀምሯል...")
    app.run_polling()
