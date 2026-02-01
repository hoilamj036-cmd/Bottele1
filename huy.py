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
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# --- CẤU HÌNH TOKEN ---
# 👇👇👇 DÁN TOKEN CỦA BẠN VÀO DƯỚI ĐÂY 👇👇👇
BOT_TOKEN = "8412922032:AAH-VKa10ewIH9TCLd-KaiLA6mw-gQwoJhc" 

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
    "gia": "1k3", 
    
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

def get_vn_date_str() -> str:
    now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
    return f"{now_vn.day:02d}/{now_vn.month:02d}"

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

# --- PHẦN TRANG TRÍ KÍ TỰ ĐẶC BIỆT ---
def format_template(cfg: Dict[str, Any], ip: str, rp: int) -> str:
    date_str = get_vn_date_str()
    last_date = cfg.get("last_active_date", "")
    
    current_total = int(cfg.get("total", 0))
    current_l = int(cfg.get("l_count", 0))
    current_mail = cfg.get("mail", "")
    current_ca = cfg.get("ca", "Ca 1")
    current_gia = cfg.get("gia", "1k3")

    # KIỂM TRA RESET NGÀY MỚI
    if last_date != date_str:
        current_total = 0
        current_l = 0
        current_mail = ""
        current_ca = "Ca 1"
        current_gia = "1k3"
        
        set_chat_cfg(cfg["_chat_id"], 
                     total=0, l_count=0, mail="", ca="Ca 1", gia="1k3", 
                     last_active_date=date_str)

    new_total = current_total + rp
    new_l = current_l + 1
    
    set_chat_cfg(cfg["_chat_id"], total=new_total, l_count=new_l, last_active_date=date_str)

    final_mail = current_mail if current_mail else "【⚠️ Chưa nhập Mail】"
    final_ca = current_ca
    final_gia = current_gia
    
    # --- DESIGN MỚI: DÙNG KÍ TỰ ĐẶC BIỆT VÀ HTML ---
    # Header dùng dấu ngoặc đặc biệt
    header = f"『 <b>{date_str}</b> 』 · ‹ ⚡ <b>{rp} RP</b> › · ‹ 💎 <b>{final_gia}</b> › · ‹ ↻ <b>L{new_l}</b> ›"
    
    # Các dòng cố định dùng khung
    fixed_lines = [
        "【🔰】 <b>Tân thủ</b>",
        "【🛡️】 <b>Qli hcb</b>",
        "»» @baobubuoihihi36 ««",
        "»» Imei <code>865201076151404</code> ««"
    ]

    # Phần nội dung chính với dải phân cách
    body = [
        "⊱⋅ ──────────── ⋅⊰",
        f"❖ <b>TỔNG: {new_total}</b> ❖",
        f"[✉] Mail: <code>{final_mail}</code>",  
        f"[🌐] IP: <code>{ip}</code>",          
        f"「🕒 <b>{final_ca}</b>」"
    ]

    parts_final = [header, *fixed_lines, *body]
    return "\n".join([p for p in parts_final if p])

# --- CÁC LỆNH (COMMANDS) ---

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "╔═══════════════╗\n"
        "   <b>☆ MENU ĐIỀU KHIỂN ☆</b>\n"
        "╚═══════════════╝\n\n"
        "‹✉› /setmail <code>mail</code> : Nhập mail (Auto @gmail)\n"
        "‹🕒› /setca <code>tên ca</code> : Nhập ca\n"
        "‹💎› /setgia <code>số</code> : 1=1k1, 3=1k3\n\n"
        "⟬ <b>RESET OPTIONS</b> ⟭\n"
        "‹↻› /rs : Xoá TẤT CẢ về mặc định\n\n"
        "‹📊› /status : Xem thông tin\n"
        "<i>(Bot tự động reset khi qua ngày mới)</i>",
        parse_mode=ParseMode.HTML
    )

