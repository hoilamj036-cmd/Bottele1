import os
import re
import json
import time
import threading
import asyncio 
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List

# Thư viện cho web server ảo và Telegram
from flask import Flask
from telegram import Update, InputMediaVideo # <--- Quan trọng: Thêm InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- CẤU HÌNH TOKEN ---
# 👇👇👇 DÁN TOKEN CỦA BẠN VÀO DƯỚI ĐÂY 👇👇👇
BOT_TOKEN = "8412922032:AAEaSxCIDmzcC0IR2Zzu2_O-rJZK-5RtDOk" 

# --- BỘ NHỚ ĐỆM ĐỂ GOM VIDEO ---
ALBUM_BUFFER = {} 

# --- PHẦN GIỮ BOT SỐNG (KEEP ALIVE) CHO RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive! Running on Render."

def run_http():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_http)
    t.start()
# ---------------------------------------

DATA_FILE = "bot_data.json"

DEFAULTS: Dict[str, Any] = {
    "handle": "@baobubuoihihi36",
    "imei": "865201076151404",
    "lines_fixed": ["Tân thủ", "Qli hcb"],
    "total": 0, "l_count": 0, "mail": "",
    "last_active_date": "", "seen_message_ids": [],
    "last_video_unique_id": "", "last_video_ts": 0.0,
}

RP_RE = re.compile(r"\b(\d+)\s*rp\b|\brp\s*(\d+)\b", re.IGNORECASE)

# --- XỬ LÝ DATA ---
def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE): return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)

def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def get_chat_cfg(chat_id: int) -> Dict[str, Any]:
    data = load_data()
    cfg = data.get(str(chat_id), {})
    merged = {**DEFAULTS, **cfg}
    for k, v in DEFAULTS.items():
        if k not in merged: merged[k] = v
    data[str(chat_id)] = merged
    save_data(data)
    return merged

def set_chat_cfg(chat_id: int, **kwargs) -> Dict[str, Any]:
    data = load_data()
    cfg = data.get(str(chat_id), {**DEFAULTS})
    cfg = {**cfg, **kwargs}
    data[str(chat_id)] = cfg
    save_data(data)
    return cfg

def get_vn_time(): return datetime.now(timezone.utc) + timedelta(hours=7)
def get_vn_date_str() -> str: return f"{get_vn_time().day:02d}/{get_vn_time().month:02d}"

def get_auto_ca() -> str:
    h = get_vn_time().hour
    if 6 <= h < 15: return "Ca 1"
    elif 15 <= h < 19: return "Ca 2"
    else: return "Ca 3"

def parse_ip_rp_copy_style(text: str) -> Tuple[Optional[str], Optional[int]]:
    if not text: return None, None
    t = re.sub(r"[\r\n\t]+", " ", text).strip()
    t = re.sub(r"\s+", " ", t).strip()
    if not t: return None, None
    m = RP_RE.search(t)
    if m:
        rp = int(m.group(1) or m.group(2))
        ip_part = (t[:m.start()] + " " + t[m.end():]).strip()
        ip_part = re.sub(r"\s+", " ", ip_part).strip()
        return (ip_part if ip_part else None), rp
    nums = list(re.finditer(r"\d+", t))
    if not nums: return None, None
    last = nums[-1]
    rp = int(last.group(0))
    ip_part = (t[:last.start()] + " " + t[last.end():]).strip()
    ip_part = re.sub(r"\s+", " ", ip_part).strip()
    ip_part = ip_part.strip(" |,-")
    return (ip_part if ip_part else None), rp

def format_template(cfg: Dict[str, Any], ip: str, rp: int) -> str:
    date_str = get_vn_date_str()
    last_date = cfg.get("last_active_date", "")
    current_total = int(cfg.get("total", 0))
    current_l = int(cfg.get("l_count", 0))
    current_mail = cfg.get("mail", "")
    auto_ca = get_auto_ca()
    
    if last_date != date_str:
        current_total = 0
        current_l = 0
        current_mail = ""
        set_chat_cfg(cfg["_chat_id"], total=0, l_count=0, mail="", last_active_date=date_str)

    new_total = current_total + rp
    new_l = current_l + 1
    set_chat_cfg(cfg["_chat_id"], total=new_total, l_count=new_l, last_active_date=date_str)

    final_mail = current_mail
    header = f"{date_str} bảo {rp}rp 1k l{new_l}"
    fixed_lines = ["Tân thủ", "Qli hcb", "@baobubuoihihi36", "Imei 865201076151404"]
    parts_final = [header, *fixed_lines, f"Tổng {new_total}", f"Mail {final_mail}", f"Ip {ip}", f"{auto_ca}"]
    return "\n".join([p for p in parts_final if p])

