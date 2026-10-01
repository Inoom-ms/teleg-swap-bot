import sqlite3
import telebot
from telebot import types

# التوكن الخاص ببوتك
TOKEN = "8630024688:AAGMXmsLt1VWmfev7iE29Yi2SzXmAjLQ6ww"
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
    
    bot.send_message(message.chat.id, "مرحباً بك! 👋\nيرجى اختيار **فوجك الحالي**:", parse_mode="Markdown", reply_markup=markup)

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
        
        bot.edit_message_text(f"أنت حالياً في **الفوج {curr_group}**.\nاختر **الفوج الذي تريد الانتقال إليه**:", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("targ_"):
        targ_group = call.data.split("_")[1]
        curr_group = user_data.get(user_id, {}).get('current_group')
        username = call.from_user.username or user_data.get(user_id, {}).get('username')
        
        if not curr_group:
            bot.send_message(call.message.chat.id, "حدث خطأ بسيط، يرجى كتابة /start وإعادة الاختيار.")
            return

        bot.edit_message_text(f"جاري البحث عن تبادل من **الفوج {curr_group}** ⬅️ **الفوج {targ_group}**...", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")

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
            
            bot.send_message(user_id, f"🎉 **وجدنا لك تبادلاً مباشراً!**\n\nالطرف الثاني: @{matched_username}\nيدرس في **الفوج {targ_group}** ويريد الانتقال لـ **الفوج {curr_group}**.\nتواصل معه الآن وتوافقا على الإجراءات!", parse_mode="Markdown")
            
            try:
                bot.send_message(matched_user_id, f"🎉 **وجدنا لك تبادلاً مباشراً!**\n\nالطرف الثاني: @{username}\nيدرس في **الفوج {curr_group}** ويريد الانتقال لـ **الفوج {targ_group}**.\nتواصل معه الآن وتوافقا على الإجراءات!", parse_mode="Markdown")
            except Exception:
                pass
        else:
            cursor.execute("INSERT OR REPLACE INTO requests (user_id, username, current_group, target_group) VALUES (?, ?, ?, ?)",
                           (user_id, username, curr_group, targ_group))
            conn.commit()
            
            bot.send_message(user_id, "✅ **تم تسجيل طلبك بنجاح!**\n\nإذا غيرت رأيك في أي وقت، أرسل /cancel لإلغاء طلبك.\nسيصلك إشعار فوري هنا على البوت بمجرد أن يسجل طالب من الفوج المطلوب يريد فوجك.")

        conn.close()

print("البوت يعمل الآن بنجاح...")
bot.infinity_polling()