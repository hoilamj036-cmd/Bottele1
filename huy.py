import os
import re
import json
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List

# Thư viện cho web server ảo và Telegram
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- CẤU HÌNH TOKEN ---
BOT_TOKEN = "8412922032:AAHFZF0AGMXXFP5GNWhPpMfumRasQI6ELlk"

# --- PHẦN GIỮ BOT SỐNG (KEEP ALIVE) CHO RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive! Running on Render."

def run_http():
    # Lấy PORT từ biến môi trường của Render
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_http)
    t.start()
# ---------------------------------------

DATA_FILE = "bot_data.json"

# Cấu hình mặc định
DEFAULTS: Dict[str, Any] = {
    "handle": "@baobubuoihihi36",
    "imei": "865201076151404",
    "lines_fixed": ["Tân thủ", "Qli hcb"],
    
    "total": 0,
    "l_count": 0,
    "mail": "",         
    "ca": "Ca 1",
    "gia": "1k3", # Giá mặc định
    
    "last_active_date": "",
    "seen_message_ids": [],
    "last_video_unique_id": "",
    "last_video_ts": 0.0,
}

RP_RE = re.compile(r"\b(\d+)\s*rp\b|\brp\s*(\d+)\b", re.IGNORECASE)

# --- XỬ LÝ DATA ---
def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_chat_cfg(chat_id: int) -> Dict[str, Any]:
    data = load_data()
    cfg = data.get(str(chat_id), {})
    merged = {**DEFAULTS, **cfg}
    for k, v in DEFAULTS.items():
        if k not in merged:
            merged[k] = v
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

# --- LOGIC XỬ LÝ TEXT ---
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
    # 1. Lấy ngày giờ Việt Nam (UTC+7)
    now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
    date_str = f"{now_vn.day:02d}/{now_vn.month:02d}"

    # 2. Kiểm tra sang ngày mới -> AUTO RESET TOÀN BỘ
    last_date = cfg.get("last_active_date", "")
    
    current_total = int(cfg.get("total", 0))
    current_l = int(cfg.get("l_count", 0))
    current_mail = cfg.get("mail", "")
    current_ca = cfg.get("ca", "Ca 1")

    if last_date != date_str:
        # Nếu khác ngày => Reset về 0 và xóa sạch thông tin phiên cũ
        current_total = 0
        current_l = 0
        current_mail = ""   # Reset mail
        current_ca = "Ca 1" # Reset ca
        
        # Lưu lại trạng thái reset ngay lập tức
        set_chat_cfg(cfg["_chat_id"], 
                     total=0, 
                     l_count=0, 
                     mail="", 
                     ca="Ca 1", 
                     last_active_date=date_str)

    # 3. Tính toán cộng dồn
    new_total = current_total + rp
    new_l = current_l + 1
    
    # Lưu lại data mới
    set_chat_cfg(cfg["_chat_id"], total=new_total, l_count=new_l, last_active_date=date_str)

    # 4. Format nội dung
    gia = cfg.get("gia", "1k3") # Lấy giá hiện tại
    header = f"{date_str} bảo {rp}rp {gia} l{new_l}"
    
    fixed_lines = [
        "Tân thủ",
        "Qli hcb",
        "@baobubuoihihi36",
        "Imei 865201076151404"
    ]

    parts_final = [
        header,
        *fixed_lines,
        f"Tổng {new_total}",
        f"Mail {current_mail}", # Dùng mail đã xử lý (nếu reset thì là rỗng)
        f"Ip {ip}",
        f"{current_ca}"         # Dùng ca đã xử lý
    ]

    return "\n".join([p for p in parts_final if p])

# --- CÁC LỆNH (COMMANDS) ---

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "=== DANH SÁCH LỆNH ===\n"
        "/setmail <mail> : Nhập mail (Auto @gmail.com)\n"
        "/setca <tên ca> : Nhập ca (VD: /setca 2)\n"
        "/setgia <giá> : Chỉnh giá tiền (VD: /setgia 1k1)\n"
        "\n--- RESET ---\n"
        "/rs : Xoá TẤT CẢ (Tổng=0, Lần=0, Mail trống, Ca=Ca 1)\n"
        "\n--- KHÁC ---\n"
        "/status : Xem thông tin\n"
        "*(Bot tự động reset TẤT CẢ khi qua ngày mới)*"
    )

