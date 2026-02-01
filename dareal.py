import serial
import pynmea2
import csv
import time
import os
import board
import adafruit_bmp280
import socket
import struct

# --- CONFIGURATION ---
# GPS (Standard UART)
GPS_PORT = '/dev/ttyAMA0'
GPS_BAUD = 115200 

# Telemetry Radio (Confirmed on GPIO 4/5 -> UART2)
TELEM_PORT = '/dev/ttyAMA2'
TELEM_BAUD = 115200

# UDP Configuration (Network Stream)
DEST_IP = "192.168.1.50"  # <--- REPLACE with your Laptop's IP
DEST_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Log File
SAVE_PATH = '/home/ardra/Downloads/telemetry_log.csv'

# --- INITIALIZATION ---
print("Initializing Sensors...")

# 1. Setup I2C & BMP280
i2c = board.I2C()
bmp = None
try:
    # Try 0x76 first as per your previous check
    bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)
    print("BMP280 (Altitude): OK")
except Exception as e:
    print(f"BMP280 Error: {e}")
    print("Trying default address 0x77...")
    try:
        bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x77)
        print("BMP280 (Altitude): OK (at 0x77)")
    except:
        print("BMP280 Not Found. Altitude will be 0.0")

# 2. Setup GPS Serial
gps_ser = None
try:
    gps_ser = serial.Serial(GPS_PORT, baudrate=GPS_BAUD, timeout=1)
    print(f"GPS Port ({GPS_PORT}): OK")
except Exception as e:
    print(f"GPS Error: {e}")

# 3. Setup Telemetry Serial
telem_ser = None
try:
    telem_ser = serial.Serial(TELEM_PORT, baudrate=TELEM_BAUD, timeout=0)
    print(f"Telemetry Radio ({TELEM_PORT}): OK")
except Exception as e:
    print(f"Telemetry Error: {e}")

# 4. Create CSV File
if not os.path.exists(SAVE_PATH):
    with open(SAVE_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Unix_Timestamp", "Latitude", "Longitude", "Altitude_m"])

print(f"\n--- SYSTEM READY ---")
print(f"Logging to: {SAVE_PATH}")
print(f"UDP Stream: {DEST_IP}:{DEST_PORT}")
print(f"Radio Stream: {TELEM_PORT} (Binary)")

# --- MAIN LOOP ---
def get_gps_coord(serial_obj):
    lat, lon = 0.0, 0.0
    if serial_obj and serial_obj.in_waiting:
        try:
            # Read a batch of lines to clear buffer and get latest
            lines = serial_obj.read(serial_obj.in_waiting).decode('ascii', errors='ignore').split('\n')
            for line in lines[-5:]: # Check last few lines
                if '$G' in line and 'RMC' in line:
                    msg = pynmea2.parse(line.strip())
                    if msg.latitude and msg.longitude:
                        lat = float(msg.latitude)
                        lon = float(msg.longitude)
                        break # Found valid data
        except:
            pass
    return lat, lon

try:
    with open(SAVE_PATH, 'a', newline='') as csv_file:
        logger = csv.writer(csv_file)
        
        while True:
            # A. Collect Data
            ts = time.time()
            
            # Altitude
            alt = round(bmp.altitude, 2) if bmp else 0.0
            
            # GPS
            lat, lon = get_gps_coord(gps_ser)
            
            data_row = [ts, lat, lon, alt]
            
            # B. Save Locally (CSV)
            logger.writerow(data_row)
            csv_file.flush()
            
            # C. Pack Binary Data
            # Structure: [Timestamp(double 8b), Lat(float 4b), Lon(float 4b), Alt(float 4b)]
            # Total Packet Size = 20 Bytes
            packet = struct.pack('!dfff', ts, lat, lon, alt)
            
            # D. Send via UDP (WiFi)
            try:
                sock.sendto(packet, (DEST_IP, DEST_PORT))
            except:
                pass 
            
            # E. Send via Telemetry Radio (LR900)
            if telem_ser:
                telem_ser.write(packet)
            
            # Debug Print (Optional)
            print(f"T:{ts:.1f} | Lat:{lat:.5f} Lon:{lon:.5f} | Alt:{alt}m | Sent 20B")
            
            # 10Hz Update Rate
            time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    if gps_ser: gps_ser.close()
    if telem_ser: telem_ser.close()
    sock.close()