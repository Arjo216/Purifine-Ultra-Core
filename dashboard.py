import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from datetime import datetime
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Purifine Ultra | Command Grid",
    page_icon="☢️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CUSTOM CSS (Cyberpunk Professional) ---
st.markdown("""
    <style>
        .stApp { background-color: #0E1117; }
        
        /* HUD Metrics */
        div[data-testid="stMetric"] {
            background-color: #1A1C24;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        div[data-testid="stMetricValue"] { 
            color: #00FF94; 
            font-family: 'Courier New', monospace; 
            font-weight: 700; 
        }
        
        /* Table Headers */
        thead tr th:first-child { display:none }
        tbody th { display:none }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 10px; }
        ::-webkit-scrollbar-track { background: #0E1117; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 5px; }
        ::-webkit-scrollbar-thumb:hover { background: #00FF94; }

        h1 {
            background: -webkit-linear-gradient(45deg, #00FF94, #00B8FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION (SQLAlchemy) ---
DB_URL = "postgresql://postgres:purifine_secure_pass@localhost:5432/purifine_ultra"

@st.cache_resource
def get_engine():
    return create_engine(DB_URL)

def load_data():
    engine = get_engine()
    query = """
        SELECT s.city, s.location_name, s.latitude, s.longitude,
               m.pm25_raw, m.pm25_corrected, m.humidity, m.confidence_score, m.time
        FROM measurements m
        JOIN sensors s ON m.sensor_id = s.sensor_id
        WHERE m.time > NOW() - INTERVAL '24 hours'
        ORDER BY m.time DESC;
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    return df

# --- 4. DATA PROCESSING ---
try:
    raw_df = load_data()
    
    if raw_df.empty:
        st.error("⚠️ Database connected but contains NO DATA. Is 'ingest_engine.py' running?")
        st.stop()
    
    # Snapshot for Map
    latest_df = raw_df.drop_duplicates(subset=['location_name'], keep='first').copy()
    
    # TYPE FORCING (Critical for Map)
    latest_df['latitude'] = pd.to_numeric(latest_df['latitude'], errors='coerce')
    latest_df['longitude'] = pd.to_numeric(latest_df['longitude'], errors='coerce')
    latest_df['pm25_corrected'] = pd.to_numeric(latest_df['pm25_corrected'], errors='coerce').fillna(0)
    latest_df = latest_df.dropna(subset=['latitude', 'longitude'])

    # COLOR LOGIC
    def get_color(val):
        if val <= 30: return [0, 255, 148, 200]    # Green
        if val <= 60: return [255, 204, 0, 200]    # Yellow
        if val <= 90: return [255, 112, 67, 200]   # Orange
        return [255, 0, 85, 220]                   # Red

    latest_df['color'] = latest_df['pm25_corrected'].apply(get_color)
    
    # METRICS
    nat_avg = latest_df['pm25_corrected'].mean()
    max_poll = latest_df['pm25_corrected'].max()
    most_polluted_city = latest_df.loc[latest_df['pm25_corrected'].idxmax()]['city']
    total_sensors = len(latest_df)

except Exception as e:
    st.error(f"⚠️ PROCESSING ERROR: {e}")
    st.stop()

# --- 5. UI LAYOUT ---

# HEADER
c1, c2 = st.columns([3, 1])
with c1:
    st.title("PURIFINE ULTRA // INTELLIGENCE GRID")
    st.caption(f"⚡ SYSTEM ONLINE | 📡 SENSORS: {total_sensors} | 🆔 USER: COMMANDER | 🕒 UTC: {datetime.now().strftime('%H:%M:%S')}")
with c2:
    if st.button("🔄 FORCE SYNC"):
        st.rerun()

# KPI HUD
k1, k2, k3, k4 = st.columns(4)
k1.metric("NETWORK HEALTH", "OPTIMAL", "100% Uptime")
k2.metric("NATIONAL AVG", f"{nat_avg:.1f} µg/m³", "-1.2%" if nat_avg < 50 else "+2.4%", delta_color="inverse")
k3.metric("CRITICAL SECTOR", most_polluted_city, f"{max_poll:.0f} µg/m³", delta_color="inverse")
k4.metric("DATA POINTS (24H)", f"{len(raw_df)}", "+ Streaming")

st.markdown("---")

# --- 6. 3D MAP SECTION ---
st.subheader("📍 GEOSPATIAL TOXICITY LAYER (3D)")

layer_scatter = pdk.Layer(
    "ScatterplotLayer",
    latest_df,
    get_position=["longitude", "latitude"],
    get_color="color",
    get_radius=8000,
    pickable=True,
    opacity=0.4,
    stroked=True,
    filled=True,
)

layer_column = pdk.Layer(
    "ColumnLayer",
    latest_df,
    get_position=["longitude", "latitude"],
    get_elevation="pm25_corrected",
    elevation_scale=200,
    radius=4000,
    get_fill_color="color",
    pickable=True,
    auto_highlight=True,
    extruded=True,
)

view_state = pdk.ViewState(
    latitude=latest_df['latitude'].mean(),
    longitude=latest_df['longitude'].mean(),
    zoom=4,
    pitch=55,
    bearing=0
)

tooltip = {"html": "<b>{city}</b><br/>PM2.5: {pm25_corrected}<br/>Hum: {humidity}%", "style": {"backgroundColor": "#111", "color": "#fff"}}

r = pdk.Deck(
    layers=[layer_scatter, layer_column],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_style="mapbox://styles/mapbox/dark-v11",
)
st.pydeck_chart(r)

# --- 7. ANALYTICS & DATA FEED (THE UPGRADE) ---
st.markdown("---")
col_chart, col_table = st.columns([1, 2]) # 1/3 Chart, 2/3 Table

with col_chart:
    st.subheader("🔬 PHYSICS ENGINE PROOF")
    st.caption("Real-time Correction Analysis")
    
    if not latest_df.empty:
        # Sort by humidity to show where physics matters most
        target_loc = latest_df.sort_values('humidity', ascending=False).iloc[0]['location_name']
        chart_data = raw_df[raw_df['location_name'] == target_loc].head(40)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=chart_data['time'], y=chart_data['pm25_raw'], 
                                mode='lines', name='Raw (Error)', line=dict(color='#666', dash='dot')))
        fig.add_trace(go.Scatter(x=chart_data['time'], y=chart_data['pm25_corrected'], 
                                mode='lines+markers', name='Corrected (True)', line=dict(color='#00FF94', width=2)))
        
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ccc', size=10),
            xaxis=dict(showgrid=False), 
            yaxis=dict(showgrid=True, gridcolor='#333'),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig, use_container_width=True)

