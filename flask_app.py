from flask import Flask, request
import requests
import json
import os
import threading
import traceback

app = Flask(__name__)

# ================== НАСТРОЙКИ ==================
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

AVAILABLE_CHATS = [
    {
        "title": "SCH_kik",
        "chat_id": FLOOD_CHAT_ID,
        "info_link": "https://t.me/SCH_kik",
        "max_members": 55,
        "check_members": True,
    },
    {
        "title": "SCH_kik2",
        "chat_id": FLOOD_CHAT_2_ID,
        "info_link": "https://t.me/SCH_kik2",
        "max_members": 60,
        "check_members": False,
    },
]

# ================== STORAGE ==================
def load_users():
    with USERS_LOCK:
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception as e:
                print(f"[load_users] error: {e}")
        return {}


def save_users(users):
    with USERS_LOCK:
        try:
            os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[save_users] Error: {e}")


def load_bookings():
    with BOOKINGS_LOCK:
        if os.path.exists(BOOKINGS_FILE):
            try:
                with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception as e:
                print(f"[load_bookings] error: {e}")
        return {}


def save_bookings(bookings):
    with BOOKINGS_LOCK:
        try:
            os.makedirs(os.path.dirname(BOOKINGS_FILE), exist_ok=True)
            with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(bookings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[save_bookings] Error: {e}")

# ================== TELEGRAM HELPERS ==================
def tg_request(method, payload):
    if not TOKEN:
        return {"ok": False, "description": "TELEGRAM_TOKEN is not set"}
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/{method}",
            json=payload,
            timeout=7,
        )
        try:
            return response.json()
        except Exception:
            return {"ok": False, "description": response.text}
    except requests.exceptions.ReadTimeout:
        return {"ok": False, "description": "timeout"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = reply_markup
    if parse_mode:
        data["parse_mode"] = parse_mode
    result = tg_request("sendMessage", data)
    if not result.get("ok"):
        print(f"[ERROR send_message] to {chat_id}: {result.get('description')}")
    return result


def send_message_bg(chat_id, text, reply_markup=None, parse_mode=None):
    threading.Thread(
        target=send_message,
        args=(chat_id, text, reply_markup, parse_mode),
        daemon=True,
    ).start()


def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "☞ Зᴀяʙᴋᴀ нᴀ ʙхᴏд"}, {"text": "☞ Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ"}],
            [{"text": "️☞ Ꭺнᴏниʍнᴀя жᴀᴧᴏбᴀ"}, {"text": "☞ Ꮻᴛʍᴇнᴀ"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def answer_callback(callback_query_id, text=""):
    return tg_request("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


def answer_callback_bg(callback_query_id, text=""):
    threading.Thread(target=answer_callback, args=(callback_query_id, text), daemon=True).start()


def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        data["reply_markup"] = reply_markup
    result = tg_request("editMessageText", data)
    if not result.get("ok"):
        print(f"[edit_message ERROR] {result}")


def edit_message_bg(chat_id, message_id, text, reply_markup=None):
    threading.Thread(target=edit_message, args=(chat_id, message_id, text, reply_markup), daemon=True).start()


def create_invite_link(chat_id, user_id):
    result = tg_request(
        "createChatInviteLink",
        {"chat_id": chat_id, "member_limit": 1, "name": f"Invite for {user_id}"},
    )
    if result.get("ok"):
        return result["result"]["invite_link"]

    export = tg_request("exportChatInviteLink", {"chat_id": chat_id})
    if export.get("ok"):
        return export["result"]

    print(f"[create_invite_link] failed: {result}")
    return None


def get_reject_feedback_keyboard(kind, user_id):
    return {
        "inline_keyboard": [[
            {"text": "✉️ Дать обратную связь", "callback_data": f"reject_{kind}_fb_{user_id}"},
            {"text": "🚫 Без обратной связи", "callback_data": f"reject_{kind}_nofb_{user_id}"},
        ]]
    }


def get_chat_member_count(chat_id):
    if not chat_id:
        return -1
    result = tg_request("getChatMemberCount", {"chat_id": chat_id})
    if result.get("ok"):
        return result.get("result", -1)
    return -1


def get_user_join_chat(users, user_id):
    info = users.get(str(user_id), {})
    idx = info.get("chosen_chat_idx")
    try:
        idx = int(idx)
    except Exception:
        return None
    if 0 <= idx < len(AVAILABLE_CHATS):
        return AVAILABLE_CHATS[idx]
    return None


def do_send_invite(user_id, first_name, username, join_chat, callback_id=None):
    invite_link = create_invite_link(join_chat["chat_id"], user_id)
    if invite_link:
        send_message(
            user_id,
            "✔︎ 𐌏ᴛ᧘ᥙчн᧐.\n\n"
            f"✏︎ Ᏼ᧐ᴛ ʙᥲɯᥲ ᥰᥱρᥴ᧐нᥲ᧘ьнᥲя ᥴᥴы᧘κᥲ нᥲ ɸ᧘уд:\n{invite_link}\n\n"
            "⚠️ Ꮯᥴы᧘κᥲ ᧐дн᧐ρᥲᤋ᧐ʙᥲя — ᥙᥴᥰ᧐᧘ьᤋуᥔᴛᥱ ᥱё ᥴρᥲᤋу.\n\n"
            "Дᴏбᴩᴏ ᴨᴏжᴀᴧᴏʙᴀᴛь.",
        )
        send_message_bg(ADMIN_GROUP_ID, f"— {first_name} (@{username}, ID: {user_id}) ᴨᴏᴧучиᴧ дᴏᴄтуᴨ ᴋ ɸᴧуду ({join_chat['title']})")
        send_message_bg(ADMIN_ID, f"— {first_name} (@{username}, ID: {user_id}) ᴨᴏᴧучиᴧ дᴏᴄтуᴨ ᴋ ɸᴧуду ({join_chat['title']})")
    else:
        send_message(user_id, "✘ Оɯибᴋᴀ ᴄᴏɜдᴀния ᴄᴄыᴧκи. Обᴩᴀᴛиᴛᴇᴄь ᴋ ᴀдʍиниᴄᴛᴩᴀции.")
        send_message_bg(ADMIN_GROUP_ID, f"✘ Оɯибᴋᴀ ᴄᴄыᴧκи дᴧя {user_id}.")
        send_message_bg(ADMIN_ID, f"✘ Оɯибᴋᴀ ᴄᴄыᴧκи дᴧя {user_id}.")
    if callback_id:
        answer_callback(callback_id, "✔︎" if invite_link else "✘")

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        print(data)
        if not data:
            return "ok", 200

        # ================== CALLBACKS ==================
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_id = callback.get("id")
            cb = callback.get("data", "")
            message = callback.get("message", {})
            cb_user = callback.get("from", {})
            admin_id = cb_user.get("id")
            admin_id_str = str(admin_id)

            users = load_users()
            bookings = load_bookings()

            if cb.startswith("join_chat_"):
                try:
                    idx = int(cb.split("_")[2])
                    chat_info = AVAILABLE_CHATS[idx]
                except (ValueError, IndexError):
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200

                if chat_info.get("check_members", True):
                    count = get_chat_member_count(chat_info["chat_id"])
                    if count == -1:
                        send_message_bg(admin_id, "Ошибка при проверке участников. Попробуйте позже.")
                        answer_callback_bg(callback_id, "Ошибка!")
                        return "ok", 200

                    if count >= chat_info["max_members"]:
                        free = []
                        for i, c in enumerate(AVAILABLE_CHATS):
                            if i == idx:
                                continue
                            if not c.get("check_members", True):
                                free.append(i)
                                continue
                            other_count = get_chat_member_count(c["chat_id"])
                            if other_count != -1 and other_count < c["max_members"]:
                                free.append(i)
                        kb = [[{"text": f"В «{AVAILABLE_CHATS[i]['title']}» (свободно)", "callback_data": f"join_chat_{i}"}] for i in free]
                        kb.append([{"text": "Забронировать роль", "callback_data": f"book_role_{idx}"}])
                        msg = f"Чат «{chat_info['title']}» заполнен!\nВыбери другой или забронируй место." if free else "Все чаты заполнены! Можно забронировать место."
                        send_message_bg(admin_id, msg, reply_markup={"inline_keyboard": kb})
                        answer_callback_bg(callback_id, "☑️")
                        return "ok", 200

                users[admin_id_str] = {"step": "join_birthday", "type": "join", "chosen_chat": chat_info["title"], "chosen_chat_idx": idx}
                save_users(users)
                send_message_bg(admin_id, f"Выбран чат «{chat_info['title']}».\nОзнакомься с инфо: {chat_info['info_link']}\n\nУкажи дату рождения (например: 15 марта):")
                answer_callback_bg(callback_id, "✔️")
                return "ok", 200

            if cb.startswith("book_role_"):
                try:
                    idx = int(cb.split("_")[2])
                    chat_info = AVAILABLE_CHATS[idx]
                except (ValueError, IndexError):
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                users[admin_id_str] = {"step": "booking_birthday", "type": "booking", "chosen_chat": chat_info["title"], "chosen_chat_idx": idx}
                save_users(users)
                send_message_bg(admin_id, f"Бронь в чат «{chat_info['title']}».\n\nУкажи дату рождения (например: 15 марта):")
                answer_callback_bg(callback_id, "✔️")
                return "ok", 200

            if cb.startswith("show_booking_"):
                uid_str = cb.split("_")[2]
                booking = bookings.get(uid_str)
                if not booking:
                    send_message_bg(admin_id, "Бронь не найдена (возможно уже удалена).")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200

                fn = booking.get("first_name", "")
                un = booking.get("username", "Нет username")
                bday = booking.get("birthday", "")
                role = booking.get("role", "")
                cw = booking.get("codeword", "")
                ch = booking.get("chosen_chat", "")
                link = booking.get("info_link", "")

                text_msg = (
                    f"📋 Анкета брони\n\n"
                    f"➥ Имя: {fn}\n➥ Username: @{un}\n"
                    f"➥ Дата рождения: {bday}\n➥ Роль: {role}\n"
                    f"➥ Кодовое слово: {cw}\n➥ Чат: {ch} ({link})"
                )
                kb = {"inline_keyboard": [[
                    {"text": "𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐", "callback_data": f"approve_booking_{uid_str}"},
                    {"text": "𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ", "callback_data": f"reject_booking_{uid_str}"},
                ]]}
                send_message_bg(admin_id, text_msg, reply_markup=kb)
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("approve_join_"):
                try:
                    user_id = int(cb.split("_")[2])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                join_chat = get_user_join_chat(users, user_id)
                if not join_chat:
                    send_message_bg(admin_id, "Не удалось определить чат заявки.")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                kb = {"inline_keyboard": [[{"text": "— ✔︎.", "callback_data": f"read_info_{user_id}"}]]}
                send_message_bg(user_id, "— Ᏼᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ʙхᴏд ᴏдᴏбᴩᴇнᴀ.\n\n", reply_markup=kb)
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ〚ять ⲙяучₑ᧘᧐")
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("reject_join_") and "_nofb_" not in cb and "_fb_" not in cb:
                try:
                    user_id = int(cb.split("_")[2])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                if message:
                    edit_message_bg(
                        message["chat"]["id"],
                        message["message_id"],
                        message.get("text", "") + "\n\nОтклонено. Дать обратную связь?",
                        reply_markup=get_reject_feedback_keyboard("join", user_id),
                    )
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("read_info_") and not cb.startswith("read_info_booking_"):
                try:
                    user_id = int(cb.split("_")[2])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                fn = cb_user.get("first_name", "")
                un = cb_user.get("username", "Нет username")
                join_chat = get_user_join_chat(users, user_id)
                if not join_chat:
                    send_message_bg(user_id, "✘ Оɯибᴋᴀ ᴄᴏɜдᴀния ᴄᴄыᴧκи. Обᴩᴀᴛиᴛᴇᴄь ᴋ ᴀдʍиниᴄᴛᴩᴀции.")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                threading.Thread(target=do_send_invite, args=(user_id, fn, un, join_chat, callback_id), daemon=True).start()
                return "ok", 200

            if cb.startswith("read_info_booking_"):
                try:
                    user_id = int(cb.split("_")[3])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                fn = cb_user.get("first_name", "")
                un = cb_user.get("username", "Нет username")
                booking = bookings.get(str(user_id))
                if not booking:
                    send_message_bg(user_id, "✘ Оɯибᴋᴀ: бᴩᴏнь нᴇ нᴀйдᴇнᴀ.")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                join_chat = AVAILABLE_CHATS[int(booking["chosen_chat_idx"])]

                def _approve_booking():
                    do_send_invite(user_id, fn, un, join_chat, callback_id)
                    bk = load_bookings()
                    if str(user_id) in bk:
                        del bk[str(user_id)]
                        save_bookings(bk)

                threading.Thread(target=_approve_booking, daemon=True).start()
                return "ok", 200

            if cb.startswith("approve_booking_"):
                uid_str = cb.split("_")[2]
                booking = bookings.get(uid_str)
                if not booking:
                    send_message_bg(admin_id, "Бронь не найдена.")
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                user_id = int(booking["user_id"])
                kb = {"inline_keyboard": [[{"text": "— ✔︎.", "callback_data": f"read_info_booking_{user_id}"}]]}
                send_message_bg(user_id, "— Ᏼᴀɯᴀ бᴩᴏнь ᴏдᴏбᴩᴇнᴀ.\n\n", reply_markup=kb)
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ〚ять ⲙяучₑ᧘᧐")
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("reject_booking_") and "_nofb_" not in cb and "_fb_" not in cb:
                uid_str = cb.split("_")[2]
                booking = bookings.get(uid_str)
                user_id = int(booking["user_id"]) if booking else int(uid_str)
                if uid_str in bookings:
                    del bookings[uid_str]
                    save_bookings(bookings)
                send_message_bg(user_id, "— Ᏼᴀɯᴀ бᴩᴏнь ᴏᴛᴋᴧᴏнᴇнᴀ.")
                if message:
                    edit_message_bg(
                        message["chat"]["id"],
                        message["message_id"],
                        message.get("text", "") + "\n\nОтклонено. Дать обратную связь?",
                        reply_markup=get_reject_feedback_keyboard("booking", user_id),
                    )
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("approve_rest_"):
                try:
                    user_id = int(cb.split("_")[2])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                send_message_bg(user_id, "— Вᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ ᴏдᴏбᴩᴇнᴀ. Оᴛдыхᴀйтᴇ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐")
                answer_callback_bg(callback_id, "✔︎")
                return "ok", 200

            if cb.startswith("reject_rest_") and "_nofb_" not in cb and "_fb_" not in cb:
                try:
                    user_id = int(cb.split("_")[2])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                if message:
                    edit_message_bg(
                        message["chat"]["id"],
                        message["message_id"],
                        message.get("text", "") + "\n\nОтклонено. Дать обратную связь?",
                        reply_markup=get_reject_feedback_keyboard("rest", user_id),
                    )
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("reject_join_nofb_"):
                try:
                    user_id = int(cb.split("_")[3])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                send_message_bg(user_id, "— Ᏼᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ʙ᥊ᴏд ᧐ᴛκ᧘ᴏнₑнᥲ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ (без обратной связи)")
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("reject_rest_nofb_"):
                try:
                    user_id = int(cb.split("_")[3])
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                send_message_bg(user_id, "— Вᴀɯᴀ ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ ᴏᴛᴋᴧᴏнᴇнᥲ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ (без обратной связи)")
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            if cb.startswith("reject_booking_nofb_"):
                try:
                    uid_str = cb.split("_")[3]
                    user_id = int(uid_str)
                except ValueError:
                    answer_callback_bg(callback_id, "✘")
                    return "ok", 200
                bk = load_bookings()
                if uid_str in bk:
                    del bk[uid_str]
                    save_bookings(bk)
                send_message_bg(user_id, "— Ᏼᴀɯᴀ бᴩᴏнь ᴏᴛᴋᴧᴏнᴇнᴀ.")
                if message:
                    edit_message_bg(message["chat"]["id"], message["message_id"], message.get("text", "") + "\n\n𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ (без обратной связи)")
                answer_callback_bg(callback_id, "✘")
                return "ok", 200

            for kind in ("join", "rest", "booking"):
                if cb.startswith(f"reject_{kind}_fb_"):
                    target_uid = int(cb.split("_")[3])
                    users[admin_id_str] = {"type": "owner_feedback", "step": "wait_text", "target_user_id": target_uid, "reject_kind": kind}
                    save_users(users)
                    send_message_bg(admin_id, "Оставьте сообщение (будет отправлено пользователю как «Сообщение от владельца: ...»).")
                    answer_callback_bg(callback_id, "✉️ Напишите текст в этот чат")
                    return "ok", 200

            return "ok", 200

        # ================== MESSAGES ==================
        if "message" not in data:
            return "ok", 200

        message = data["message"]
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if not chat_id:
            return "ok", 200

        text = (message.get("text") or "").strip()
        username = message.get("from", {}).get("username", "Нет username")
        first_name = message.get("from", {}).get("first_name", "")

        if chat.get("type") in ["group", "supergroup"] and chat_id != ADMIN_GROUP_ID:
            return "ok", 200

        users = load_users()
        chat_id_str = str(chat_id)

        menu_texts = {
            "/start",
            "Гᴧᴀʙнᴏᴇ ʍᴇню:",
            "☞ Зᴀяʙᴋᴀ нᴀ ʙхᴏд",
            "☞ Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ",
            "️☞ Ꭺнᴏниʍнᴀя жᴀᴧᴏбᴀ",
            "☞ Ꮻᴛʍᴇнᴀ",
        }
        is_menu_click = text in menu_texts

        # Команда списка броней: реагируем только на "спящие", без учета регистра.
        if text.lower().strip() == "спящие":
            if chat_id not in [ADMIN_ID, ADMIN_GROUP_ID]:
                return "ok", 200

            bookings = load_bookings()
            if not bookings:
                send_message(chat_id, "— Список броней пуст.")
                return "ok", 200

            kb = []
            for uid_str, b in bookings.items():
                fn = b.get("first_name", "")
                un = b.get("username", "Нет username")
                ch = b.get("chosen_chat", "")
                kb.append([{
                    "text": f"{fn} (@{un}) → {ch}",
                    "callback_data": f"show_booking_{uid_str}"
                }])

            send_message(chat_id, "🕓 Список броней:", reply_markup={"inline_keyboard": kb})
            return "ok", 200

        if (
            not is_menu_click
            and chat_id_str in users
            and users[chat_id_str].get("type") == "owner_feedback"
            and users[chat_id_str].get("step") == "wait_text"
        ):
            target_uid = int(users[chat_id_str].get("target_user_id"))
            reject_kind = users[chat_id_str].get("reject_kind", "")
            send_message_bg(target_uid, f"Сообщение от владельца:\n\n{text}")
            send_message(chat_id, f"✔︎ Сообщение отправлено (ID: {target_uid}).", reply_markup=get_main_keyboard())
            send_message_bg(ADMIN_GROUP_ID, f"✉️ Обратная связь (kind={reject_kind}, ID={target_uid}):\n{text}")
            send_message_bg(ADMIN_ID, f"✉️ Обратная связь (kind={reject_kind}, ID={target_uid}):\n{text}")
            del users[chat_id_str]
            save_users(users)
            return "ok", 200

        if not is_menu_click and chat_id_str in users and users[chat_id_str].get("type") == "booking":
            step = users[chat_id_str].get("step")

            if step == "booking_birthday":
                users[chat_id_str]["birthday"] = text
                users[chat_id_str]["step"] = "booking_role"
                save_users(users)
                send_message(chat_id, "— Кᴀᴋую ᴩᴏᴧь ты хᴏчᴇɯь ɜᴀняᴛь?")
                return "ok", 200

            if step == "booking_role":
                users[chat_id_str]["role"] = text
                users[chat_id_str]["step"] = "booking_codeword"
                save_users(users)
                send_message(chat_id, "— Уκᴀжи κᴏдᴏʙᴏᴇ ᴄᴧᴏʙᴏ:")
                return "ok", 200

            if step == "booking_codeword":
                birthday = users[chat_id_str].get("birthday", "")
                role = users[chat_id_str].get("role", "")
                codeword = text
                chat_idx = users[chat_id_str].get("chosen_chat_idx", 0)
                chat_title = users[chat_id_str].get("chosen_chat", "")
                info_link = AVAILABLE_CHATS[int(chat_idx)]["info_link"]

                bookings = load_bookings()
                bookings[chat_id_str] = {
                    "user_id": chat_id,
                    "first_name": first_name,
                    "username": username,
                    "birthday": birthday,
                    "role": role,
                    "codeword": codeword,
                    "chosen_chat": chat_title,
                    "chosen_chat_idx": chat_idx,
                    "info_link": info_link,
                }
                save_bookings(bookings)

                del users[chat_id_str]
                save_users(users)

                send_message(chat_id, "✔︎ Ᏼᴀɯᴀ бᴩᴏнь ɜᴀᴩᴇᴦиᴄᴛᴩиᴩᴏʙᴀнᴀ. Мы уведомим вас, когда появится место!", reply_markup=get_main_keyboard())
                send_message_bg(ADMIN_GROUP_ID, f"🕓 Новая бронь: {first_name} (@{username}, ID: {chat_id}) → «{chat_title}»")
                send_message_bg(ADMIN_ID, f"🕓 Новая бронь: {first_name} (@{username}, ID: {chat_id}) → «{chat_title}»")
                return "ok", 200

        if text in ["/start", "Гᴧᴀʙнᴏᴇ ʍᴇню:"]:
            if chat_id_str in users:
                del users[chat_id_str]
                save_users(users)
            send_message(chat_id, "— Пᴩиʙᴇᴛ.\n\nᏴыбᴇᴩиᴛᴇ дᴇйᴄᴛʙиᴇ из ʍᴇню нижᴇ:", reply_markup=get_main_keyboard())
            return "ok", 200

        if text == "☞ Ꮻᴛʍᴇнᴀ":
            if chat_id_str in users:
                del users[chat_id_str]
                save_users(users)
                send_message(chat_id, "✘ Ꭲᴇᴋуɯᴇᴇ дᴇйᴄᴛʙиᴇ ᴏтʍᴇнᴇнᴏ.", reply_markup=get_main_keyboard())
            else:
                send_message(chat_id, "— Ꮋᴇᴛ ᴀᴋᴛиʙныx дᴇйᴄᴛʙий.", reply_markup=get_main_keyboard())
            return "ok", 200

        if text == "️☞ Ꭺнᴏниʍнᴀя жᴀᴧᴏбᴀ":
            send_message(chat_id, "— Ꭺнᴏниʍнᴀя жᴀᴧᴏбᴀ.\n\n✎ ᴏᴨиɯи жᴀᴧᴏбу — ᴏнᴀ yйдёт ᴀдʍинᴀʍ ᴀнᴏниʍнᴏ.\n\n⚠︎ ʜᴇ ɜᴧᴏyᴨᴏᴛᴩᴇбᴧяй.")
            users[chat_id_str] = {"step": "complaint_text", "type": "complaint"}
            save_users(users)
            return "ok", 200

        if chat_id_str in users and users[chat_id_str].get("type") == "complaint" and users[chat_id_str].get("step") == "complaint_text":
            admin_msg = f"⚠︎ жᴀᴧᴏбᴀ\n\n✎ Тᴇᴋᴄᴛ:\n{text}\n\nОᴛᴨᴩᴀʙᴧᴇнᴏ ᴀнᴏниʍнᴏ"
            send_message_bg(ADMIN_GROUP_ID, admin_msg)
            send_message_bg(ADMIN_ID, admin_msg)
            send_message(chat_id, "✔︎ Вᴀɯᴀ жᴀᴧᴏбᴀ ᴏᴛᴨᴀʙʙᴧᴇнᴀ ᴀнᴏниʍнᴏ.", reply_markup=get_main_keyboard())
            del users[chat_id_str]
            save_users(users)
            return "ok", 200

        if text == "☞ Зᴀяʙᴋᴀ нᴀ ʙхᴏд":
            users[chat_id_str] = {"step": "join_choose_chat", "type": "join"}
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
                codeword = text
                chat_idx = users[chat_id_str].get("chosen_chat_idx", 0)
                chat_title = users[chat_id_str].get("chosen_chat", "")
                info_link = AVAILABLE_CHATS[int(chat_idx)]["info_link"]
                admin_msg = (
                    "📩 Нᴏʙᴀя ɜᴀяʙᴋᴀ нᴀ ʙхᴏд\n\n"
                    f"➥ Иʍя: {first_name}\n➥ Usᴇrnᴀʍᴇ: @{username}\n"
                    f"➥ Дᴀᴛᴀ ᴩᴏждᴇния: {birthday}\n➥ Жᴇᴧᴀᴇʍᴀя ᴩᴏᴧь: {role}\n"
                    f"➥ Кᴏдᴏʙᴏᴇ ᴄᴧᴏʙᴏ: {codeword}\n➥ Чᴀᴛ: {chat_title} ({info_link})"
                )
                kb = {"inline_keyboard": [[
                    {"text": "𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐", "callback_data": f"approve_join_{chat_id}"},
                    {"text": "𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ", "callback_data": f"reject_join_{chat_id}"},
                ]]}
                send_message_bg(ADMIN_GROUP_ID, admin_msg, reply_markup=kb)
                send_message_bg(ADMIN_ID, admin_msg, reply_markup=kb)
                send_message(chat_id, "✔︎ ɜᴀяʙᴋᴀ ᴏᴛᴨᴩᴀʙᴧᴇнᴀ. Ꮎжидᴀй ᴩᴇɯᴇния.", reply_markup=get_main_keyboard())
                users[chat_id_str]["step"] = "join_wait_admin"
                save_users(users)
                return "ok", 200

        if text == "☞ Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ":
            send_message(chat_id, "— ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ.\n\n✦ Кᴀᴋᴀя у ᴛᴇбя ᴩᴏᴧь?")
            users[chat_id_str] = {"step": "rest_role", "type": "rest"}
            save_users(users)
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
                admin_msg = (
                    "📩 Зᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ\n\n"
                    f"➥ Иʍя: {first_name}\n➥ Usᴇrnᴀʍᴇ: @{username}\n"
                    f"➥ Рᴏᴧь: {role}\n➥ Сᴩᴏк: {duration}\n➥ Пᴩичинᴀ: {text}"
                )
                kb = {"inline_keyboard": [[
                    {"text": "𐌿ρᥙняᴛь ⲙяучᥱ᧘᧐", "callback_data": f"approve_rest_{chat_id}"},
                    {"text": "𐌿ρ᧐ᴦнᥲᴛь ᥰᥴᥲ", "callback_data": f"reject_rest_{chat_id}"},
                ]]}
                send_message_bg(ADMIN_GROUP_ID, admin_msg, reply_markup=kb)
                send_message_bg(ADMIN_ID, admin_msg, reply_markup=kb)
                send_message(chat_id, "✔︎ ɜᴀяʙᴋᴀ нᴀ ᴩᴇᴄᴛ ᴏᴛᴨᴀʙʙᴧᴇнᴀ. Ꮎжидᴀй ᴩᴇɯᴇния.", reply_markup=get_main_keyboard())
                del users[chat_id_str]
                save_users(users)
                return "ok", 200

        send_message(chat_id, "— Иᴄᴨᴏᴧьɜуй ᴋнᴏᴨᴋи ʍᴇню нижᴇ.", reply_markup=get_main_keyboard())
        return "ok", 200

    except Exception as e:
        print(f"[webhook] Exception: {e}")
        traceback.print_exc()
        return "ok", 200


@app.route("/set_webhook")
def set_webhook():
    result = tg_request("setWebhook", {"url": WEBHOOK_URL})
    print("[set_webhook]", result)
    return result


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
