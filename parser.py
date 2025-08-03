import csv
from datetime import datetime
import matplotlib.pyplot as plt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time, os
from dotenv import load_dotenv
import requests

# === Конфигурация ===
NIGHT_HOURS = range(0, 6)
LOG_FILE = "sample_logs.csv"
REPORT_FILE = "output_report.txt"
ALERT_FILE = "alerts.log"

# === Telegram ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram_alert(text):
    if TELEGRAM_TOKEN and CHAT_ID:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": text}
        )

# === Слежение за изменениями в логах ===
class LogWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".csv"):
            print(f"Обнаружен новый файл: {event.src_path}")
            os.system("python parser.py")

observer = Observer()
observer.schedule(LogWatcher(), path=".", recursive=False)
observer.start()
print("Следим за логами...")

# === Инициализация переменных ===
night_logins = []
file_downloads = {}
night_downloads = {}
login_fails = {}
file_deletes = []
ip_activity = {}
alerts = []

# === Чтение логов ===
with open(LOG_FILE, "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    logs = list(reader)

for row in logs:
    ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
    hour = ts.hour
    user = row["username"]
    ip = row["src_ip"]
    event = row["event"]

    ip_activity[ip] = ip_activity.get(ip, 0) + 1

    if event == "login_success" and hour in NIGHT_HOURS:
        night_logins.append(row)

    if event == "file_download":
        file_downloads[user] = file_downloads.get(user, 0) + 1
        if hour in NIGHT_HOURS:
            night_downloads[user] = night_downloads.get(user, 0) + 1

    if event == "login_failed":
        login_fails[ip] = login_fails.get(ip, 0) + 1

    if event == "file_delete":
        file_deletes.append((row, hour))

# === Генерация отчёта ===
with open(REPORT_FILE, "w", encoding="utf-8") as out:
    out.write("🔒 Ночные входы:\n")
    for e in night_logins:
        out.write(f"{e['timestamp']} — {e['username']} ({e['src_ip']})\n")

    out.write("\n📥 Подозрительные загрузки файлов (3+):\n")
    for user, count in file_downloads.items():
        if count >= 3:
            out.write(f"{user}: {count} загрузок\n")

    out.write("\n🌙 Ночные загрузки:\n")
    for user, count in night_downloads.items():
        out.write(f"{user}: {count} загрузок ночью\n")

    out.write("\n🛑 Брутфорс (3+ login_failed от одного IP):\n")
    for ip, count in login_fails.items():
        if count >= 3:
            out.write(f"{ip}: {count} login_failed\n")

    out.write("\n🧹 Удаления файлов (особенно ночью):\n")
    for (e, hour) in file_deletes:
        flag = "🕒 НОЧЬ!" if hour in NIGHT_HOURS else ""
        out.write(f"{e['timestamp']} — {e['username']} ({e['src_ip']}) {flag}\n")

    out.write("\n📊 Активность по IP:\n")
    for ip, count in ip_activity.items():
        out.write(f"{ip}: {count} событий\n")

# === Алерты в alert.log + Telegram ===
alerts = []
for user, count in file_downloads.items():
    if count >= 5:
        alerts.append(f"⚠️ Много загрузок: {user} — {count}")
for ip, count in login_fails.items():
    if count >= 3:
        msg = f"❗️Подозрение на брутфорс\nIP: {ip}\nОшибок входа: {count}"
        alerts.append(msg)

for row, hour in file_deletes:
    if hour in NIGHT_HOURS:
        msg = (
            f"❗️Ночное удаление файла\n"
            f"Юзер: {row['username']}\n"
            f"IP: {row['src_ip']}\n"
            f"Время: {row['timestamp']}"
        )
        alerts.append(msg)

# === Запись в файл и отправка в Telegram
with open(ALERT_FILE, "w", encoding="utf-8") as alert_file:
    for alert in alerts:
        alert_file.write(alert + "\n\n")
        send_telegram_alert(alert)

# === Визуализация графиков ===

# 📊 График 1: активность по часам
hours = [datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S").hour for e in logs]
hour_freq = {}
for h in hours:
    hour_freq[h] = hour_freq.get(h, 0) + 1

plt.bar(hour_freq.keys(), hour_freq.values(), color='skyblue')
plt.title("Активность по часам")
plt.xlabel("Час")
plt.ylabel("Количество событий")
plt.grid(True)
plt.savefig("activity_by_hour.png")
plt.clf()

# 📊 График 2: загрузки по пользователям
users = list(file_downloads.keys())
downloads = list(file_downloads.values())
plt.bar(users, downloads, color='orange')
plt.title("Скачивания файлов по пользователям")
plt.xlabel("Пользователь")
plt.ylabel("Количество загрузок")
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()
plt.savefig("downloads_by_user.png")
