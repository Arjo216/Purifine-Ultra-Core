-- Enable Spatial Features (PostGIS)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Sensor Registry
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id VARCHAR(50) PRIMARY KEY,
    city VARCHAR(100),
    location_name VARCHAR(200),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    source_type VARCHAR(20) DEFAULT 'government'
);

-- 2. Measurements (Hyper-Table)
CREATE TABLE IF NOT EXISTS measurements (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) REFERENCES sensors(sensor_id),
    pm25_raw DOUBLE PRECISION,      -- What the sensor said
    pm25_corrected DOUBLE PRECISION,-- What the physics said (The Truth)
    humidity DOUBLE PRECISION,
    temp_c DOUBLE PRECISION,
    confidence_score VARCHAR(10)    -- 'High', 'Med', 'Low'
);

-- Convert to Time-Series Hypertable
SELECT create_hypertable('measurements', 'time', if_not_exists => TRUE);