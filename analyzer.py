from calendar import monthrange
import os, json
from collections import defaultdict
from datetime import timedelta, timezone, datetime
from zoneinfo import ZoneInfo

app_timezone = ZoneInfo("Europe/Moscow")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FOLDER = os.path.join(SCRIPT_DIR, "stats")

def format_playtime(seconds, lang):
    minutes = seconds / 60
    minute = 'm' if lang == 'EN' else 'м'
    hour = 'h' if lang == 'EN' else 'ч'
    day = 'd' if lang == 'EN' else 'д'
    if minutes < 1:
        return f"~1{minute}"
    elif minutes < 60:
        return f"{round(minutes, 1)}{minute}"
    else:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        parts = []
        if days:
            parts.append(f"{days}{day}")
        if hours:
            parts.append(f"{hours}{hour}")
        if minutes:
            parts.append(f"{minutes}{minute}")
        return " ".join(parts)

def calculate_session_seconds(sessions):
    total = 0
    for session in sessions:
        try:
            start = datetime.fromisoformat(session['play_start'])
            end = datetime.fromisoformat(session['play_end'])
            duration = (end - start).total_seconds()
            if duration > 0:
                total += duration
        except:
            continue
    return total

def get_date_range(option: str):
    today = datetime.now(app_timezone)
    if option == "today":
        return [today.strftime("%Y-%m-%d")]

    elif option == "yesterday":
        yest = today - timedelta(days=1)
        return [yest.strftime("%Y-%m-%d")]

    elif option == "this_week":
        return [
            (today - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in reversed(range(7))
        ]
    elif option == "this_month":
        year, month = today.year, today.month
        days_in_month = monthrange(year, month)[1]
        start = today.replace(day=1)
        return [
            (start + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days_in_month)
        ]

    else:
        raise ValueError("Invalid option. Choose from: today, yesterday, this_week, this_month")

def players_analyzer(period, language="EN"):
    if not os.path.exists(STATS_FOLDER):
        print("❌ Stats folder not found.")
        return
    wanted_dates = get_date_range(period)
    minimum_data_files = {
        'today': 1,
        'yesterday': 2,
        'this_week': 3,
        'this_month': 7,
    }
    all_files = [
        f for f in os.listdir(STATS_FOLDER)
        if f.startswith("players-") and f.endswith((".json", ".jsonl"))
    ]

    relevant_files = [
        f for f in all_files
        if os.path.splitext(f)[0].replace("players-", "") in wanted_dates
    ]
    min_data_required = minimum_data_files.get(period, 1)
    data_found = len(all_files)
    if not (data_found >= min_data_required): 
        print('[REJECTED]:', 'Found', data_found, 'min was', min_data_required)
        return

    if not relevant_files:
        print("⚠️ No matching JSON files found in stats folder.")
        return
    player_stats = defaultdict(lambda: {
        "total_seconds": 0,
        "total_score": 0,
    })
    for filename in relevant_files:
        file_path = os.path.join(STATS_FOLDER, filename)

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    name = entry.get("player_name", "").strip() or 'NoName'
                    sessions = entry.get("sessions", [])

                    duration = calculate_session_seconds(sessions)
                    score_sum = sum(
                        int(s.get("score", 0)) for s in sessions
                        if s.get("play_start") and s.get("play_end")
                    )
                    stats = player_stats[name]
                    stats["total_seconds"] += duration
                    stats["total_score"] += score_sum
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
                    continue

    requested_stats = []
    for name, data in sorted(player_stats.items(), key=lambda x: x[1]["total_seconds"], reverse=True):
        readable_time = format_playtime(data["total_seconds"], language)
        player_score = max(0, data['total_score'])
        requested_stats.append({
            'name': name,
            'score': player_score,
            'gameplay': readable_time
        })

    return requested_stats