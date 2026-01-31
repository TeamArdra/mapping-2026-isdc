import cv2
import piexif
import os
import time
import sys
import serial
from datetime import datetime
from fractions import Fraction
from picamera2 import Picamera2 # Native RPi 5 Library

# ================= CONFIGURATION =================
# GPS Settings
SERIAL_PORT = "/dev/ttyAMA0"
BAUD_RATE = 115200          # Foxeer M10Q Default
IMAGE_INTERVAL = 2.0        # Seconds between captures
OUTPUT_FOLDER = "pi5_mapping_images"
DEBUG_MODE = True           # Prints raw GPS sentences to terminal

# CAMERA SETTINGS (Module 3 - IMX708)
WIDTH, HEIGHT = 2304, 1296  # High-res capture size

# --- MAPPING METADATA (SPOOFING) ---
FAKE_MAKE = "Sony"
FAKE_MODEL = "IMX708" 
FOCAL_LENGTH = 4.74   
FOCAL_35MM = 28

# ================= HELPERS =================

def to_deg(value, loc):
    if value < 0: loc_value = loc[1]
    else: loc_value = loc[0]
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min = int(t1)
    sec = round((t1 - min) * 60, 4)
    return (deg, min, sec, loc_value)

def change_to_rational(number):
    f = Fraction(str(abs(number))).limit_denominator(10000)
    return (f.numerator, f.denominator)

def parse_nmea(line):
    """Refined parser for Foxeer M10Q (GNGGA / GPGGA)"""
    try:
        # Check for GGA sentences (most common for positioning/altitude)
        if '$GNGGA' in line or '$GPGGA' in line:
            parts = line.split(',')
            # Verify we have enough data fields and actual coordinates
            if len(parts) > 9 and parts[2] and parts[4]:
                # Latitude conversion
                lat = float(parts[2][:2]) + float(parts[2][2:]) / 60.0
                if parts[3] == 'S': lat = -lat
                # Longitude conversion
                lon = float(parts[4][:3]) + float(parts[4][3:]) / 60.0
                if parts[5] == 'W': lon = -lon
                # Altitude Above Mean Sea Level
                alt = float(parts[9])
                return lat, lon, alt
    except Exception:
        return None
    return None

def inject_metadata(file_name, lat, lng, alt):
    """Inserts GPS coordinates into JPG EXIF headers"""
    try:
        lat_deg = to_deg(lat, ["N", "S"])
        lng_deg = to_deg(lng, ["E", "W"])
        
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: FAKE_MAKE.encode('utf-8'),
                piexif.ImageIFD.Model: FAKE_MODEL.encode('utf-8'),
            },
            "Exif": {
                piexif.ExifIFD.FocalLength: (int(FOCAL_LENGTH * 100), 100),
                piexif.ExifIFD.FocalLengthIn35mmFilm: FOCAL_35MM,
                piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime("%Y:%m:%d %H:%M:%S").encode('utf-8')
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: lat_deg[3].encode('utf-8'),
                piexif.GPSIFD.GPSLatitude: [change_to_rational(lat_deg[0]), change_to_rational(lat_deg[1]), change_to_rational(lat_deg[2])],
                piexif.GPSIFD.GPSLongitudeRef: lng_deg[3].encode('utf-8'),
                piexif.GPSIFD.GPSLongitude: [change_to_rational(lng_deg[0]), change_to_rational(lng_deg[1]), change_to_rational(lng_deg[2])],
                piexif.GPSIFD.GPSAltitudeRef: 0,
                piexif.GPSIFD.GPSAltitude: change_to_rational(alt)
            }
        }
        piexif.insert(piexif.dump(exif_dict), file_name)
    except Exception as e:
        print(f"\n[Metadata Error] {e}")

# ================= MAIN MISSION LOOP =================

def main():
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)

    # 1. Setup GPS Serial
    try:
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.5)
        print(f"GPS: Serial port {SERIAL_PORT} opened at {BAUD_RATE}")
    except Exception as e:
        print(f"GPS Error: {e}")
        return

    # 2. Setup Camera Module 3
    try:
        picam2 = Picamera2()
        # Corrected configuration format for RPi 5 / libcamera
        config = picam2.create_still_configuration(main={"size": (WIDTH, HEIGHT)})
        picam2.configure(config)
        picam2.start()
        print("Camera: RPi Module 3 Online")
    except Exception as e:
        print(f"Camera Error: {e}")
        return

    # Mission State Variables
    last_photo_time = time.time()
    last_serial_check = time.time()
    count = 0
    curr_lat, curr_lon, curr_alt = 0.0, 0.0, 0.0

    print("\n--- STARTING MISSION (Press Ctrl+C to stop) ---")

    try:
        while True:
            # A. Process Serial Data
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('ascii', errors='replace').strip()
                    last_serial_check = time.time() # Reset timeout monitor
                    
                    if DEBUG_MODE:
                        # Print raw data to check if it's empty (,,,,) or valid
                        sys.stdout.write(f"\rRAW GPS: {line[:60]}...")
                        sys.stdout.flush()

                    gps_data = parse_nmea(line)
                    if gps_data:
                        curr_lat, curr_lon, curr_alt = gps_data
                        print(f"\n[LOCK] Lat: {curr_lat:.5f} | Lon: {curr_lon:.5f} | Alt: {curr_alt}m")
                except Exception:
                    pass

            # B. Heartbeat Check
            if time.time() - last_serial_check > 5.0:
                sys.stdout.write(f"\r[WARNING] No data from GPS for 5 seconds! Check wiring.")
                sys.stdout.flush()

            # C. Capture Logic (Only saves if we have a GPS coordinate)
            if (time.time() - last_photo_time) > IMAGE_INTERVAL and curr_lat != 0:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{OUTPUT_FOLDER}/img_{timestamp}_{count}.jpg"
                
                # Capture high-res frame
                picam2.capture_file(filename)
                
                # Inject Coordinates
                inject_metadata(filename, curr_lat, curr_lon, curr_alt)
                
                print(f"\n[Captured] {filename} (Alt: {curr_alt}m)")
                count += 1
                last_photo_time = time.time()

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\nMission Ended by User.")
    finally:
        picam2.stop()
        ser.close()
        print("Hardware safely released.")

if __name__ == "__main__":
    main()