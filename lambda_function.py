import json
import boto3
import requests
import smtplib
import os
import time
from email.mime.text import MIMEText
from datetime import datetime

# Force Lambda to use Eastern Time for our scheduling checks
os.environ['TZ'] = 'America/New_York'
time.tzset()

def _load_local_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_local_env()

GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
GMAPS_API_KEY = os.environ.get('GMAPS_API_KEY', '')

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('CommuteUsers')

def get_weather_description(code):
    if code in [0, 1]: return "Clear ☀️"
    if code in [2, 3]: return "Cloudy ☁️"
    if code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return "Rain 🌧️"
    if code in [56, 57, 66, 67]: return "Freezing Rain 🧊"
    if code in [71, 73, 75, 77, 85, 86]: return "Snow ❄️"
    if code in [95, 96, 99]: return "Thunderstorms ⚡"
    return "Mixed conditions"

def get_commute_data(start_coords, end_coords):
    if not GMAPS_API_KEY:
        print("Maps API key is not set")
        return "Unknown", 0

    origin = f"{start_coords['lat']},{start_coords['lon']}"
    dest = f"{end_coords['lat']},{end_coords['lon']}"
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin}&destinations={dest}&departure_time=now&key={GMAPS_API_KEY}"

    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            element = res['rows'][0]['elements'][0]
            duration_text = element.get('duration_in_traffic', element.get('duration'))['text']
            duration_mins = int(element.get('duration_in_traffic', element.get('duration'))['value'] / 60)
            return duration_text, duration_mins
    except Exception as e:
        print("Maps API Error:", e)
    return "Unknown", 0

def get_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=precipitation_probability&timezone=auto"
    res = requests.get(url).json()
    curr = res['current_weather']
    temp_f = round((curr['temperature'] * 9/5) + 32, 1)
    desc = get_weather_description(curr['weathercode'])
    precip = res['hourly']['precipitation_probability'][datetime.now().hour]
    return temp_f, desc, precip

def send_gmail(to_email, subject, body):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("Gmail credentials are not set; skipping send")
        return

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = f"Commute Alerts <{GMAIL_USER}>"
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)

def lambda_handler(event, context):
    current_time_str = datetime.now().strftime("%H:%M")
    print(f"Dispatcher running at {current_time_str} ET")

    users = table.scan().get('Items', [])
    dispatched_count = 0

    for user in users:
        if user.get('schedule_time', '07:00') != current_time_str:
            continue

        email = user['user_email']
        start = user['start_city']
        end = user['end_city']

        duration_txt, duration_mins = get_commute_data(user['start_coords'], user['end_coords'])
        temp, condition, precip_chance = get_weather(float(user['start_coords']['lat']), float(user['start_coords']['lon']))

        subject = f"🚗 Commute Update: {duration_txt} to {end}"
        body = f"Good morning!\n\nYour commute from {start} to {end} will take approximately {duration_txt} with current traffic.\n\nCurrent Conditions at departure:\n"
        body += f"🌡️ {temp}°F | {condition}\n"
        body += f"💧 Precipitation Chance: {precip_chance}%\n\n"

        if precip_chance > 30 or "Snow" in condition or "Rain" in condition:
            body += "Advice: Weather conditions are active. Leave a few minutes early and drive safe!"
        elif duration_mins > 45:
            body += "Advice: Traffic is heavier than usual today. Grab a coffee and queue up a good podcast!"
        else:
            body += "Advice: Roads are looking clear and the weather is on your side. Have a great drive!"

        send_gmail(email, subject, body)
        dispatched_count += 1

    return {'statusCode': 200, 'body': f'Sent {dispatched_count} alerts at {current_time_str}.'}
