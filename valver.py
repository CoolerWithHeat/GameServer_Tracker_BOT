from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters 
import json, os, asyncio, valve.source.a2s
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime, timedelta
from analyzer import players_analyzer, app_timezone as operating_timezone
from zoneinfo import ZoneInfo

USER_FILE = "users.json"
server_address = ("46.174.50.10", 27236)
app_timezone = operating_timezone #ZoneInfo("Europe/Moscow")
server_data = {}
moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))
tashkent_time = datetime.now(ZoneInfo("Asia/Tashkent"))
today = moscow_time.date()

SESSION_GAP_SECONDS = 7

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_TIME_FILE = os.path.join(SCRIPT_DIR, "server_time.json")

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        try:
            return json.load(f)
        except: return {}

def load_last_server_time():
    if os.path.exists(SERVER_TIME_FILE):
        try:
            with open(SERVER_TIME_FILE, 'r') as f:
                data = json.load(f)
                return datetime.fromisoformat(data['last_time'])
        except Exception:
            pass
    return None

def save_current_server_time(now):
    with open(SERVER_TIME_FILE, 'w') as f:
        json.dump({'last_time': now.isoformat()}, f)

month_translation = {
    "January": "Январь",
    "February": "Февраль",
    "March": "Март",
    "April": "Апрель",
    "May": "Май",
    "June": "Июнь",
    "July": "Июль",
    "August": "Август",
    "September": "Сентябрь",
    "October": "Октябрь",
    "November": "Ноябрь",
    "December": "Декабрь"
}

def save_players_stats(data):
    os.makedirs("stats", exist_ok=True)
    date_str = datetime.now(app_timezone).strftime("%Y-%m-%d")
    filepath = os.path.join("stats", f"players-{date_str}.jsonl")

    existing_data = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    name = record['player_name']
                    existing_data[name] = record
                except:
                    continue

    now = datetime.now(app_timezone)
    last_server_time = load_last_server_time()
    downtime = max(0, (now - last_server_time).total_seconds()) if last_server_time else 0
    session_gap = max(SESSION_GAP_SECONDS, downtime)
    if downtime > SESSION_GAP_SECONDS: print('[DOWNTIME]:', 'adjusted for', int(downtime), 'seconds')
    for record in data:
        name = record['player_name']
        playtime = record['player_playtime']
        score = record.get('player_score', 0)
        now_iso = now.isoformat()

        if name not in existing_data:
            play_start = (now - timedelta(seconds=playtime)).isoformat()
            record['timestamp'] = now_iso
            record['last_seen'] = now_iso
            record['sessions'] = [{
                'play_start': play_start,
                'play_end': now_iso,
                'score': score
            }]
            existing_data[name] = record

        else:
            saved = existing_data[name]
            last_seen_str = saved.get('last_seen')
            last_seen = datetime.fromisoformat(last_seen_str) if last_seen_str else now
            time_diff = (now - last_seen).total_seconds()

            saved['last_seen'] = now_iso

            if 'sessions' not in saved or not saved['sessions']:
                play_start = (now - timedelta(seconds=playtime)).isoformat()
                saved['sessions'] = [{
                    'play_start': play_start,
                    'play_end': now_iso,
                    'score': score
                }]
            else:
                last_session = saved['sessions'][-1]
                if time_diff <= session_gap:
                    last_session['play_end'] = now_iso
                    if score > last_session.get('score', 0):
                        last_session['score'] = score
                else:
                    saved['sessions'].append({
                        'play_start': now_iso,
                        'play_end': now_iso,
                        'score': score
                    })
            if playtime > saved.get('player_playtime', 0):
                saved['player_playtime'] = playtime
                saved['timestamp'] = now_iso
            if score > saved.get('player_score', 0):
                saved['player_score'] = score

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for record in existing_data.values():
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
    except Exception as e:
        print('Error occurred when saving:', e)

    save_current_server_time(now)

def PlayersStat(data):
    records = []
    for each_player in data:
        player_name = each_player['name']
        player_playtime = each_player['duration']   
        player_score = each_player['score']
        playtime_format = 'seconds'

        record = {
            'player_name': player_name,
            'player_playtime': player_playtime,
            'player_score': player_score,
            'playtime_format': playtime_format
        }
        records.append(record)

    save_players_stats(records)


