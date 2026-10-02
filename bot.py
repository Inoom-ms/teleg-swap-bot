import os
import firebase_admin
from firebase_admin import credentials, firestore
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# ==========================================
# 1. إعداد سيرفر Flask المصغر لإبقاء البوت نشطاً
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_flask():
    # موقع Render يحدد المنفذ تلقائياً عبر متغير البيئة PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    # تشغيل Flask في خيط منفصل (Thread) لعدم تعطيل البوت
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# بدء تشغيل سيرفر الويب
keep_alive()

# ==========================================
# 2. إعداد وتوصيل Firebase
# ==========================================
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ==========================================
# 3. التوكن وإعداد البوت
# ==========================================
TOKEN = "8630024688:AAGMXmsLt1VWmfev7iE29Yi2SzXmAjLQ6ww"
bot = telebot.TeleBot(TOKEN)

user_data = {}

# أمر البداية /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if not username:
        bot.reply_to(message, "⚠️ عفواً، يجب أن يكون لديك اسم مستخدم (Username) على تلغرام حتى يتواصل معك باقي الطلبة.\nقم بإنشائه من إعدادات حسابك ثم أعد كتابة /start.")
        return

    user_data[user_id] = {'username': username}
    
    markup = types.InlineKeyboardMarkup(row_width=4)
    buttons = [types.InlineKeyboardButton(f"فوج {i}", callback_data=f"curr_{i}") for i in range(1, 15)]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, "مرحباً بك! 👋\nيرجى اختيار <b>فوجك الحالي</b>:", parse_mode="HTML", reply_markup=markup)

# أمر إلغاء الطلب /cancel
@bot.message_handler(commands=['cancel'])
def cancel_request(message):
    user_id = str(message.from_user.id)
    db.collection("requests").document(user_id).delete()
    bot.send_message(message.chat.id, "✅ تم إلغاء طلبك وحذفه من قائمة الانتظار بنجاح.")

# معالجة الضغط على الأزرار
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id
    user_id_str = str(user_id)
    
    if call.data.startswith("curr_"):
        curr_group = call.data.split("_")[1]
        user_data[user_id] = user_data.get(user_id, {})
        user_data[user_id]['current_group'] = curr_group
        user_data[user_id]['username'] = call.from_user.username
        
        markup = types.InlineKeyboardMarkup(row_width=4)
        buttons = [types.InlineKeyboardButton(f"فوج {i}", callback_data=f"targ_{i}") for i in range(1, 15) if str(i) != curr_group]
        markup.add(*buttons)
        
        bot.edit_message_text(f"أنت حالياً في <b>الفوج {curr_group}</b>.\nاختر <b>الفوج الذي تريد الانتقال إليه</b>:", 
                              call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif call.data.startswith("targ_"):
        targ_group = call.data.split("_")[1]
        curr_group = user_data.get(user_id, {}).get('current_group')
        username = call.from_user.username or user_data.get(user_id, {}).get('username')
        
        if not curr_group:
            bot.send_message(call.message.chat.id, "حدث خطأ بسيط، يرجى كتابة /start وإعادة الاختيار.")
            return

        bot.edit_message_text(f"جاري البحث عن تبادل من <b>الفوج {curr_group}</b> ⬅️ <b>الفوج {targ_group}</b>...", 
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")

        requests_ref = db.collection("requests")
        query = requests_ref.where("current_group", "==", targ_group).where("target_group", "==", curr_group).limit(1)
        matches = query.get()

        if len(matches) > 0:
            matched_doc = matches[0]
            matched_data = matched_doc.to_dict()
            matched_user_id = int(matched_doc.id)
            matched_username = matched_data.get("username")
            
            requests_ref.document(matched_doc.id).delete()
            
            msg_to_user = (
                f"🎉 <b>وجدنا لك تبادلاً مباشراً!</b>\n\n"
                f"الطرف الثاني: @{matched_username}\n"
                f"يدرس في <b>الفوج {targ_group}</b> ويريد الانتقال لـ <b>الفوج {curr_group}</b>.\n"
                f"تواصل معه الآن وتوافقا على الإجراءات!"
            )
            
            msg_to_match = (
                f"🎉 <b>وجدنا لك تبادلاً مباشراً!</b>\n\n"
                f"الطرف الثاني: @{username}\n"
                f"يدرس في <b>الفوج {curr_group}</b> ويريد الانتقال لـ <b>الفوج {targ_group}</b>.\n"
                f"تواصل معه الآن وتوافقا على الإجراءات!"
            )
            
            bot.send_message(user_id, msg_to_user, parse_mode="HTML")
            
            try:
                bot.send_message(matched_user_id, msg_to_match, parse_mode="HTML")
            except Exception:
                pass
        else:
            requests_ref.document(user_id_str).set({
                "username": username,
                "current_group": curr_group,
                "target_group": targ_group
            })
            
            bot.send_message(user_id, "✅ <b>تم تسجيل طلبك بنجاح!</b>\n\nإذا غيرت رأيك في أي وقت، أرسل /cancel لإلغاء طلبك.\nسيصلك إشعار فوري هنا على البوت بمجرد أن يسجل طالب من الفوج المطلوب يريد فوجك.", parse_mode="HTML")

print("البوت وسيرفر الويب يعملان الآن بنجاح...")
bot.infinity_polling()
        
