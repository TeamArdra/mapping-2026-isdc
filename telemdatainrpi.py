import serial
import pynmea2
import csv
import time
import os
import board
import adafruit_bmp280

# --- CONFIGURATION ---
# Foxeer M10Q 250 default baud rate is 115200
GPS_PORT = '/dev/ttyAMA0'
GPS_BAUD = 115200 

# Telemetry LR900 (MicoAir) 
TELEM_PORT = '/dev/ttyAMA2'
TELEM_BAUD = 57600

# File path
SAVE_PATH = '/home/ardra/Downloads/telemetry_log.csv'

# --- INITIALIZATION ---
i2c = board.I2C() # Uses GPIO 2 and 3
bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)

gps_ser = serial.Serial(GPS_PORT, baudrate=GPS_BAUD, timeout=1)
telem_ser = serial.Serial(TELEM_PORT, baudrate=TELEM_BAUD, timeout=1)

# Create CSV header if file doesn't exist
if not os.path.exists(SAVE_PATH):
    with open(SAVE_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Altitude_m"])

print(f"System Ready. Logging to {SAVE_PATH} and streaming to Telemetry...")

def get_data():
    # 1. Get Altitude
    alt = round(bmp.altitude, 2)
    
    # 2. Get GPS
    # M10Q outputs at 10Hz; we read the most recent line
    line = gps_ser.readline().decode('ascii', errors='replace').strip()
    lat, lon = "0.0", "0.0"
    
    if '$G' in line and 'RMC' in line:
        try:
            msg = pynmea2.parse(line)
            if msg.latitude and msg.longitude:
                lat, lon = round(msg.latitude, 6), round(msg.longitude, 6)
        except:
            pass
            
    timestamp = time.strftime('%H:%M:%S')
    return [timestamp, lat, lon, alt]

try:
    with open(SAVE_PATH, 'a', newline='') as csv_file:
        logger = csv.writer(csv_file)
        
        while True:
            # Collect
            data_row = get_data()
            
            # Save Locally
            logger.writerow(data_row)
            csv_file.flush() # Ensure it writes to disk immediately
            
            # Send to Telemetry (CSV Format)
            csv_string = ",".join(map(str, data_row)) + "\n"
            telem_ser.write(csv_string.encode('utf-8'))
            
            # Debug Print
            print(f"Logged & Sent: {csv_string.strip()}")
            
            # Foxeer M10Q 10Hz sync
            time.sleep(0.1) 

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    gps_ser.close()
    telem_ser.close()