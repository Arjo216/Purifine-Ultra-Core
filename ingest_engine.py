import requests
import psycopg2
import time
import os
from calibration import AerosolPhysicsEngine

# DB Configuration (Matches docker-compose)
DB_CONFIG = {
    "dbname": "purifine_ultra",
    "user": "postgres",
    "password": "purifine_secure_pass",
    "host": "localhost", # Connects to the container
    "port": "5432"
}

API_URL = "https://api.openaq.org/v2/latest"
TARGET_CITIES = ["Delhi", "Mumbai", "Bengaluru", "Kolkata", "Chennai"]

physics = AerosolPhysicsEngine()

def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Waiting for DB... {e}")
        return None

def fetch_and_process():
    print("📡 Contacting Satellites & Ground Stations...")
    all_data = []
    
    for city in TARGET_CITIES:
        params = {
            "limit": 100, "page": 1, "offset": 0, "sort": "desc",
            "city": city, "country": "IN", "order_by": "lastUpdated",
            "dump_raw": "false"
        }
        try:
            response = requests.get(API_URL, params=params)
            if response.status_code == 200:
                data = response.json().get('results', [])
                all_data.extend(data)
                print(f"   -> Fetched {len(data)} nodes for {city}")
        except Exception:
            pass
            
    return all_data

def save_to_db(data):
    conn = connect_db()
    if not conn: return
    cursor = conn.cursor()
    count = 0
    
    for reading in data:
        # Extract basic info
        sensor_id = f"openaq_{reading['locationId']}"
        city = reading['city']
        coords = reading.get('coordinates')
        if not coords: continue
        
        # Register Sensor
        cursor.execute("""
            INSERT INTO sensors (sensor_id, city, location_name, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (sensor_id) DO NOTHING;
        """, (sensor_id, city, reading['location'], coords['latitude'], coords['longitude']))
        
        # Extract measurements
        vals = {m['parameter']: m['value'] for m in reading['measurements']}
        pm25 = vals.get('pm25')
        humidity = vals.get('humidity', 50.0) # Default to 50% if missing
        
        if pm25:
            # --- THE MAGIC: APPLY PHYSICS ---
            env = "coastal" if city in ["Mumbai", "Chennai", "Kolkata"] else "traffic"
            pm25_corrected = physics.correct_pm25(pm25, humidity, env)
            conf_score = physics.get_confidence_score(humidity)
            
            timestamp = reading['measurements'][0]['lastUpdated']
            
            cursor.execute("""
                INSERT INTO measurements (time, sensor_id, pm25_raw, pm25_corrected, humidity, confidence_score)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (timestamp, sensor_id, pm25, pm25_corrected, humidity, conf_score))
            count += 1
            
    conn.commit()
    conn.close()
    print(f"✅ Purifine Ultra Database Updated: {count} new scientific data points.")

if __name__ == "__main__":
    # Wait for DB to start
    time.sleep(5) 
    print("🚀 Purifine Ultra Engine: INITIALIZED")
    while True:
        data = fetch_and_process()
        save_to_db(data)
        print("💤 Sleeping for 15 mins...")
        time.sleep(900)