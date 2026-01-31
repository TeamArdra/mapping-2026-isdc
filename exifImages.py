import serial
import pynmea2
import time
import os
import subprocess
import piexif
import threading
from datetime import datetime
from fractions import Fraction

# ================= CONFIGURATION =================
# GPS SETTINGS
SERIAL_PORT = '/dev/ttyUSB0' # CHECK THIS: likely /dev/ttyUSB0 or /dev/serial0
BAUD_RATE = 115200           # Foxeer M10Q usually defaults to 115200
GPS_TIMEOUT = 1

# CAMERA SETTINGS
OUTPUT_FOLDER = "/home/pi/mission_data"
INTERVAL = 2.0               # Seconds between photos
SHUTTER_SPEED = 1000         # Microseconds (1000 = 1/1000th sec to reduce blur)

# GLOBAL VARIABLES (Shared between threads)
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
                    
                    # We look for $GNGGA (Global Navigation GNSS System Fix Data)
                    # This contains Lat, Lon, and Altitude
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
    gps_thread.daemon = True # Kills thread when main program exits
    gps_thread.start()
    
    print("Waiting for GPS Lock...")
    # Optional: Wait for lock before starting. Remove loop if you want to force start.
    while not gps_lock:
        time.sleep(1)
        print("Scanning satellites...")
    
    print("GPS LOCKED. Starting Camera Mission.")
    
    count = 0
    
    try:
        while True:
            start_time = time.time()
            
            # 2. Capture Photo using Libcamera
            # We use rpicam-still (formerly libcamera-still)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{OUTPUT_FOLDER}/img_{timestamp}_{count}.jpg"
            
            # -t 1: minimal timeout
            # --nopreview: save CPU
            # --shutter: fixed shutter speed prevents motion blur on drones
            cmd = [
                "rpicam-still",
                "-o", filename,
                "-t", "100", 
                "--nopreview",
                "--shutter", str(SHUTTER_SPEED),
                "--width", "4608", # Set to your camera max resolution
                "--height", "2592"
            ]
            
            # Execute camera command
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 3. Stitch GPS Data
            # We grab the variables RIGHT NOW to minimize sync error
            lat_snap = current_lat
            lon_snap = current_lon
            alt_snap = current_alt
            
            if os.path.exists(filename):
                inject_exif(filename, lat_snap, lon_snap, alt_snap)
                print(f"[Saved] {filename} | GPS: {lat_snap:.5f}, {lon_snap:.5f}, {alt_snap:.1f}m")
                count += 1
            else:
                print("Error: Camera failed to save image.")
            
            # 4. Wait for next interval
            elapsed = time.time() - start_time
            sleep_time = max(0, INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nMission Stopped.")

if __name__ == "__main__":
    main()