def getUserLanguage(data={}): 
    user_data = data or {}
    language = user_data.get('language', 'EN')
    return language

def load_user_schedule(user_id):
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        try:
            data = json.load(f)
            user_data = data.get(user_id)
            return user_data.get('players_alarm')
        except: return 0

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def russian_form(count: int) -> str:
    if 11 <= count % 100 <= 14:
        return "игроков"
    last_digit = count % 10
    if last_digit == 1:
        return "игрок"
    elif 2 <= last_digit <= 4:
        return "игрока"
    else:
        return "игроков"


def render_text_image(text, font_size=30, padding=30, line_spacing=6):
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    font = ImageFont.truetype(font_path, font_size)
    lines = text.split("\n")
    width = max(int(font.getlength(line)) for line in lines) + 2 * padding
    height = (font_size + line_spacing) * len(lines) + 2 * padding
    img = Image.new("RGB", (width, height), color=(18, 18, 18))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        y = padding + i * (font_size + line_spacing)
        draw.text((padding, y), line, font=font, fill=(255, 255, 255))
    return img

def getTimePlayed(seconds, lang="EN"):
    if seconds < 60:
        return "1м" if lang == "RU" else "1m"
    elif seconds < 90:
        return "1.5м" if lang == "RU" else "1.5m"
    elif seconds < 3600:
        minutes = round(seconds / 60)
        return f"{minutes}м" if lang == "RU" else f"{minutes}m"
    else:
        hours = seconds / 3600
        if hours < 1.5:
            return "~1ч" if lang == "RU" else "~1h"
        else:
            calculated_hours = round(hours, 1)
            calculated_hours = int(calculated_hours) if calculated_hours.is_integer() else calculated_hours
            return f"{calculated_hours}ч" if lang == "RU" else f"{calculated_hours}h"

def get_players(players, lang="EN"):
    score_exists = False
    players_list = []
    for player in players["players"]:
        player_name = player.get('name')
        player_score = player.get('score')
        player_gameplay_duration = player.get('duration')
        if int(player['score']) > 0:
            score_exists = True
        formatted_duration = round(player_gameplay_duration)
        player_data = {
            'name': player_name if player_name else 'NoName',
            'played': getTimePlayed(formatted_duration, lang)
        }
        players_list.append(player_data)
    return players_list

def freeSpaceCalc(space):
    if (space % 2) == 0:
        space_needed = space / 2
        return int(space_needed), int(space_needed)
    else:
        space1 = (space / 2) + 0.5
        space2 = space - space1
        return int(space1), int(space2)

def formPlayerList(player_info):
    player_name = player_info.get('name', 'NoName')[:23]
    player_played = player_info.get('played')
    name_col = player_name.center(23)
    played_col = player_played.center(8)
    return f"#{name_col}|{played_col}#"


def build_players_string(players_list, server_info, lang="EN"):
    lines = []
    if lang == "RU":
        lines.append(f"\nСервер: {server_info['server_name']}")
        lines.append(f"Карта: {server_info['map']}")
        lines.append(f"Игроки: {server_info['player_count']} / {server_info['max_players']}")
    else:
        lines.append(f"\nServer: {server_info['server_name']}")
        lines.append(f"Map: {server_info['map']}")
        lines.append(f"Players: {server_info['player_count']} / {server_info['max_players']}")
    if len(players_list) > 0:
        lines.append('\n')
        lines.append('##################################')
        if lang == "RU":
            lines.append('#         ИГРОК         | В ИГРЕ #')
        else:
            lines.append('#         PLAYERS       | PLAYED #')
        lines.append('#--------------------------------#')
        for each_player in players_list:
            formed_player = formPlayerList(each_player)
            lines.append(formed_player)
        lines.append('##################################')
    return "\n".join(lines)

def LocalParser(serverData, language):
    info = serverData.get('info')
    players_data = serverData.get('players')
    players_list = get_players(players_data, language)
    return build_players_string(players_list, info, lang=language)

def GetServerData(user_lang="EN", for_background_task=False):
    with valve.source.a2s.ServerQuerier(server_address) as server:
        global server_data 
        info = server.info()
        players_data = server.players()
        server_data = {
            "info": dict(info),
            "players": dict(players_data)
        }
        PlayersStat(server_data['players']['players'])
        players_list = get_players(players_data, user_lang)
        if(not for_background_task): return build_players_string(players_list, info, lang=user_lang)
        else: return players_data, players_list


