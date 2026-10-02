import sqlite3
import telebot
from telebot import types

# التوكن الخاص ببوتك
TOKEN = ""
bot = telebot.TeleBot(TOKEN)

# 1. إعداد قاعدة البيانات
def init_db():
    conn = sqlite3.connect("swap_bot.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            current_group TEXT,
            target_group TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# تخزين مؤقت لحالات المستخدمين
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
    user_id = message.from_user.id
    conn = sqlite3.connect("swap_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM requests WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ تم إلغاء طلبك وحذفه من قائمة الانتظار بنجاح.")

# معالجة الضغط على الأزرار
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id
    
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

        conn = sqlite3.connect("swap_bot.db")
        cursor = conn.cursor()
        
        # البحث عن توافق
        cursor.execute("SELECT user_id, username FROM requests WHERE current_group = ? AND target_group = ?", 
                       (targ_group, curr_group))
        match = cursor.fetchone()

        if match:
            matched_user_id, matched_username = match
            
            cursor.execute("DELETE FROM requests WHERE user_id = ?", (matched_user_id,))
            conn.commit()
            
            # إرسال الرسائل باستخدام تنسيق HTML لتفادي مشكلة الخط السفلي _
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
            cursor.execute("INSERT OR REPLACE INTO requests (user_id, username, current_group, target_group) VALUES (?, ?, ?, ?)",
                           (user_id, username, curr_group, targ_group))
            conn.commit()
            
            bot.send_message(user_id, "✅ <b>تم تسجيل طلبك بنجاح!</b>\n\nإذا غيرت رأيك في أي وقت، أرسل /cancel لإلغاء طلبك.\nسيصلك إشعار فوري هنا على البوت بمجرد أن يسجل طالب من الفوج المطلوب يريد فوجك.", parse_mode="HTML")

        conn.close()

print("البوت يعمل الآن بنجاح...")
bot.infinity_polling()
