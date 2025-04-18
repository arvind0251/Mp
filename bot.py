import json import requests import threading import time from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters import os

DATA_FILE = "bot_data.json"

def save_data(): data = { "USER_DATA": USER_DATA, "SERVICE_PRICING": SERVICE_PRICING, "COUNTRIES": COUNTRIES } with open(DATA_FILE, "w") as f: json.dump(data, f)

def load_data(): global USER_DATA, SERVICE_PRICING, COUNTRIES if os.path.exists(DATA_FILE): with open(DATA_FILE, "r") as f: data = json.load(f) USER_DATA = data.get("USER_DATA", {}) SERVICE_PRICING = data.get("SERVICE_PRICING", {}) COUNTRIES = data.get("COUNTRIES", {})

ADMIN_ID = 7459732827 USER_DATA = {} SERVICE_PRICING = {} COUNTRIES = {}

UPI_ID = "BHARATPE.8X0M0S6J8F70781@fbpe" ACCESS_TOKEN = "75c8651095404000b35d3135e78d05fe" MERCHANT_ID = 53177293 API_KEY = "a4ac091e88004e00ba43894f854a789d" HEADERS_5SIM = {"Authorization": f"Bearer {API_KEY}"}

def verify_utr_with_bharatpay(utr): url = "https://api.bharatpe.in/v1/payment/verify" headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"} payload = {"utr": utr, "merchant_id": MERCHANT_ID} try: response = requests.post(url, headers=headers, data=json.dumps(payload)) return response.json().get("status") == "PAID" except: return False

def button_handler(update: Update, context: CallbackContext): query = update.callback_query chat_id = query.message.chat_id query.answer()

if query.data.startswith("otp_service_"):
    srv_name = query.data.replace("otp_service_", "")
    country = context.user_data.get("otp_country")
    srv_info = SERVICE_PRICING.get(srv_name)
    if not srv_info:
        query.edit_message_text("Service config missing.")
        return

    price = srv_info['price']
    if USER_DATA[chat_id]["balance"] < price:
        query.edit_message_text(f"❌ Not enough balance. ₹{price} needed.")
        return

    USER_DATA[chat_id]["balance"] -= price
    save_data()
    USER_DATA[chat_id]["total_numbers"] += 1

    url = f"https://5sim.net/v1/user/buy/activation/any/{country}/{srv_info['id']}"
    r = requests.get(url, headers=HEADERS_5SIM)
    if r.status_code != 200:
        query.edit_message_text("❌ 5sim error. Try later.")
        return

    data = r.json()
    number, id_ = data["phone"], data["id"]
    query.edit_message_text(f"✅ Number: {number}\nWaiting for OTP...")

    def poll_otp():
        for _ in range(1200):
            res = requests.get(f"https://5sim.net/v1/user/check/{id_}", headers=HEADERS_5SIM)
            sms = res.json().get("sms")
            if sms:
                otp = sms[0]["code"]
                context.bot.send_message(chat_id, f"✅ OTP: {otp}")
                requests.get(f"https://5sim.net/v1/user/finish/{id_}", headers=HEADERS_5SIM)
                USER_DATA[chat_id]["used_numbers"] += 1
                save_data()
                return
            time.sleep(1)

        context.bot.send_message(chat_id, "⏰ OTP expired.")
        requests.get(f"https://5sim.net/v1/user/ban/{id_}", headers=HEADERS_5SIM)

    threading.Thread(target=poll_otp).start()

elif query.data == "admin_panel" and chat_id == ADMIN_ID:
    btns = [
        [InlineKeyboardButton("➕ Add Country", callback_data="admin_add_country")],
        [InlineKeyboardButton("➕ Add Service", callback_data="admin_add_service")],
        [InlineKeyboardButton("💰 View Prices", callback_data="admin_prices")],
    ]
    query.edit_message_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(btns))

elif query.data == "admin_add_country":
    context.user_data["admin_action"] = "add_country"
    query.edit_message_text("Send country in format:\n`India,india`", parse_mode='Markdown')

elif query.data == "admin_add_service":
    context.user_data["admin_action"] = "add_service"
    query.edit_message_text("Send service in format:\n`Telegram,telegram,20`", parse_mode='Markdown')

elif query.data == "admin_prices":
    if not SERVICE_PRICING:
        query.edit_message_text("No services added yet.")
        return
    lines = [f"{srv}: ₹{info['price']} | ID: {info['id']}" for srv, info in SERVICE_PRICING.items()]
    query.edit_message_text("Prices:\n" + "\n".join(lines))

def admin_text(update: Update, context: CallbackContext): if update.message.chat_id != ADMIN_ID: return action = context.user_data.get("admin_action") text = update.message.text.strip()

if action == "add_country":
    try:
        name, code = [i.strip() for i in text.split(",")]
        COUNTRIES[name] = code
        update.message.reply_text(f"✅ Country Added: {name} → {code}")
        save_data()
    except:
        update.message.reply_text("❌ Format: India,india")

elif action == "add_service":
    try:
        name, sid, price = [i.strip() for i in text.split(",")]
        SERVICE_PRICING[name] = {"id": sid, "price": int(price)}
        update.message.reply_text(f"✅ Service Added: {name} → {sid} ₹{price}")
        save_data()
    except:
        update.message.reply_text("❌ Format: Telegram,telegram,20")

def utr_handler(update: Update, context: CallbackContext): chat_id = update.message.chat_id if context.user_data.get("awaiting_utr"): utr = update.message.text.strip() if verify_utr_with_bharatpay(utr): USER_DATA[chat_id]["balance"] += 20 USER_DATA[chat_id]["total_recharged"] += 20 ref = USER_DATA[chat_id].get("referred_by") if ref and ref in USER_DATA: USER_DATA[ref]["referral_wallet"] += 0.6 update.message.reply_text("✅ ₹20 Recharge Successful!") save_data() else: update.message.reply_text("❌ UTR not verified.") context.user_data.pop("awaiting_utr", None)

def main(): load_data() updater = Updater("8120936026:AAE-LYykj7ZEGSxEaAnKq9E_wP38PVo2GJM", use_context=True) dp = updater.dispatcher dp.add_handler(CommandHandler("start", start, pass_args=True)) dp.add_handler(CallbackQueryHandler(button_handler)) dp.add_handler(MessageHandler(Filters.text & ~Filters.command, utr_handler)) dp.add_handler(MessageHandler(Filters.text & ~Filters.command, admin_text)) updater.start_polling() updater.idle()

if name == 'main': main()

