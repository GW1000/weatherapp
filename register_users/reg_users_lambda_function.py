import json
import boto3
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('CommuteUsers')

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

def respond(status, payload):
    return {
        'statusCode': status,
        'headers': CORS_HEADERS,
        'body': json.dumps(payload)
    }

def parse_body(event):
    body = event
    if isinstance(event, dict) and 'body' in event and event['body'] is not None:
        if isinstance(event['body'], str):
            try:
                body = json.loads(event['body'])
            except Exception:
                body = {}
        else:
            body = event['body']
    return body if isinstance(body, dict) else {}

def geocode_city(city_name):
    clean_city = city_name.split(',')[0].strip()
    encoded_city = urllib.parse.quote(clean_city)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CommuteAlertApp/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            results = data.get('results')
            if results:
                return {
                    'lat': Decimal(str(round(results[0]['latitude'], 4))),
                    'lon': Decimal(str(round(results[0]['longitude'], 4))),
                    'display_name': f"{results[0].get('name')}, {results[0].get('admin1', '')}"
                }
    except Exception as e:
        print(f"Geocoding error for '{city_name}': {str(e)}")
    return None

def public_trip(item):
    return {
        'user_email': item.get('user_email'),
        'start_city': item.get('start_city'),
        'end_city': item.get('end_city'),
        'schedule_time': item.get('schedule_time', '07:00'),
        'created_at': item.get('created_at')
    }

def get_trips(user_email):
    item = table.get_item(Key={'user_email': user_email}).get('Item')
    return [item] if item else []

def lambda_handler(event, context):
    try:
        if isinstance(event, dict) and event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return respond(200, {'ok': True})

        body = parse_body(event)
        action = (body.get('action') or 'register').strip().lower()
        user_email = (body.get('user_email') or '').strip()

        if action == 'list':
            if not user_email:
                return respond(400, {'error': 'Missing required field: user_email'})
            trips = [public_trip(item) for item in get_trips(user_email)]
            return respond(200, {'trips': trips})

        if action == 'unsubscribe':
            if not user_email:
                return respond(400, {'error': 'Missing required field: user_email'})
            if not get_trips(user_email):
                return respond(404, {'error': 'No subscription found for that email.'})
            table.delete_item(Key={'user_email': user_email})
            return respond(200, {'message': 'Unsubscribed successfully.'})

        start_city = body.get('start_city')
        end_city = body.get('end_city')
        schedule_time = body.get('schedule_time', '07:00')

        if not user_email or not start_city or not end_city:
            return respond(400, {'error': 'Missing required fields: user_email, start_city, or end_city'})

        start_coords = geocode_city(start_city)
        end_coords = geocode_city(end_city)

        if not start_coords or not end_coords:
            return respond(400, {'error': 'Could not geocode one or both city locations. Check spelling.'})

        item = {
            'user_email': user_email,
            'start_city': start_city,
            'end_city': end_city,
            'start_coords': start_coords,
            'end_coords': end_coords,
            'schedule_time': schedule_time,
            'created_at': datetime.utcnow().isoformat()
        }

        table.put_item(Item=item)
        return respond(200, {
            'message': 'User registered successfully!',
            'data': public_trip(item)
        })
    except Exception as e:
        print(f"Error executing action: {str(e)}")
        return respond(500, {'error': f"Internal server error: {str(e)}"})