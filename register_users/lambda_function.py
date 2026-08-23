import json
import boto3
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('CommuteUsers')

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

def lambda_handler(event, context):
    # Extract JSON payload
    body = event
    if isinstance(event, dict) and 'body' in event and event['body'] is not None:
        if isinstance(event['body'], str):
            try:
                body = json.loads(event['body'])
            except Exception:
                body = {}
        else:
            body = event['body']

    user_email = body.get('user_email')
    start_city = body.get('start_city')
    end_city = body.get('end_city')
    schedule_time = body.get('schedule_time', '07:00')

    if not user_email or not start_city or not end_city:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing required fields: user_email, start_city, or end_city'})
        }

    # Geocode locations
    start_coords = geocode_city(start_city)
    end_coords = geocode_city(end_city)

    if not start_coords or not end_coords:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Could not geocode one or both city locations. Check spelling.'})
        }

    # Save to DynamoDB
    item = {
        'user_email': user_email,
        'start_city': start_city,
        'end_city': end_city,
        'start_coords': start_coords,
        'end_coords': end_coords,
        'schedule_time': schedule_time,
        'created_at': datetime.utcnow().isoformat()
    }

    try:
        table.put_item(Item=item)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'User registered successfully!',
                'data': {
                    'user_email': user_email,
                    'start_city': start_city,
                    'end_city': end_city,
                    'schedule_time': schedule_time
                }
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Failed to save to database: {str(e)}"})
        }