import json, requests, threading, time, os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

DATA_FILE = "bot_data.json"
USER_DATA, SERVICE_PRICING, COUNTRIES = {}, {}, {}

ADMIN_ID = 7459732827
UPI_ID = "BHARATPE.8X0M0S6J8F70781@fbpe"
QR_CODE_LINK = "https://i.ibb.co/BHS157vz/BHARATPE-QR.png"
ACCESS_TOKEN = "75c8651095404000b35d3135e78d05fe"
MERCHANT_ID = 53177293
API_KEY = "a4ac091e88004e00ba43894f854a789d"
HEADERS_5SIM = {"Authorization": f"Bearer {API_KEY}"}
BOT_TOKEN = "8120936026:AAE-LYykj7ZEGSxEaAnKq9E_wP38PVo2GJM"
SUPPORT_URL = "https://t.me/akotpshop"

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"USER_DATA": USER_DATA, "SERVICE_PRICING": SERVICE_PRICING, "COUNTRIES": COUNTRIES}, f)

def load_data():
    global USER_DATA, SERVICE_PRICING, COUNTRIES
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            USER_DATA = data.get("USER_DATA", {})
            SERVICE_PRICING = data.get("SERVICE_PRICING", {})
            COUNTRIES = data.get("COUNTRIES", {})

def verify_utr_with_bharatpay(utr):
    try:
        r = requests.post("https://api.bharatpe.in/v1/payment/verify", headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }, data=json.dumps({"utr": utr, "merchant_id": MERCHANT_ID}))
        return r.json().get("status") == "PAID"
    except:
        return False

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    name = update.effective_user.first_name
    args = context.args

    if chat_id not in USER_DATA:
        USER_DATA[chat_id] = {
            "name": name, "balance": 0.0, "total_recharged": 0.0,
            "total_numbers": 0, "used_numbers": 0, "refers": 0,
            "referral_wallet": 0.0, "referred_by": None, "promo_used": None
        }
        if args:
            try:
                ref = int(args[0])
                if ref != chat_id and ref in USER_DATA:
                    USER_DATA[chat_id]["referred_by"] = ref
                    USER_DATA[ref]["refers"] += 1
            except: pass

    d = USER_DATA[chat_id]
    buttons = [
        [InlineKeyboardButton("🛒 Get OTP", callback_data="get_otp")],
        [InlineKeyboardButton("💳 Recharge", callback_data="recharge")],
        [InlineKeyboardButton("👥 Profile", callback_data="profile")],
        [InlineKeyboardButton("🎁 Promo Code", callback_data="promo_code")],
        [InlineKeyboardButton("🛎 Support", url=SUPPORT_URL)]
    ]
    if chat_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel")])
    msg = f"""👋 Hello {d['name']}!
💰 Balance: ₹{d['balance']:.2f}
📦 Total Numbers: {d['total_numbers']}
✅ Used: {d['used_numbers']}"""
    update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    query.answer()

    if query.data == "recharge":
        context.user_data["awaiting_utr"] = True
        context.bot.send_photo(chat_id, QR_CODE_LINK,
            caption=f"Pay ₹20 to:\n`{UPI_ID}`\nSend your UTR here.", parse_mode="Markdown")

    elif query.data == "profile":
        d = USER_DATA[chat_id]
        msg = f"""👤 {d['name']} | ID: {chat_id}
Balance: ₹{d['balance']}
Used: {d['used_numbers']}
Referral Wallet: ₹{d['referral_wallet']}
Refers: {d['refers']}
Total Recharged: ₹{d['total_recharged']}"""
        query.edit_message_text(msg)

    elif query.data == "promo_code":
        context.user_data["awaiting_promo"] = True
        query.edit_message_text("Apna promo code bheje:")

    elif query.data == "get_otp":
        if not COUNTRIES:
            return query.edit_message_text("❌ No countries configured.")
        buttons = [[InlineKeyboardButton(name, callback_data=f"otp_country_{key}")] for name, key in COUNTRIES.items()]
        query.edit_message_text("Select Country:", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("otp_country_"):
        context.user_data["otp_country"] = query.data.replace("otp_country_", "")
        if not SERVICE_PRICING:
            return query.edit_message_text("❌ No services configured.")
        buttons = [[InlineKeyboardButton(f"{srv} (₹{info['price']})", callback_data=f"otp_service_{srv}")] for srv, info in SERVICE_PRICING.items()]
        query.edit_message_text("Select Service:", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("otp_service_"):
        srv = query.data.replace("otp_service_", "")
        country = context.user_data.get("otp_country")
        srv_info = SERVICE_PRICING.get(srv)
        if not srv_info: return query.edit_message_text("❌ Service not found.")
        price = srv_info["price"]
        if USER_DATA[chat_id]["balance"] < price:
            return query.edit_message_text(f"❌ ₹{price} needed.")
        USER_DATA[chat_id]["balance"] -= price
        USER_DATA[chat_id]["total_numbers"] += 1
        save_data()

        r = requests.get(f"https://5sim.net/v1/user/buy/activation/any/{country}/{srv_info['id']}", headers=HEADERS_5SIM)
        if r.status_code != 200:
            return query.edit_message_text("❌ 5sim error.")
        data = r.json()
        number, id_ = data["phone"], data["id"]
        query.edit_message_text(f"✅ Number: {number}\nWaiting for OTP...")

        def poll():
            for _ in range(1200):
                sms = requests.get(f"https://5sim.net/v1/user/check/{id_}", headers=HEADERS_5SIM).json().get("sms")
                if sms:
                    otp = sms[0]["code"]
                    context.bot.send_message(chat_id, f"✅ OTP: {otp}")
                    requests.get(f"https://5sim.net/v1/user/finish/{id_}", headers=HEADERS_5SIM)
                    USER_DATA[chat_id]["used_numbers"] += 1
                    save_data()
                    return
                time.sleep(1)
            requests.get(f"https://5sim.net/v1/user/cancel/{id_}", headers=HEADERS_5SIM)
            USER_DATA[chat_id]["balance"] += price
            save_data()
            context.bot.send_message(chat_id, "❌ OTP not received. ₹ refunded.")

        threading.Thread(target=poll).start()

    elif query.data == "admin_panel":
        query.edit_message_text("Admin Panel:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Country", callback_data="admin_add_country")],
            [InlineKeyboardButton("➕ Add Service", callback_data="admin_add_service")],
            [InlineKeyboardButton("💰 View Services", callback_data="admin_prices")]
        ]))

    elif query.data == "admin_add_country":
        context.user_data["admin_action"] = "add_country"
        query.edit_message_text("Send country in format:\n`India,india`", parse_mode="Markdown")

    elif query.data == "admin_add_service":
        context.user_data["admin_action"] = "add_service"
        query.edit_message_text("Send service in format:\n`Telegram,telegram,20`", parse_mode="Markdown")

    elif query.data == "admin_prices":
        if not SERVICE_PRICING:
            return query.edit_message_text("No services yet.")
        lines = [f"{s}: ₹{d['price']} | ID: {d['id']}" for s, d in SERVICE_PRICING.items()]
        query.edit_message_text("Services:\n" + "\n".join(lines))