async def setmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Dùng: /setmail <mail mới>")
    
    raw_mail = context.args[0].strip()
    clean_mail = raw_mail.lower()
    
    if "@" in clean_mail:
        username = clean_mail.split("@")[0]
        final_mail = f"{username}@gmail.com"
    else:
        final_mail = f"{clean_mail}@gmail.com"

    set_chat_cfg(update.effective_chat.id, mail=final_mail)
    await update.message.reply_text(f"✅ Đã lưu mail: {final_mail}")

async def setca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Dùng: /setca <số ca> (Ví dụ: /setca 2)")
    
    raw = " ".join(context.args).strip()
    
    if raw.isdigit():
        ca = f"Ca {raw}"
    else:
        ca = raw
        
    set_chat_cfg(update.effective_chat.id, ca=ca)
    await update.message.reply_text(f"✅ Đã lưu ca: {ca}")

async def setgia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Dùng: /setgia <giá> (Ví dụ: /setgia 1k1)")
    
    gia_moi = " ".join(context.args).strip()
    set_chat_cfg(update.effective_chat.id, gia=gia_moi)
    await update.message.reply_text(f"✅ Đã đổi giá thành: {gia_moi}")

async def rs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Reset toàn bộ
    set_chat_cfg(chat_id, total=0, l_count=0, mail="", ca="Ca 1")
    await update.message.reply_text("✅ Đã xoá sạch: Tổng=0, Lần=0, Mail=(trống), Ca=Ca 1.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_chat_cfg(update.effective_chat.id)
    await update.message.reply_text(
        f"Ca: {cfg.get('ca')}\n"
        f"Giá: {cfg.get('gia', '1k3')}\n"
        f"Tổng: {cfg.get('total')}\n"
        f"Lần: {cfg.get('l_count')}\n"
        f"Mail: {cfg.get('mail')}\n"
        f"Ngày check: {cfg.get('last_active_date')} (VN)"
    )

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cfg = get_chat_cfg(chat_id)
    cfg["_chat_id"] = chat_id

    msg = update.message
    if not msg or not msg.video: return

    # Chống spam/trùng lặp
    vu = msg.video.file_unique_id
    if vu == cfg.get("last_video_unique_id") and (time.time() - cfg.get("last_video_ts", 0)) < 10:
        return
    set_chat_cfg(chat_id, last_video_unique_id=vu, last_video_ts=time.time())

    mid = msg.message_id
    seen = cfg.get("seen_message_ids", [])
    if mid in seen: return
    seen.append(mid)
    set_chat_cfg(chat_id, seen_message_ids=seen[-100:])

    caption = (msg.caption or "").strip()
    if msg.media_group_id and not caption: return

    ip, rp = parse_ip_rp_copy_style(caption)
    if not ip or rp is None:
        return await msg.reply_text("❌ Lỗi: Thiếu IP hoặc RP.")

    text = format_template(cfg, ip=ip, rp=rp)
    
    # Reply chuẩn
    await msg.reply_text(text, reply_to_message_id=msg.message_id)

def main():
    if not BOT_TOKEN or "MỚI" in BOT_TOKEN:
        print("⚠️ CẢNH BÁO: CHƯA CÓ TOKEN")
        return

    keep_alive()

    app = Application.builder().token(BOT_TOKEN).connect_timeout(30).read_timeout(30).build()

    app.add_handler(CommandHandler("start", menu_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("setmail", setmail))
    app.add_handler(CommandHandler("setca", setca))
    app.add_handler(CommandHandler("setgia", setgia)) # Thêm lệnh setgia
    app.add_handler(CommandHandler("rs", rs))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(MessageHandler(filters.VIDEO, on_video))

    print("Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
