import requests
import psycopg2
import time
import random
from datetime import datetime
from calibration import AerosolPhysicsEngine

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "purifine_ultra",
    "user": "postgres",
    "password": "purifine_secure_pass",
    "host": "localhost",
    "port": "5432"
}

# 🔑 PASTE YOUR API KEY HERE
OPENAQ_API_KEY = "8a8d0cf35746cbfe535dfa7ed082026694f3873d833933b61b122f1d09167bee" 

physics = AerosolPhysicsEngine()

# TARGET LOCATIONS (Major Indian US Consulates)
TARGET_LOCATIONS = [8118, 8039, 8172, 8476, 8556]

def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return None

def fetch_live_data():
    """
    Fetches ONLY PM2.5 data using server-side filtering.
    URL Pattern: /locations/{id}/latest?parameterName=pm25
    """
    if not OPENAQ_API_KEY or OPENAQ_API_KEY == "YOUR_API_KEY_HERE":
        print("⚠️ No API Key found. Switching to SIMULATION MODE.")
        return generate_mock_data()

    print("📡 Contacting OpenAQ V3 Satellite Uplink...")
    headers = {"X-API-Key": OPENAQ_API_KEY}
    all_data = []

    for loc_id in TARGET_LOCATIONS:
        # THE FIX: Force API to send only PM2.5 data
        url = f"https://api.openaq.org/v3/locations/{loc_id}/latest?parameterName=pm25"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                
                # Tag metadata and filter invalid readings immediately
                valid_items = []
                for item in results:
                    item['_source_loc_id'] = loc_id
                    # OpenAQ sends -999 for errors. Filter these out.
                    if item.get('value', -999) > 0: 
                        valid_items.append(item)
                        
                all_data.extend(valid_items)
                print(f"   -> Locked on signal: Location {loc_id} ({len(valid_items)} PM2.5 readings)")
            else:
                print(f"   -> Failed {loc_id}: Status {response.status_code}")
        except Exception as e:
            print(f"   -> Connection failed: {e}")
            
    return all_data

def generate_mock_data():
    """Generates realistic test data"""
    print("🔮 GENERATING HYPER-REALISTIC SIMULATION DATA...")
    mock_data = []
    cities = [("Delhi", 28.61, 77.20), ("Mumbai", 19.07, 72.87), ("Kolkata", 22.57, 88.36)]
    
    for city, lat, lon in cities:
        mock_data.append({
            "is_mock": True,
            "city_name": city,
            "id": random.randint(1000,9999),
            "value": random.uniform(20, 180),
            "humidity_sim": random.uniform(40, 90)
        })
    return mock_data

def save_to_db(data):
    conn = connect_db()
    if not conn: return
    cursor = conn.cursor()
    count = 0
    
    for reading in data:
        sensor_id = ""
        city = "India-Metro"
        lat = 0.0
        lon = 0.0
        pm25 = None
        humidity = 50.0 

        # --- PATH A: SIMULATION ---
        if reading.get("is_mock"):
            sensor_id = f"sim_{reading['id']}"
            pm25 = reading['value']
            lat = 28.6
            lon = 77.2
            humidity = reading['humidity_sim']

        # --- PATH B: REAL API DATA (SIMPLIFIED) ---
        else:
            # We trust it is PM2.5 because we asked for it in the URL.
            pm25 = reading.get('value')
            
            # Double check for valid number
            if pm25 is None or pm25 <= 0: continue

            loc_id = reading.get('_source_loc_id')
            sensor_id = f"openaq_v3_{loc_id}"
            
            # Extract Coordinates directly from top-level
            coords = reading.get('coordinates', {})
            lat = coords.get('latitude', 0.0)
            lon = coords.get('longitude', 0.0)

            # Map IDs to City Names for display
            if loc_id == 8118: city = "Delhi"
            elif loc_id == 8039: city = "Mumbai"
            elif loc_id == 8172: city = "Kolkata"
            elif loc_id == 8476: city = "Chennai"
            elif loc_id == 8556: city = "Hyderabad"
            
            # If coordinates are missing (sometimes happens), fill them from known map
            if lat == 0.0:
                if city == "Delhi": lat, lon = 28.63, 77.22
                elif city == "Mumbai": lat, lon = 19.07, 72.87

        # --- PHYSICS & SAVE ---
        env_type = "coastal" if city in ["Mumbai", "Kolkata", "Chennai"] else "traffic"
        pm25_corrected = physics.correct_pm25(pm25, humidity, env_type)
        conf_score = physics.get_confidence_score(humidity)
        
        # Upsert Sensor
        cursor.execute("""
            INSERT INTO sensors (sensor_id, city, location_name, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (sensor_id) DO NOTHING;
        """, (sensor_id, city, f"Station {sensor_id}", lat, lon))
        
        # Insert Measurement
        cursor.execute("""
            INSERT INTO measurements (time, sensor_id, pm25_raw, pm25_corrected, humidity, confidence_score)
            VALUES (NOW(), %s, %s, %s, %s, %s);
        """, (sensor_id, pm25, pm25_corrected, humidity, conf_score))
        count += 1
            
    conn.commit()
    conn.close()
    print(f"✅ Purifine Ultra Database Updated: {count} new scientific data points.")

if __name__ == "__main__":
    print("🚀 Purifine Ultra Engine V3.4 (Filtered): INITIALIZED")
    while True:
        data = fetch_live_data()
        save_to_db(data)
        print("💤 Sleeping for 60 seconds...")
        time.sleep(60)