BOT_TOKEN = "" #Bot Token Right Here

LANGUAGE_CHOICES = [["EN", "RU"]]

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str):
    user_id = str(update.effective_user.id)
    users = load_users()
    players_alarm = load_user_schedule(user_id)
    users[user_id] = {'language': lang_code, 'players_alarm': players_alarm}
    save_users(users)

    message_text = (
        "✅ Language set to English." if lang_code == "EN"
        else "✅ Язык изменён на русский."
    )
    reply_markup = get_persistent_menu(lang_code)

    if update.callback_query:
        await update.callback_query.edit_message_text(message_text)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="_____________☠️ MAFIA ☠️_____________",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )


async def handle_persistent_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    lang = users.get(user_id, "EN")
    if (lang == "EN" and update.message.text == "Check Status") or \
       (lang == "RU" and update.message.text == "Проверить Статус"):
        await check_status(update, context)

async def show_cube_choices(update: Update, context: ContextTypes.DEFAULT_TYPE, lang="EN"):
    message_text = "📅 Choose Time Period ↓" if lang == "EN" else "📅 Выберите период ↓"
    await update.message.reply_text(
        message_text,
        reply_markup=cube_inline_keyboard(lang)
    )

async def send_loading_notice(update: Update, context: ContextTypes.DEFAULT_TYPE, language="EN", delay=3):
    try:
        async def PerformLoading():
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⏳ Loading, please wait..." if language == "EN" else "⏳ Загрузка, пожалуйста, подождите..."
            )
            await asyncio.sleep(delay)
            await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
        asyncio.create_task(PerformLoading())
    except Exception as e:
        print(f"Error in send_loading_notice: {e}")

async def handle_status_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    requesting_user = users.get(user_id, {})
    user_exists = len(requesting_user.keys())
    if user_exists:
        lang = requesting_user.get('language', "EN")
        button_pressed = update.message.text.strip()
        if (lang == "RU" and button_pressed == "🎮 Проверить Статус") or (lang == "EN" and button_pressed == "🎮 Check Status"):
            await check_status(update, context)

        elif (lang == "RU" and button_pressed == "⏰ Установить Будильник") or (lang == "EN" and button_pressed == "⏰ Set Alarm"):
            await set_alarm(update, context)
        elif (lang == "RU" and button_pressed == "📊 Статистика Игроков") or (lang == "EN" and button_pressed == "📊 Player Stats"):
            await show_cube_choices(update, context, lang)
    else:
        await greet(update, context)


def get_main_menu(lang):
    if lang == "RU":
        return ReplyKeyboardMarkup(
            [[KeyboardButton("Проверить Статус")]],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            [[KeyboardButton("Check Status")]],
            resize_keyboard=True
        )

async def greet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="/en"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="/ru")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Language | Язык",
        reply_markup=reply_markup
    )

async def en_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_language(update, context, "EN")

async def ru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_language(update, context, "RU")

def VerifiedName():
    players = server_data['players']['players']
    for each_player in players:
        player_name = each_player['name']
        player_played = each_player['duration']
        played_30_secs = int(player_played) >= 30
        if (not player_name) and (not played_30_secs): return False
    return True 

def is_alarm_triggered(alarm_value, player_count):
    lower_end = {
        2: 1,
        5: 3,
        9: 6,
        10: 10
    }
    if alarm_value:
        making_difference = lower_end[alarm_value] == player_count
        if alarm_value == 2:
            if making_difference:  return VerifiedName()
            return 1 <= player_count <= 2
        elif alarm_value == 5:
            if making_difference:  return VerifiedName()
            return 3 <= player_count <= 5
        elif alarm_value == 9:
            if making_difference:  return VerifiedName()
            return 6 <= player_count <= 9
        elif alarm_value == 10:
            if making_difference:  return VerifiedName()
            return player_count >= 10
    return False

async def handle_language_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "/en":
        await set_language(update=update, context=context, lang_code="EN")
    elif query.data == "/ru":
        await set_language(update=update, context=context, lang_code="RU")

