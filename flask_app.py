from flask import Flask, request
import requests
import json
import os
import threading
import traceback
import time

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN", "8391181965:").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1986087627"))
ADMIN_GROUP_ID = int(os.environ.get("ADMIN_GROUP_ID", "-1003740654454"))
FLOOD_CHAT_ID = int(os.environ.get("FLOOD_CHAT_ID", "-1003188439372"))
FLOOD_CHAT_2_ID = int(os.environ.get("FLOOD_CHAT_2_ID", "-3795017989"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://bohdanasalimova.pythonanywhere.com/webhook").strip()
USERS_FILE = os.environ.get("USERS_FILE", "/home/bohdanasalimova/mysite/users.json").strip()
BOOKINGS_FILE = os.environ.get("BOOKINGS_FILE", "/home/bohdanasalimova/mysite/bookings.json").strip()

USERS_LOCK = threading.Lock()
BOOKINGS_LOCK = threading.Lock()
ACTIVE_TYPING = {"join", "rest", "booking", "owner_feedback", "complaint"}
MENU_TEXTS = {
    "/start",
    "Гᴧᴀʙнᴏᴇ ʍᴇню:",
    "☞ Зᴀяʙᴋᴀ нᴀ ʙхᴏд",
    "☞ Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ",
    "️☞ Ꭺнᴏниʍнᴀя жᴀᴧᴏбᴀ",
    "☞ Ꮻᴛʍᴇнᴀ",
}
AVAILABLE_CHATS = [
    {"title": "SCH_kik", "chat_id": FLOOD_CHAT_ID, "info_link": "https://t.me/SCH_kik", "max_members": 55, "check_members": True},
    {"title": "SCH_kik2", "chat_id": FLOOD_CHAT_2_ID, "info_link": "https://t.me/SCH_kik2", "max_members": 60, "check_members": False},
]


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else default
    except Exception as e:
        print(f"[load_json_file] {path}: {e}")
        return default


def save_json_file(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[save_json_file] {path}: {e}")


def load_users():
    with USERS_LOCK:
        return load_json_file(USERS_FILE, {})


def save_users(users):
    with USERS_LOCK:
        save_json_file(USERS_FILE, users)


def load_bookings():
    with BOOKINGS_LOCK:
        return load_json_file(BOOKINGS_FILE, {})


def save_bookings(bookings):
    with BOOKINGS_LOCK:
        save_json_file(BOOKINGS_FILE, bookings)


def tg_request(method, payload):
    if not TOKEN:
        return {"ok": False, "description": "TELEGRAM_TOKEN is not set"}
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=7)
        return r.json() if r.content else {"ok": False, "description": "empty response"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    res = tg_request("sendMessage", payload)
    if not res.get("ok"):
        print(f"[send_message] {chat_id}: {res.get('description')}")
    return res


def send_bg(chat_id, text, reply_markup=None, parse_mode=None):
    threading.Thread(target=send_message, args=(chat_id, text, reply_markup, parse_mode), daemon=True).start()


def answer_callback(callback_query_id, text=""):
    return tg_request("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


def answer_callback_bg(callback_query_id, text=""):
    threading.Thread(target=answer_callback, args=(callback_query_id, text), daemon=True).start()


def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    res = tg_request("editMessageText", payload)
    if not res.get("ok"):
        print(f"[edit_message] {res}")


def edit_message_bg(chat_id, message_id, text, reply_markup=None):
    threading.Thread(target=edit_message, args=(chat_id, message_id, text, reply_markup), daemon=True).start()


def main_keyboard():
    return {"keyboard": [[{"text": "☞ Зᴀяʙᴋᴀ нᴀ ʙхᴏд"}, {"text": "☞ Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ"}], [{"text": "️☞ Ꭺнᴏниʍнᴀя ��ᴀᴧᴏбᴀ"}, {"text": "☞ Ꮻᴛʍᴇнᴀ"}]], "resize_keyboard": True, "one_time_keyboard": False}


def get_reject_keyboard(kind, user_id):
    return {"inline_keyboard": [[{"text": "✉️ Дать обратную связь", "callback_data": f"reject_{kind}_fb_{user_id}"}, {"text": "🚫 Без обратной связи", "callback_data": f"reject_{kind}_nofb_{user_id}"}]]}


def get_chat_member_count(chat_id):
    res = tg_request("getChatMemberCount", {"chat_id": chat_id})
    return res.get("result", -1) if res.get("ok") else -1


def create_invite_link(chat_id, user_id):
    res = tg_request("createChatInviteLink", {"chat_id": chat_id, "member_limit": 1, "name": f"Invite for {user_id}"})
    if res.get("ok"):
        return res["result"]["invite_link"]
    res = tg_request("exportChatInviteLink", {"chat_id": chat_id})
    return res.get("result") if res.get("ok") else None


def get_user_join_chat(users, user_id):
    info = users.get(str(user_id), {})
    try:
        idx = int(info.get("chosen_chat_idx", -1))
        return AVAILABLE_CHATS[idx] if 0 <= idx < len(AVAILABLE_CHATS) else None
    except Exception:
        return None


def do_send_invite(user_id, first_name, username, join_chat, callback_id=None):
    invite_link = create_invite_link(join_chat["chat_id"], user_id)
    if invite_link:
        send_message(user_id, f"✔︎ 𐌏ᴛ᧘ᥙчн᧐.\n\n✏︎ Ᏼ᧐ᴛ ʙᥲɯᥲ ᥰᥱρᥴ᧐нᥲ᧘ьнᥲя ᥴᥴы᧘κᥲ нᥲ ɸ᧘уд:\n{invite_link}\n\n⚠️ Ꮯᥴы᧘κᥲ ᧐дн᧐ρᥲᤋ᧐ʙᥲя — ᥙᥴᥰ᧐᧘ьᤋуᥔᴛᥱ ᥱё ᥴρᥲᤋу.\n\nДᴏбᴩᴏ ᴨᴏжᴀᴧᴏʙᴀᴛь.")
        send_bg(ADMIN_GROUP_ID, f"— {first_name} (@{username}, ID: {user_id}) ᴨᴏᴧучиᴧ дᴏᴄтуᴨ ᴋ ɸᴧуду ({join_chat['title']})")
        send_bg(ADMIN_ID, f"— {first_name} (@{username}, ID: {user_id}) ᴨᴏᴧучиᴧ дᴏᴄтуᴨ ᴋ ɸᴧуду ({join_chat['title']})")
    else:
        send_message(user_id, "✘ Оɯибᴋᴀ ᴄᴏɜдᴀния ᴄᴄыᴧκи. Обᴩᴀᴛиᴛᴇᴄь ᴋ ᴀдʍиниᴄᴛᴩᴀции.")
    if callback_id:
        answer_callback(callback_id, "✔︎" if invite_link else "✘")


def reminder_loop():
    while True:
        try:
            users = load_users()
            now = time.time()
            overdue = []
            for uid_str, info in users.items():
                if info.get("type") not in ("join", "rest", "booking"):
                    continue
                created_at = info.get("created_at")
                try:
                    created_at = float(created_at)
                except Exception:
                    continue
                if now - created_at >= 3 * 24 * 60 * 60:
                    overdue.append(f"• {info.get('type', '').upper()}: {info.get('first_name', '')} (@{info.get('username', 'Нет username')}) — {info.get('step', '')} — ID {uid_str}")
            if overdue:
                msg = "⚠️ Зависшие заявки старше 3 дней:\n\n" + "\n".join(overdue)
                send_bg(ADMIN_GROUP_ID, msg)
                send_bg(ADMIN_ID, msg)
        except Exception as e:
            print(f"[reminder_loop] {e}")
        time.sleep(6 * 60 * 60)


threading.Thread(target=reminder_loop, daemon=True).start()


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data:
            return "ok", 200

        if "callback_query" in data:
            cbq = data["callback_query"]
            cb = cbq.get("data", "")
            callback_id = cbq.get("id")
            message = cbq.get("message", {})
            cb_user = cbq.get("from", {})
            admin_id = cb_user.get("id")
            admin_id_str = str(admin_id)
            users = load_users()
            bookings = load_bookings()

            if cb.startswith("join_chat_"):
                idx = int(cb.split("_")[2])
                chat_info = AVAILABLE_CHATS[idx]
                if chat_info.get("check_members", True):
                    count = get_chat_member_count(chat_info["chat_id"])
                    if count != -1 and count >= chat_info["max_members"]:
                        free = []
                        for i, c in enumerate(AVAILABLE_CHATS):
                            if i == idx:
                                continue
                            if not c.get("check_members", True):
                                free.append(i)
                                continue
                            other = get_chat_member_count(c["chat_id"])
                            if other != -1 and other < c["max_members"]:
                                free.append(i)
                        kb = [[{"text": f"В «{AVAILABLE_CHATS[i]['title']}» (свободно)", "callback_data": f"join_chat_{i}"}] for i in free]
                        kb.append([{"text": "Забронировать роль", "callback_data": f"book_role_{idx}"}])
                        send_bg(admin_id, f"Чат «{chat_info['title']}» заполнен!\nВыбери другой или забронируй место.", reply_markup={"inline_keyboard": kb})
                        answer_callback_bg(callback_id, "☑️")
                        return "ok", 200
                users[admin_id_str] = {"step": "join_birthday", "type": "join", "chosen_chat": chat_info["title"], "chosen_chat_idx": idx, "created_at": time.time()}
                save_users(users)
                send_bg(admin_id, f"Выбран чат «{chat_info['title']}».\nОзнакомься с инфо: {chat_info['info_link']}\n\nУкажи дату рождения (например: 15 марта):")
                answer_callback_bg(callback_id, "✔️")
                return "ok", 200

            if cb.startswith("book_role_"):
                idx = int(cb.split("_")[2])
                chat_info = AVAILABLE_CHATS[idx]
                users[admin_id_str] = {"step": "booking_birthday", "type": "booking", "chosen_chat": chat_info["title"], "chosen_chat_idx": idx, "created_at": time.time()}
                save_users(users)
                send_bg(admin_id, f"Бронь в чат «{chat_info['title']}».\n\nУкажи дату рождения (например: 15 марта):")
                answer_callback_bg(callback_id, "✔️")
                return "ok", 200

            if cb.startswith("show_booking_"):
                uid_str = cb.split("_")[2]
                booking = bookings.get(uid_str)
                if not booking:
                    send_bg(admin_id, "Бронь не найдена (возможно уже удалена).")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                text_msg = f"📋 Анкета брони\n\n➥ Имя: {booking.get('first_name', '')}\n➥ Username: @{booking.get('username', 'Нет username')}\n➥ Дата рождения: {booking.get('birthday', '')}\n➥ Роль: {booking.get('role', '')}\n➥ Кодовое слово: {booking.get('codeword', '')}\n➥ Чат: {booking.get('chosen_chat', '')} ({booking.get('info_link', '')})"
                kb = {"inline_keyboard": [[{"text": "𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐", "callback_data": f"approve_booking_{uid_str}"}, {"text": "𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ", "callback_data": f"reject_booking_{uid_str}"}]]}
                send_bg(admin_id, text_msg, reply_markup=kb)
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("approve_join_"):
                user_id = int(cb.split("_")[2])
                join_chat = get_user_join_chat(users, user_id)
                if not join_chat:
                    send_bg(admin_id, "Не удалось определить чат заявки.")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                send_bg(user_id, "— Ᏼᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ʙхᴏд ᴏдᴏбᴩᴇнᴀ.\n\n", reply_markup={"inline_keyboard": [[{"text": "— ✔︎.", "callback_data": f"read_info_{user_id}"}]]})
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ〚ять ⲙяучₑ᧘᧐")
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("reject_join_") and "_fb_" not in cb and "_nofb_" not in cb:
                user_id = int(cb.split("_")[2])
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\nОтклонено. Дать обратную связь?", reply_markup=get_reject_keyboard("join", user_id))
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("read_info_") and not cb.startswith("read_info_booking_"):
                user_id = int(cb.split("_")[2])
                join_chat = get_user_join_chat(users, user_id)
                if join_chat:
                    fn = cb_user.get("first_name", "")
                    un = cb_user.get("username", "Нет username")
                    threading.Thread(target=do_send_invite, args=(user_id, fn, un, join_chat, callback_id), daemon=True).start()
                else:
                    send_bg(user_id, "✘ Оɯибᴋᴀ ᴄᴏɜдᴀния ᴄᴄыᴧκи. Обᴩᴀᴛиᴛᴇᴄь ᴋ ᴀдʍиниᴄᴛᴩᴀции.")
                    answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("read_info_booking_"):
                user_id = int(cb.split("_")[3])
                booking = bookings.get(str(user_id))
                if booking:
                    join_chat = AVAILABLE_CHATS[int(booking["chosen_chat_idx"])]
                    fn = cb_user.get("first_name", "")
                    un = cb_user.get("username", "Нет username")
                    def _approve_booking():
                        do_send_invite(user_id, fn, un, join_chat, callback_id)
                        bk = load_bookings()
                        bk.pop(str(user_id), None)
                        save_bookings(bk)
                    threading.Thread(target=_approve_booking, daemon=True).start()
                else:
                    send_bg(user_id, "✘ Оɯибᴋᴀ: бᴩᴏнь нᴇ нᴀйдᴇнᴀ.")
                    answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("approve_booking_"):
                uid_str = cb.split("_")[2]
                booking = bookings.get(uid_str)
                if not booking:
                    send_bg(admin_id, "Бронь не найдена.")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                user_id = int(booking["user_id"])
                send_bg(user_id, "— Ᏼᴀɯᴀ бᴩᴏнь ᴏдᴏбᴩᴇнᴀ.\n\n", reply_markup={"inline_keyboard": [[{"text": "— ✔︎.", "callback_data": f"read_info_booking_{user_id}"}]]})
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ〚ять ⲙяучₑ᧘᧐")
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("reject_booking_") and "_fb_" not in cb and "_nofb_" not in cb:
                uid_str = cb.split("_")[2]
                booking = bookings.get(uid_str)
                user_id = int(booking["user_id"]) if booking else int(uid_str)
                bookings.pop(uid_str, None)
                save_bookings(bookings)
                send_bg(user_id, "— Ᏼᴀɯᴀ бᴩᴏнь ᴏᴛᴋᴧᴏнᴇнᴀ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\nОтклонено. Дать обратную связь?", reply_markup=get_reject_keyboard("booking", user_id))
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("approve_rest_"):
                user_id = int(cb.split("_")[2])
                send_bg(user_id, "— Вᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ ᴏдᴏбᴩᴇнᴀ. Оᴛдыхᴀйтᴇ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐")
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("reject_rest_") and "_fb_" not in cb and "_nofb_" not in cb:
                user_id = int(cb.split("_")[2])
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\nОтклонено. Дать обратную связь?", reply_markup=get_reject_keyboard("rest", user_id))
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("reject_join_nofb_"):
                user_id = int(cb.split("_")[3])
                send_bg(user_id, "— Ᏼᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ʙ᥊ᴏд ᧐ᴛκ᧘ᴏнₑнᥲ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ (без обратной связи)")
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("reject_rest_nofb_"):
                user_id = int(cb.split("_")[3])
                send_bg(user_id, "— Вᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ ᴏᴛᴋᴧᴏнᴇнᥲ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ (без обратной связи)")
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("reject_booking_nofb_"):
                uid_str = cb.split("_")[3]
                user_id = int(uid_str)
                bk = load_bookings()
                bk.pop(uid_str, None)
                save_bookings(bk)
                send_bg(user_id, "— Ᏼᴀɯᴀ бᴩᴏнь ᴏᴛᴋᴧᴏнᴇнᴀ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ (без обратной связи)")
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            for kind in ("join", "rest", "booking"):
                if cb.startswith(f"reject_{kind}_fb_"):
                    target_uid = int(cb.split("_")[3])
                    users[admin_id_str] = {"type": "owner_feedback", "step": "wait_text", "target_user_id": target_uid, "reject_kind": kind, "created_at": time.time()}
                    save_users(users)
                    send_bg(admin_id, "Оставьте сообщение (будет отправлено пользователю как «Сообщение от владельца: ...»).")
                    answer_callback_bg(callback_id, "✉️ Напишите текст в этот чат")
                    return "ok", 200

            return "ok", 200

        message = data.get("message")
        if not message:
            return "ok", 200
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if not chat_id:
            return "ok", 200
        chat_type = chat.get("type")
        text = (message.get("text") or "").strip()
        username = message.get("from", {}).get("username", "Нет username")
        first_name = message.get("from", {}).get("first_name", "")
        users = load_users()
        bookings = load_bookings()
        chat_id_str = str(chat_id)
        is_admin_chat = chat_id == ADMIN_GROUP_ID or chat_id == ADMIN_ID
        is_private = chat_type == "private"
        is_menu_click = text in MENU_TEXTS

        if text.lower().strip() == "спящие" and is_admin_chat:
            if not bookings:
                send_message(chat_id, "— Список броней пуст.")
                return "ok", 200
            kb = [[{"text": f"{b.get('first_name', '')} (@{b.get('username', 'Нет username')}) → {b.get('chosen_chat', '')}", "callback_data": f"show_booking_{uid}"}] for uid, b in bookings.items()]
            send_message(chat_id, "🕓 Список броней:", reply_markup={"inline_keyboard": kb})
            return "ok", 200

        if text.lower().strip() == "мяукают" and is_admin_chat:
            items = [f"• {info.get('first_name', '')} (@{info.get('username', 'Нет username')}) — {info.get('step', '')} — {info.get('chosen_chat', 'не выбран')}" for _, info in users.items() if info.get("type") == "join"]
            send_message(chat_id, "— Активных заявок на вход нет." if not items else "🐾 Заявки на вход:\n\n" + "\n".join(items[:50]))
            return "ok", 200

        if text.lower().strip() == "кто отдыхает" and is_admin_chat:
            items = [f"• {info.get('first_name', '')} (@{info.get('username', 'Нет username')}) — {info.get('step', '')}" for _, info in users.items() if info.get("type") == "rest"]
            send_message(chat_id, "— Активных заявок на рест нет." if not items else "🛌 Кто отдыхает:\n\n" + "\n".join(items[:50]))
            return "ok", 200

        if text == "☞ Зᴀяʙᴋᴀ нᴀ ʙхᴏд":
            users[chat_id_str] = {"step": "join_choose_chat", "type": "join", "created_at": time.time()}
            save_users(users)
            kb = [[{"text": f"В чат «{c['title']}»", "callback_data": f"join_chat_{i}"}] for i, c in enumerate(AVAILABLE_CHATS)]
            send_message(chat_id, "Выберите чат:", reply_markup={"inline_keyboard": kb})
            return "ok", 200

        if chat_id_str in users and users[chat_id_str].get("type") == "join":
            step = users[chat_id_str].get("step")
            if step == "join_choose_chat":
                kb = [[{"text": f"В чат «{c['title']}»", "callback_data": f"join_chat_{i}"}] for i, c in enumerate(AVAILABLE_CHATS)]
                send_message(chat_id, "Пожалуйста, выберите чат кнопкой ниже.", reply_markup={"inline_keyboard": kb})
                return "ok", 200
            if step == "join_birthday":
                users[chat_id_str]["birthday"] = text
                users[chat_id_str]["step"] = "join_role"
                save_users(users)
                send_message(chat_id, "— Кᴀᴋую ᴩᴏᴧь ты хᴏчᴇɯь ɜᴀняᴛь?")
                return "ok", 200
            if step == "join_role":
                users[chat_id_str]["role"] = text
                users[chat_id_str]["step"] = "join_codeword"
                save_users(users)
                send_message(chat_id, "— Уκᴀжи κᴏдᴏʙᴏᴇ ᴄᴧᴏʙᴏ:")
                return "ok", 200
            if step == "join_codeword":
                birthday = users[chat_id_str].get("birthday", "")
                role = users[chat_id_str].get("role", "")
                chat_idx = users[chat_id_str].get("chosen_chat_idx", 0)
                chat_title = users[chat_id_str].get("chosen_chat", "")
                info_link = AVAILABLE_CHATS[int(chat_idx)]["info_link"]
                admin_msg = f"📩 Нᴏʙᴀя ɜᴀяʙᴋᴀ нᴀ ʙхᴏд\n\n➥ Иʍя: {first_name}\n➥ Usᴇrnᴀʍᴇ: @{username}\n➥ Дᴀᴛᴀ ᴩᴏждᴇния: {birthday}\n➥ Жᴇᴧᴀᴇʍᴀя ᴩᴏᴧь: {role}\n➥ Кᴏдᴏʙᴏᴇ ᴄᴧᴏʙᴏ: {text}\n➥ Чᴀᴛ: {chat_title} ({info_link})"
                kb = {"inline_keyboard": [[{"text": "𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐", "callback_data": f"approve_join_{chat_id}"}, {"text": "𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ", "callback_data": f"reject_join_{chat_id}"}]]}
                send_bg(ADMIN_GROUP_ID, admin_msg, reply_markup=kb)
                send_bg(ADMIN_ID, admin_msg, reply_markup=kb)
                send_message(chat_id, "✔︎ ɜᴀяʙᴋᴀ ᴏᴛᴨᴩᴀʙᴧᴇнᴀ. Ꮎжидᴀй ᴩᴇɯᴇния.", reply_markup=main_keyboard())
                users[chat_id_str]["step"] = "join_wait_admin"
                save_users(users)
                return "ok", 200

        if text == "☞ Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ":
            users[chat_id_str] = {"step": "rest_role", "type": "rest", "created_at": time.time()}
            save_users(users)
            send_message(chat_id, "— ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ.\n\n✦ Кᴀᴋᴀя у ᴛᴇбя ᴩᴏᴧь?")
            return "ok", 200

        if chat_id_str in users and users[chat_id_str].get("type") == "rest":
            step = users[chat_id_str].get("step")
            if step == "rest_role":
                users[chat_id_str]["role"] = text
                users[chat_id_str]["step"] = "rest_duration"
                save_users(users)
                send_message(chat_id, "— Нᴀ κᴀкᴏй cᴩᴏк нужᴇн ᴩᴇᴄᴛ? (дᴏ 2 нᴇдᴇᴧь, ᴏᴛ ᴋᴀᴋᴏᴦᴏ дᴏ ᴋᴀᴋᴏᴦᴏ чиᴄᴧᴀ.)")
                return "ok", 200
            if step == "rest_duration":
                users[chat_id_str]["duration"] = text
                users[chat_id_str]["step"] = "rest_reason"
                save_users(users)
                send_message(chat_id, "— Уκᴀжи ᴨᴩичину:")
                return "ok", 200
            if step == "rest_reason":
                role = users[chat_id_str].get("role", "")
                duration = users[chat_id_str].get("duration", "")
                admin_msg = f"📩 Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ\n\n➥ Иʍя: {first_name}\n➥ Usᴇrnᴀʍᴇ: @{username}\n➥ Рᴏᴧь: {role}\n➥ Сᴩᴏк: {duration}\n➥ Пᴩичинᴀ: {text}"
                kb = {"inline_keyboard": [[{"text": "𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐", "callback_data": f"approve_rest_{chat_id}"}, {"text": "𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ", "callback_data": f"reject_rest_{chat_id}"}]]}
                send_bg(ADMIN_GROUP_ID, admin_msg, reply_markup=kb)
                send_bg(ADMIN_ID, admin_msg, reply_markup=kb)
                send_message(chat_id, "✔︎ ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ ᴏᴛᴨᴀʙʙᴧᴇнᴀ. Ꮎжидᴀй ᴩᴇɯᴇния.", reply_markup=main_keyboard())
                del users[chat_id_str]
                save_users(users)
                return "ok", 200

        if text == "️☞ Ꭺнᴏниʍнᴀя жᴀᴧᴏбᴀ":
            users[chat_id_str] = {"step": "complaint_text", "type": "complaint", "created_at": time.time()}
            save_users(users)
            send_message(chat_id, "— Ꭺнᴏниʍнᴀя жᴀᴧᴏбᴀ.\n\n✎ ᴏᴨиɯи жᴀᴧᴏбу — ᴏнᴀ yйдёт ᴀдʍинᴀʍ ᴀнᴏниʍнᴏ.")
            return "ok", 200

        if chat_id_str in users and users[chat_id_str].get("type") == "complaint" and users[chat_id_str].get("step") == "complaint_text":
            admin_msg = f"⚠︎ жᴀᴧᴏбᴀ\n\n✎ Тᴇᴋᴄᴛ:\n{text}\n\nОᴛᴨᴩᴀʙᴧᴇнᴏ ᴀнᴏниʍнᴏ"
            send_bg(ADMIN_GROUP_ID, admin_msg)
            send_bg(ADMIN_ID, admin_msg)
            send_message(chat_id, "✔︎ Вᴀɯᴀ жᴀᴧᴏбᴀ ᴏᴛᴨᴀʙʙᴧᴇнᴀ ᴀнᴏниʍнᴏ.", reply_markup=main_keyboard())
            del users[chat_id_str]
            save_users(users)
            return "ok", 200

        if text == "☞ Ꮻᴛʍᴇнᴀ":
            users.pop(chat_id_str, None)
            save_users(users)
            send_message(chat_id, "✘ Ꭲᴇᴋуɯᴇᴇ дᴇйᴄᴛʙиᴇ ᴏтʍᴇнᴇнᴏ." if is_private else "— Ꮋᴇᴛ ᴀᴋᴛиʙныx дᴇйᴄᴛʙий.", reply_markup=main_keyboard())
            return "ok", 200

        if chat_type == "private" and chat_id != ADMIN_ID:
            send_message(chat_id, "— Иᴄᴨᴏᴧьɜуй ᴋнᴏᴨᴋи ʍᴇню нижᴇ.", reply_markup=main_keyboard())

        return "ok", 200

    except Exception as e:
        print(f"[webhook] Exception: {e}")
        traceback.print_exc()
        return "ok", 200


@app.route("/set_webhook")
def set_webhook():
    return tg_request("setWebhook", {"url": WEBHOOK_URL})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
