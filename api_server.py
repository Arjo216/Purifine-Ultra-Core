from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import psycopg2
from typing import List, Optional
from datetime import datetime

# --- APP INITIALIZATION ---
app = FastAPI(
    title="Purifine Ultra Intelligence Grid",
    description="Real-time, Physics-Corrected Air Quality Data for India",
    version="3.5"
)

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "purifine_ultra",
    "user": "postgres",
    "password": "purifine_secure_pass",
    "host": "localhost",
    "port": "5432"
}

# --- DATA MODELS (The Contract) ---
class PollutionData(BaseModel):
    sensor_id: str
    city: str
    location: str
    timestamp: datetime
    pm25_raw: float
    pm25_corrected: float
    humidity: float
    confidence: str

class HealthStatus(BaseModel):
    status: str
    active_sensors: int
    db_latency_ms: float

# --- HELPER FUNCTIONS ---
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ DB Conn Failed: {e}")
        return None

# --- ENDPOINTS ---

@app.get("/", tags=["System"])
def home():
    return {"system": "Purifine Ultra", "status": "ONLINE", "version": "3.5"}

@app.get("/v1/live/map", response_model=List[PollutionData], tags=["Public Data"])
def get_live_map(city: Optional[str] = None):
    """
    Returns the LATEST reading for every active sensor.
    Optional: Filter by 'city' (e.g., ?city=Delhi)
    """
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Database Offline")
    
    cursor = conn.cursor()
    
    # SQL Magic: Get the most recent row for each unique sensor
    query = """
        SELECT DISTINCT ON (s.sensor_id)
            s.sensor_id, s.city, s.location_name, 
            m.time, m.pm25_raw, m.pm25_corrected, m.humidity, m.confidence_score
        FROM sensors s
        JOIN measurements m ON s.sensor_id = m.sensor_id
    """
    
    if city:
        query += " WHERE s.city = %s"
        params = (city,)
    else:
        params = ()
        
    query += " ORDER BY s.sensor_id, m.time DESC;"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "sensor_id": row[0],
            "city": row[1],
            "location": row[2],
            "timestamp": row[3],
            "pm25_raw": row[4],
            "pm25_corrected": row[5],
            "humidity": row[6],
            "confidence": row[7]
        })
        
    return results

@app.get("/v1/analytics/city-ranking", tags=["Analytics"])
def get_city_rankings():
    """
    Ranks cities from Most Polluted to Least Polluted based on current average.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Analytics Query: Average of last 1 hour per city
    cursor.execute("""
        SELECT s.city, AVG(m.pm25_corrected) as avg_pm25
        FROM measurements m
        JOIN sensors s ON m.sensor_id = s.sensor_id
        WHERE m.time > NOW() - INTERVAL '24 hours'
        GROUP BY s.city
        ORDER BY avg_pm25 DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    
    ranking = []
    for rank, row in enumerate(rows, 1):
        ranking.append({
            "rank": rank,
            "city": row[0],
            "average_pm25": round(row[1], 2),
            "status": "Hazardous" if row[1] > 100 else "Poor" if row[1] > 50 else "Good"
        })
        
    return ranking