async def setmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("[✖] Dùng: /setmail <mail mới>")
    raw_mail = context.args[0].strip().lower()
    final_mail = f"{raw_mail.split('@')[0]}@gmail.com" if "@" in raw_mail else f"{raw_mail}@gmail.com"
    
    set_chat_cfg(update.effective_chat.id, mail=final_mail, last_active_date=get_vn_date_str())
    await update.message.reply_text(f"【✔】 <b>Đã lưu mail:</b> <code>{final_mail}</code>", parse_mode=ParseMode.HTML)

async def setca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("[✖] Dùng: /setca <số ca>")
    raw = " ".join(context.args).strip()
    ca = f"Ca {raw}" if raw.isdigit() else raw
    
    set_chat_cfg(update.effective_chat.id, ca=ca, last_active_date=get_vn_date_str())
    await update.message.reply_text(f"【✔】 <b>Đã lưu ca:</b> {ca}", parse_mode=ParseMode.HTML)

async def setgia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("[✖] Dùng: /setgia 1 hoặc 3")
    raw = context.args[0].strip()
    if raw == "1": gia = "1k1"
    elif raw == "3": gia = "1k3"
    else: gia = " ".join(context.args).strip()

    set_chat_cfg(update.effective_chat.id, gia=gia, last_active_date=get_vn_date_str())
    await update.message.reply_text(f"【✔】 <b>Đã đổi giá:</b> {gia}", parse_mode=ParseMode.HTML)

async def rs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_chat_cfg(chat_id, total=0, l_count=0, mail="", ca="Ca 1", gia="1k3", last_active_date=get_vn_date_str())
    await update.message.reply_text("⟬♻️⟭ <b>Đã RESET toàn bộ dữ liệu!</b>", parse_mode=ParseMode.HTML)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_chat_cfg(update.effective_chat.id)
    text = (
        f"╔══ <b>TRẠNG THÁI HIỆN TẠI</b> ══╗\n"
        f" 🕒 Ca: <b>{cfg.get('ca')}</b>\n"
        f" 💎 Giá: <b>{cfg.get('gia', '1k3')}</b>\n"
        f" 🏆 Tổng: <b>{cfg.get('total')}</b>\n"
        f" ↻ Lần: <b>{cfg.get('l_count')}</b>\n"
        f" ✉ Mail: <code>{cfg.get('mail')}</code>\n"
        f" 📅 Ngày check: {cfg.get('last_active_date')}\n"
        f"╚══════════════════╝"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cfg = get_chat_cfg(chat_id)
    cfg["_chat_id"] = chat_id
    msg = update.message
    if not msg or not msg.video: return

    vu = msg.video.file_unique_id
    if vu == cfg.get("last_video_unique_id") and (time.time() - cfg.get("last_video_ts", 0)) < 10: return
    set_chat_cfg(chat_id, last_video_unique_id=vu, last_video_ts=time.time())

    mid = msg.message_id
    seen = cfg.get("seen_message_ids", [])
    if mid in seen: return
    seen.append(mid)
    set_chat_cfg(chat_id, seen_message_ids=seen[-100:])

    caption = (msg.caption or "").strip()
    if msg.media_group_id and not caption: return
    ip, rp = parse_ip_rp_copy_style(caption)
    if not ip or rp is None: return await msg.reply_text("【✖】 <b>Lỗi:</b> Không tìm thấy IP hoặc RP.", parse_mode=ParseMode.HTML)

    text = format_template(cfg, ip=ip, rp=rp)
    
    await msg.reply_text(text, reply_to_message_id=msg.message_id, parse_mode=ParseMode.HTML)

def main():
    if not BOT_TOKEN or "TOKEN" in BOT_TOKEN:
        print("⚠️ CẢNH BÁO: CHƯA CÓ TOKEN")
        return
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).connect_timeout(30).read_timeout(30).build()
    app.add_handler(CommandHandler("start", menu_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("setmail", setmail))
    app.add_handler(CommandHandler("setca", setca))
    app.add_handler(CommandHandler("setgia", setgia))
    app.add_handler(CommandHandler("rs", rs))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.VIDEO, on_video))
    print("Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