def cube_inline_keyboard(lang):
    if lang == "RU":
        buttons = [
            [
                InlineKeyboardButton("Сегодня", callback_data="today-stats"),
                InlineKeyboardButton("Вчера", callback_data="yesterday-stats")
            ],
            [
                InlineKeyboardButton("За неделю", callback_data="weekly-stats"),
                InlineKeyboardButton("За месяц", callback_data="monthly-stats")
            ]
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton("Today", callback_data="today-stats"),
                InlineKeyboardButton("Yesterday", callback_data="yesterday-stats")
            ],
            [
                InlineKeyboardButton("Weekly", callback_data="weekly-stats"),
                InlineKeyboardButton("Monthly", callback_data="monthly-stats")
            ]
        ]
    return InlineKeyboardMarkup(buttons)


def get_persistent_menu(lang):
    if lang == "RU":
        buttons = [
            [KeyboardButton("🎮 Проверить Статус")],
            [KeyboardButton("⏰ Установить Будильник")],
            [KeyboardButton("📊 Статистика Игроков")]
        ]
    if lang == "EN":
        buttons = [
            [KeyboardButton("🎮 Check Status")],
            [KeyboardButton("⏰ Set Alarm")],
            [KeyboardButton("📊 Player Stats")]
        ]

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )



async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    requesting_user = users.get(user_id, {})
    lang = requesting_user.get('language', "EN")
    await send_loading_notice(update, context, lang, 0.5)
    data_exists = len(server_data.keys()) > 0
    text_output = LocalParser(server_data, lang) if data_exists else GetServerData(user_lang=lang)
    img = render_text_image(text_output, font_size=30)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    await update.message.reply_photo(
        photo=buffer,
        caption="🎮 Статус" if lang == "RU" else "🎮 Server Status"
    )

