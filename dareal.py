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
GPS_PORT = '/dev/ttyAMA0'
GPS_BAUD = 115200 

# UDP Configuration
DEST_IP = "192.168.1.50"  # Replace with your Ground Station IP
DEST_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

SAVE_PATH = '/home/ardra/Downloads/telemetry_log.csv'

# --- INITIALIZATION ---
i2c = board.I2C()
bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
gps_ser = serial.Serial(GPS_PORT, baudrate=GPS_BAUD, timeout=1)

if not os.path.exists(SAVE_PATH):
    with open(SAVE_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Altitude_m"])

def get_data():
    alt = round(bmp.altitude, 2)
    line = gps_ser.readline().decode('ascii', errors='replace').strip()
    lat, lon = 0.0, 0.0 # Using floats for binary packing
    
    if '$G' in line and 'RMC' in line:
        try:
            msg = pynmea2.parse(line)
            if msg.latitude and msg.longitude:
                lat, lon = float(msg.latitude), float(msg.longitude)
        except:
            pass
            
    timestamp = time.time() # Using Unix timestamp for easier processing
    return [timestamp, lat, lon, alt]

try:
    with open(SAVE_PATH, 'a', newline='') as csv_file:
        logger = csv.writer(csv_file)
        
        while True:
            data = get_data() # [ts, lat, lon, alt]
            
            # 1. Save Locally (CSV for humans)
            logger.writerow(data)
            csv_file.flush()
            
            # 2. UDP Binary Packing (Columns/Fields)
            # Format: 'd' = double (8 bytes), 'f' = float (4 bytes)
            # Payload: [Timestamp(d), Lat(f), Lon(f), Alt(f)]
            packet = struct.pack('!dfff', data[0], data[1], data[2], data[3])
            
            # 3. Send via UDP
            sock.sendto(packet, (DEST_IP, DEST_PORT))
            
            print(f"Sent UDP Packet: Lat:{data[1]}, Lon:{data[2]}, Alt:{data[3]}")
            time.sleep(0.1) 

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    gps_ser.close()
    sock.close()