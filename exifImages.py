# ==============================================================================
#                                  USER GUIDE
# ==============================================================================
#
# --- STEP 1: TERMINAL SETUP COMMANDS ---
# Open your terminal and run these 4 commands before starting:
#
# 1. Update System:
#    sudo apt update
#
# 2. Install Camera & Python Tools:
#    sudo apt install python3-pip libcamera-apps -y
#
# 3. Install Required Libraries:
#    pip3 install pyserial piexif pynmea2 --break-system-packages
#
# 4. Enable Serial Port (CRITICAL):
#    sudo raspi-config
#    [Interface Options] -> [Serial Port] -> [Login Shell: NO] -> [Hardware: YES]
#    (Then Reboot)
#
#
# --- STEP 2: WHAT YOU NEED TO CHANGE IN THIS CODE ---
#
# 1. SERIAL_PORT (Line 60):
#    - If using USB cable: Change to '/dev/ttyUSB0' or '/dev/ttyACM0'
#    - If using GPIO Pins: Change to '/dev/serial0'
#
# 2. SHUTTER_SPEED (Line 73):
#    - Sunny Day: Keep at 1000
#    - Cloudy/Evening: Change to 4000 or 5000 (prevents dark photos)
#
# 3. OUTPUT_FOLDER (Line 69):
#    - Change this if you want to save to a USB drive (e.g. /media/pi/USB/data)
#
# ==============================================================================

import serial
import pynmea2
import time
import os
import subprocess
import piexif
import threading
from datetime import datetime
from fractions import Fraction

# ================= CONFIGURATION SECTION =================

# --- 1. GPS CONNECTION ---
# CHECK THIS! If plugged via USB, it's usually /dev/ttyUSB0 or /dev/ttyACM0
# If wired to pins 8 & 10, it's /dev/serial0
SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 115200           # Foxeer M10Q default
GPS_TIMEOUT = 1

# --- 2. STORAGE SETTINGS ---
# Folder where images will be saved
OUTPUT_FOLDER = "/home/pi/Downloads/mission_data" 

# --- 3. CAMERA TUNING (RPi Camera V3) ---
INTERVAL = 2.0               # Seconds between photos
SHUTTER_SPEED = 1000         # Microseconds (1000 = 1/1000th sec). Increase if image is dark.

# GLOBAL VARIABLES (Do not touch)
current_lat = 0.0
current_lon = 0.0
current_alt = 0.0
gps_lock = False

# ================= HELPER FUNCTIONS =================

def to_deg(value, loc):
    """Converts decimal degrees to DMS format for EXIF"""
    if value < 0: loc_value = loc[1]
    else: loc_value = loc[0]
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min_val = int(t1)
    sec = round((t1 - min_val) * 60, 4)
    return (deg, min_val, sec, loc_value)

def change_to_rational(number):
    """Converts float to rational fraction for EXIF"""
    value = abs(number)
    if value == 0: return (0, 1)
    f = Fraction(str(value)).limit_denominator(10000)
    return (f.numerator, f.denominator)

def inject_exif(filename, lat, lon, alt):
    """Injects GPS data into the existing JPEG"""
    try:
        exif_dict = piexif.load(filename)
        
        lat_deg = to_deg(lat, ["N", "S"])
        lng_deg = to_deg(lon, ["E", "W"])
        
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: lat_deg[3].encode('utf-8'),
            piexif.GPSIFD.GPSLatitude: [change_to_rational(lat_deg[0]), change_to_rational(lat_deg[1]), change_to_rational(lat_deg[2])],
            piexif.GPSIFD.GPSLongitudeRef: lng_deg[3].encode('utf-8'),
            piexif.GPSIFD.GPSLongitude: [change_to_rational(lng_deg[0]), change_to_rational(lng_deg[1]), change_to_rational(lng_deg[2])],
            piexif.GPSIFD.GPSAltitudeRef: 1 if alt < 0 else 0,
            piexif.GPSIFD.GPSAltitude: change_to_rational(round(alt, 2))
        }
        
        exif_dict["GPS"] = gps_ifd
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, filename)
        
    except Exception as e:
        print(f"EXIF Error: {e}")

# ================= THREAD: GPS READER =================
def read_gps_loop():
    global current_lat, current_lon, current_alt, gps_lock
    print(f"GPS Thread: Connecting to {SERIAL_PORT}...")
    
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=GPS_TIMEOUT) as ser:
            while True:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore')
                    
                    if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                        msg = pynmea2.parse(line)
                        if msg.latitude != 0.0:
                            current_lat = msg.latitude
                            current_lon = msg.longitude
                            current_alt = msg.altitude
                            gps_lock = True
                        else:
                            gps_lock = False
                except pynmea2.ParseError:
                    continue
                except Exception as e:
                    print(f"GPS Read Error: {e}")
                    time.sleep(1)
                    
    except serial.SerialException as e:
        print(f"CRITICAL GPS ERROR: Could not open port {SERIAL_PORT}")
        print(f"Make sure you stopped other services accessing the serial port!")

# ================= MAIN LOOP =================
def main():
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    
    # 1. Start GPS Thread
    gps_thread = threading.Thread(target=read_gps_loop)
    gps_thread.daemon = True 
    gps_thread.start()
    
    print("Waiting for GPS Lock...")
    # NOTE: To test indoors without GPS, comment out the 'while' loop below
    while not gps_lock:
        time.sleep(1)
        print(f"Scanning satellites... (Make sure you are outdoors)")
    
    print("GPS LOCKED. Starting Camera Mission.")
    
    count = 0
    
    try:
        while True:
            start_time = time.time()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{OUTPUT_FOLDER}/img_{timestamp}_{count}.jpg"
            
            # 2. Camera Command for RPi Camera V3 (12MP)
            # If you change cameras, update --width and --height below!
            cmd = [
                "rpicam-still",
                "-o", filename,
                "-t", "100",           # Minimal timeout
                "--nopreview",
                "--shutter", str(SHUTTER_SPEED),
                "--width", "4608",     # V3 Max Width
                "--height", "2592",    # V3 Max Height
                "--autofocus-mode", "manual", # CRITICAL: Disable autofocus
                "--lens-position", "1.0"      # CRITICAL: Lock focus to Infinity
            ]
            
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 3. Stitch GPS Data
            lat_snap = current_lat
            lon_snap = current_lon
            alt_snap = current_alt
            
            if os.path.exists(filename):
                inject_exif(filename, lat_snap, lon_snap, alt_snap)
                print(f"[Saved] {filename} | GPS: {lat_snap:.5f}, {lon_snap:.5f}, {alt_snap:.1f}m")
                count += 1
            else:
                print("Error: Camera failed to save image.")
            
            elapsed = time.time() - start_time
            sleep_time = max(0, INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nMission Stopped.")

if __name__ == "__main__":
    main()