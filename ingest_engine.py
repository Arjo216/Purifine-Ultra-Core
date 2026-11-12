import os
import requests
import psycopg2
import time
from dotenv import load_dotenv
from datetime import datetime
from calibration import AerosolPhysicsEngine

# --- SECURE CONFIGURATION ---
load_dotenv()

DB_CONFIG = {
    "dbname": "purifine_ultra",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "purifine_secure_pass"),
    "host": "localhost",
    "port": "5432"
}

OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")
physics = AerosolPhysicsEngine()

# THE UPGRADE: Hardcoding the Grid so we never lose a city's location even if sensors die
CITY_MAP = {
    8118: ("Delhi", 28.63, 77.22),
    8039: ("Mumbai", 19.07, 72.87),
    8172: ("Kolkata", 22.57, 88.36),
    8476: ("Chennai", 13.08, 80.27),
    8556: ("Hyderabad", 17.38, 78.48),
    5607: ("Bengaluru", 12.97, 77.59),
    8045: ("Pune", 18.52, 73.85),
    8234: ("Ahmedabad", 23.02, 72.57),
    8612: ("Lucknow", 26.84, 80.94),
    8910: ("Jaipur", 26.91, 75.78),
    8228: ("Gurgaon", 28.45, 77.02),
    8229: ("Noida", 28.53, 77.39)
}

def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return None

def get_live_humidity(lat, lon):
    """Fetches real-time humidity with built-in retry logic and anti-throttling."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=relative_humidity_2m"
    
    for attempt in range(2): # Will try twice before giving up
        try:
            res = requests.get(url, timeout=10) # Increased timeout to 10s
            if res.status_code == 200:
                time.sleep(1.5) # Strict 1.5s pause to prevent IP ban
                return res.json()['current']['relative_humidity_2m']
        except Exception as e:
            time.sleep(2) # If it fails, wait 2 seconds and retry
            
    return 50.0 # Ultimate safe fallback

def fetch_live_data():
    print("📡 Contacting Satellites (Resilient Omni-Sync)...")
    headers = {"X-API-Key": OPENAQ_API_KEY}
    all_data = []

    for loc_id, (city, lat, lon) in CITY_MAP.items():
        pm25_val = 0.0 # Default to 0 if offline
        
        # 1. Fetch PM2.5 Data
        url = f"https://api.openaq.org/v3/locations/{loc_id}/latest?parameterName=pm25"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                for item in results:
                    if item.get('value', -999) > 0:
                        pm25_val = item['value']
                        break
        except Exception:
            pass # We silently ignore PM2.5 errors now to ensure weather still runs

        if pm25_val > 0:
            print(f"   -> Locked PM2.5 signal {loc_id} ({city}) | {pm25_val} µg/m³")
        else:
            print(f"   -> ⚠️ Sensor Offline {loc_id} ({city}) | PM2.5 defaulting to 0.0")

        # 2. Fetch Weather Data (Runs even if PM2.5 failed)
        humidity_val = get_live_humidity(lat, lon)
        print(f"      -> Weather Sync: {city} Humidity is {humidity_val}%")

        all_data.append({
            '_source_loc_id': loc_id,
            'city': city,
            'lat': lat,
            'lon': lon,
            'value': pm25_val,
            'humidity_real': humidity_val
        })
            
    return all_data

def save_to_db(data):
    conn = connect_db()
    if not conn: return
    cursor = conn.cursor()
    count = 0
    
    for reading in data:
        loc_id = reading['_source_loc_id']
        sensor_id = f"openaq_v3_{loc_id}"
        city = reading['city']
        lat = reading['lat']
        lon = reading['lon']
        pm25 = reading['value']
        humidity = reading['humidity_real']

        env_type = "coastal" if city in ["Mumbai", "Kolkata", "Chennai"] else "traffic"
        
        # Apply physics only if we have real PM2.5 data
        if pm25 > 0:
            pm25_corrected = physics.correct_pm25(pm25, humidity, env_type)
        else:
            pm25_corrected = 0.0
            
        conf_score = physics.get_confidence_score(humidity)
        
        cursor.execute("""
            INSERT INTO sensors (sensor_id, city, location_name, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (sensor_id) DO NOTHING;
        """, (sensor_id, city, f"Station {sensor_id}", lat, lon))
        
        cursor.execute("""
            INSERT INTO measurements (time, sensor_id, pm25_raw, pm25_corrected, humidity, confidence_score)
            VALUES (NOW(), %s, %s, %s, %s, %s);
        """, (sensor_id, pm25, pm25_corrected, humidity, conf_score))
        count += 1
            
    conn.commit()
    conn.close()
    print(f"✅ Purifine Ultra Database Updated: {count} highly resilient data points.")

if __name__ == "__main__":
    print("🚀 Purifine Ultra Engine V7.0 (Resilient Omni-Sync): INITIALIZED")
    while True:
        data = fetch_live_data()
        save_to_db(data)
        print("💤 Sleeping for 60 seconds...")
        time.sleep(60)