# --- COMMANDS ---
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "=== MENU ===\n/setmail <mail>\n/rs : Xoá TẤT CẢ\n/status : Xem info\n"
        "• Giá: 1k (Fixed)\n• Ca: Auto (6h-15h-19h)\n*(Bot trả lại Video theo Album)*"
    )

async def setmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Dùng: /setmail <mail>")
    raw = context.args[0].strip().lower()
    final = f"{raw.split('@')[0]}@gmail.com" if "@" in raw else f"{raw}@gmail.com"
    set_chat_cfg(update.effective_chat.id, mail=final, last_active_date=get_vn_date_str())
    await update.message.reply_text(f"✅ Đã lưu: {final}")

async def rs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_chat_cfg(update.effective_chat.id, total=0, l_count=0, mail="", last_active_date=get_vn_date_str())
    await update.message.reply_text("✅ Đã xoá sạch.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_chat_cfg(update.effective_chat.id)
    await update.message.reply_text(f"Ca: {get_auto_ca()}\nGiá: 1k\nTổng: {cfg.get('total')}\nLần: {cfg.get('l_count')}\nMail: {cfg.get('mail')}")

# --- LOGIC GỬI ALBUM ---
async def send_album_delayed(chat_id, group_id, context):
    """Hàm này đợi 2s rồi gửi tất cả video trong buffer đi 1 lần"""
    await asyncio.sleep(2) # Đợi các video khác tới đủ
    
    if group_id not in ALBUM_BUFFER: return

    data = ALBUM_BUFFER[group_id]
    del ALBUM_BUFFER[group_id] # Xóa khỏi bộ nhớ đệm

    # Nếu không tính toán được nội dung (do không có caption ở bất kỳ video nào) -> Bỏ qua
    if not data.get('text'): return 

    # Tạo danh sách Media để gửi
    media_group = []
    files = data['files'] # Danh sách file_id
    text = data['text']

    for i, file_id in enumerate(files):
        # Chỉ gắn caption vào video đầu tiên
        caption = text if i == 0 else None
        media_group.append(InputMediaVideo(media=file_id, caption=caption))

    try:
        # Gửi cả cục đi 1 lúc
        await context.bot.send_media_group(chat_id=chat_id, media=media_group, reply_to_message_id=data['reply_id'])
    except Exception as e:
        print(f"Lỗi gửi album: {e}")

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = update.message
    if not msg or not msg.video: return

    group_id = msg.media_group_id
    caption = (msg.caption or "").strip()
    
    # 1. NẾU LÀ VIDEO ĐƠN LẺ (KHÔNG PHẢI ALBUM)
    if not group_id:
        if not caption: return
        ip, rp = parse_ip_rp_copy_style(caption)
        if ip and rp is not None:
            cfg = get_chat_cfg(chat_id)
            cfg["_chat_id"] = chat_id
            text = format_template(cfg, ip=ip, rp=rp)
            await msg.reply_video(video=msg.video.file_id, caption=text, reply_to_message_id=msg.message_id)
        return

    # 2. NẾU LÀ ALBUM (NHIỀU VIDEO)
    # Nếu là video đầu tiên của nhóm mà bot thấy -> Tạo bộ đệm
    if group_id not in ALBUM_BUFFER:
        ALBUM_BUFFER[group_id] = {
            'files': [], 
            'text': None, 
            'reply_id': msg.message_id # Reply vào tin nhắn đầu tiên
        }
        # Kích hoạt bộ đếm ngược để gửi
        asyncio.create_task(send_album_delayed(chat_id, group_id, context))

    # Thêm video hiện tại vào danh sách
    ALBUM_BUFFER[group_id]['files'].append(msg.video.file_id)

    # Nếu video này có caption -> Tính toán và lưu nội dung báo cáo
    if caption:
        ip, rp = parse_ip_rp_copy_style(caption)
        if ip and rp is not None:
            cfg = get_chat_cfg(chat_id)
            cfg["_chat_id"] = chat_id
            ALBUM_BUFFER[group_id]['text'] = format_template(cfg, ip=ip, rp=rp)

def main():
    if not BOT_TOKEN or "TOKEN" in BOT_TOKEN:
        print("⚠️ CẢNH BÁO: CHƯA CÓ TOKEN")
        return
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).connect_timeout(30).read_timeout(30).build()
    app.add_handler(CommandHandler("start", menu_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("setmail", setmail))
    app.add_handler(CommandHandler("rs", rs))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.VIDEO, on_video))
    print("Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