def promo_code_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if context.user_data.get("awaiting_promo"):
        code = update.message.text.strip().upper()
        if USER_DATA[chat_id].get("promo_used") == code:
            update.message.reply_text("❌ Ye promo pehle use ho chuka.")
        elif code == "WELCOME100":
            USER_DATA[chat_id]["balance"] += 10
            USER_DATA[chat_id]["promo_used"] = code
            update.message.reply_text("✅ ₹10 added from promo code.")
            save_data()
        else:
            update.message.reply_text("❌ Galat promo code.")
        context.user_data.pop("awaiting_promo", None)

def admin_text(update: Update, context: CallbackContext):
    if update.message.chat_id != ADMIN_ID: return
    action = context.user_data.get("admin_action")
    text = update.message.text.strip()

    if action == "add_country":
        try:
            name, code = text.split(",")
            COUNTRIES[name.strip()] = code.strip()
            update.message.reply_text(f"✅ Country Added: {name} → {code}")
            save_data()
        except:
            update.message.reply_text("❌ Format: India,india")

    elif action == "add_service":
        try:
            name, sid, price = [x.strip() for x in text.split(",")]
            SERVICE_PRICING[name] = {"id": sid, "price": int(price)}
            update.message.reply_text(f"✅ Service Added: {name} ₹{price}")
            save_data()
        except:
            update.message.reply_text("❌ Format: Telegram,telegram,20")

def utr_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if context.user_data.get("awaiting_utr"):
        utr = update.message.text.strip()
        if verify_utr_with_bharatpay(utr):
            USER_DATA[chat_id]["balance"] += 20
            USER_DATA[chat_id]["total_recharged"] += 20
            ref = USER_DATA[chat_id].get("referred_by")
            if ref and ref in USER_DATA:
                USER_DATA[ref]["referral_wallet"] += 0.6
            update.message.reply_text("✅ ₹20 Recharge Successful!")
            save_data()
        else:
            update.message.reply_text("❌ UTR not verified.")
        context.user_data.pop("awaiting_utr", None)

def main():
    load_data()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start, pass_args=True))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, promo_code_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, utr_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, admin_text))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()  