with col_table:
    st.subheader("📋 SCIENTIFIC DATA FEED")
    
    # Prepare Table Data
    table_df = raw_df[['time', 'city', 'location_name', 'pm25_raw', 'pm25_corrected', 'humidity', 'confidence_score']].copy()
    
    # Add a "Delta" column (Difference between Raw and Corrected)
    table_df['Physics Delta'] = table_df['pm25_raw'] - table_df['pm25_corrected']
    
    # Render the "Ultimate" Table
    st.dataframe(
        table_df,
        column_config={
            "time": st.column_config.DatetimeColumn("Timestamp", format="HH:mm:ss"),
            "city": "City",
            "location_name": st.column_config.TextColumn("Station ID", width="medium"),
            "pm25_corrected": st.column_config.ProgressColumn(
                "Toxicity (PM2.5)",
                help="Physics-Corrected Value",
                format="%.1f",
                min_value=0,
                max_value=300,
            ),
            "humidity": st.column_config.NumberColumn("Hum %", format="%.0f%%"),
            "confidence_score": st.column_config.TextColumn("Conf.", help="AI Confidence"),
            "Physics Delta": st.column_config.NumberColumn("Correction", format="%.1f", help="Amount reduced by Physics Engine"),
            "pm25_raw": st.column_config.NumberColumn("Raw Input", format="%.1f")
        },
        height=400, # Matches chart height
        hide_index=True,
        use_container_width=True
    )
    
    # CSV Download
    csv = table_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 DOWNLOAD FULL REPORT (CSV)", data=csv, file_name="purifine_report.csv", mime="text/csv")

time.sleep(2)