def get_alarm_inline_keyboard(lang):
    if lang == "RU":
        buttons = [
            [InlineKeyboardButton("🔔 1-2 Игрока", callback_data="/alarm-set-2")],
            [InlineKeyboardButton("🔔 3-5 Игроков", callback_data="/alarm-set-5")],
            [InlineKeyboardButton("🔔 6-9 Игроков", callback_data="/alarm-set-9")],
            [InlineKeyboardButton("🔔 10+ Игроков", callback_data="/alarm-set-10")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🔔 1-2 Players", callback_data="/alarm-set-2")],
            [InlineKeyboardButton("🔔 3-5 Players", callback_data="/alarm-set-5")],
            [InlineKeyboardButton("🔔 6-9 Players", callback_data="/alarm-set-9")],
            [InlineKeyboardButton("🔔 10+ Players", callback_data="/alarm-set-10")]
        ]
    return InlineKeyboardMarkup(buttons)


async def set_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()
    user = users.get(user_id, {})
    user_language = user.get('language', 'EN')

    text = "Notify you when there are this many players on the server: " if user_language == "EN" else "Уведомлять вас когда на сервере будет:"
    
    await update.message.reply_text(
        text,
        reply_markup=get_alarm_inline_keyboard(user_language)
    )

async def handle_alarm_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    users = load_users()
    user = users.get(user_id, {})
    lang = user.get('language', 'EN')
    alarm_plans = {
        2: '1-2',
        5: '3-5',
        9: '6-9',
        10: '10+'
    }
    data = query.data
    try:
        players = int(data.split("-")[-1])
    except Exception:
        players = 0

    users[user_id]['players_alarm'] = players
    save_users(users)
    success_msg = (
        f"✅ You'll be notified when there are {alarm_plans[players]} players on the server." if lang == "EN"
        else f"✅ Получите уведомление когда на сервере будет {alarm_plans[players]} {russian_form(players)}."
    )
    await query.edit_message_text(success_msg)

async def AlertMessageSender(app, user_id: str, lang: str = "EN", message: str = "EN"):
    data_exists = len(server_data.keys()) > 0
    text_output = LocalParser(server_data, lang) if data_exists else GetServerData(user_lang=lang)
    img = render_text_image(text_output, font_size=30)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    try:
        await app.bot.send_photo(
            chat_id=int(user_id),
            photo=buffer,
            caption= message,
        )
        print(f"[ALERT MESSAGE SENT] to {user_id}")
    except Exception as e:
        print(f"[ERROR] Failed to send alert image to {user_id}: {e}")


def reset_alarm(users={}, user_id='', language="EN"):
    if len(users.keys()) and len(user_id) > 5:
        users[user_id] =  {"language": language, "players_alarm": 0}
        save_users(users)
    else: print('user alert reset failed!')

async def AlertUser(app, user_id, player_count, language, users):
    try:
        Alert_Messages = {
            'EN': f' ___⏰___ ALERT ___⏰___ \n\n{player_count} player{'s' if (player_count > 1) else ''} already playing!',
            'RU': f'_⏰_Оповещение_⏰_ \n {player_count} {russian_form(player_count)} на сервере!',
        }
        message = Alert_Messages.get(language)
        await AlertMessageSender(app, user_id, language, message)
        reset_alarm(users, user_id, language)
    except Exception as e:
        print(f"[ALERT ERROR] Could not notify user {user_id}: {e}")

async def background_player_tracker(app):
    while True:
        players_data, players_list = GetServerData(for_background_task=True)
        players_count = len(players_list)
        print(f"[Tracker] players: {players_count}")
        users = load_users()
        for user_id, data in users.items():
            alarm_value = data.get("players_alarm", 0)
            language = data.get("language", 'EN')
            if is_alarm_triggered(alarm_value, players_count): 
                await AlertUser(app, user_id, players_count, language, users)
        await asyncio.sleep(3)

async def handle_stats_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    users = load_users()
    user = users.get(user_id, {})
    lang = user.get('language', 'EN')
    await query.answer()
    callback = query.data
    def english_hints(): return '\n\n______ PLAYER  →  PLAYED  →  SCORE ____'
    def russian_hints(): return '\n\n______ ИГРОК  →  ИГРАЛ(а)  →  ОЧКИ ___'
    month_name = today.strftime("%B")
    operation_identifiers = {
        "today-stats" : 'today',
        "yesterday-stats" : 'yesterday',
        "weekly-stats" : 'this_week',
        "monthly-stats" : 'this_month',
    }

    header_text = {
        "EN": {
            "today-stats": "📅 Today’s Player Stats",
            "yesterday-stats": "📅 Yesterday’s Player Stats",
            "weekly-stats": "📈 Weekly Player Stats",
            "monthly-stats": f"📊 Player Stats of {month_name}"
        },
        "RU": {
            "today-stats": "📅 Статистика за сегодня",
            "yesterday-stats": "📅 Статистика за вчера",
            "weekly-stats": "📈 Статистика за неделю",
            "monthly-stats": f"📊 Статистика За {month_translation[month_name]}"
        }
    }

    stat_date = operation_identifiers.get(callback, 'today')
    stats = players_analyzer(stat_date, lang)
    selected_label = header_text.get(lang, {}).get(callback, "📊 Player Stats")

    if not stats:
        message = {
            "EN": "⚠️ No data available for this period.",
            "RU": "⚠️ Нет данных за этот период."
        }.get(lang, "⚠️ No data.")
    else:
        selected_label += english_hints() if lang == 'EN' else russian_hints()
        lines = []
        for index, entry in enumerate(stats, start=1):
            lines.append(f"{index}  👤{entry['name']} | 🕹️{entry['gameplay']} | 🧮 {entry['score']}")
        message = "\n".join(lines)

    final_text = f"{selected_label}\n\n{message}"
    await query.edit_message_text(final_text)

async def start_background_tasks(app):
    app.create_task(background_player_tracker(app))

def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(start_background_tasks)
        .build()
    )
    app.add_handler(CommandHandler("start", greet))
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(CommandHandler("en", en_command))
    app.add_handler(CommandHandler("ru", ru_command))
    app.add_handler(CallbackQueryHandler(handle_alarm_selection, pattern=r"^/alarm-set-\d+$"))
    app.add_handler(CallbackQueryHandler(handle_stats_selection, pattern=r"^(today|yesterday|weekly|monthly)-stats$"))
    app.add_handler(CallbackQueryHandler(handle_language_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_status_button))
    app.add_handler(CallbackQueryHandler(handle_stats_selection, pattern=r"^(today|yesterday|weekly|monthly)-stats$"))

    app.run_polling()

if __name__ == "__main__":
    main()