import cv2
import piexif
import os
import time
import sys
import serial
from datetime import datetime
from fractions import Fraction
from picamera2 import Picamera2 # Specific for RPi 5 / Camera Module 3

# ================= CONFIGURATION =================
# GPS Settings
SERIAL_PORT = "/dev/ttyAMA0"
BAUD_RATE = 115200  # Foxeer M10Q default
IMAGE_INTERVAL = 2.0
OUTPUT_FOLDER = "pi5_mapping_images"

# CAMERA SETTINGS (Module 3)
WIDTH, HEIGHT = 2304, 1296 # 1080p-ish (Module 3 supports up to 4608x2592)

# --- PIX4D/MAPPING SPOOFING ---
FAKE_MAKE = "Sony"
FAKE_MODEL = "IMX708" # The sensor in RPi Cam 3
FOCAL_LENGTH = 4.74   # Actual for RPi Cam 3
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
    """Simple parser for GNGGA sentences from Foxeer M10Q"""
    if line.startswith('$GNGGA'):
        parts = line.split(',')
        try:
            if parts[2] and parts[4]:
                # Latitude
                lat = float(parts[2][:2]) + float(parts[2][2:]) / 60.0
                if parts[3] == 'S': lat = -lat
                # Longitude
                lon = float(parts[4][:3]) + float(parts[4][3:]) / 60.0
                if parts[5] == 'W': lon = -lon
                # Altitude
                alt = float(parts[9])
                return lat, lon, alt
        except (ValueError, IndexError):
            return None
    return None

def inject_metadata(file_name, lat, lng, alt):
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
        print(f"Metadata Error: {e}")

# ================= MAIN LOOP =================

def main():
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)

    # 1. Setup GPS
    try:
        ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)
        print(f"GPS: Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"GPS Error: {e}")
        return

    # 2. Setup Camera Module 3
    picam2 = Picamera2()
    config = picam2.create_still_configuration(main_size=(WIDTH, HEIGHT))
    picam2.configure(config)
    picam2.start()
    print("Camera: RPi Module 3 Online")

    # State
    last_photo_time = time.time()
    count = 0
    curr_lat, curr_lon, curr_alt = 0.0, 0.0, 0.0

    print("--- STARTING CAPTURE (Press Ctrl+C to stop) ---")

    try:
        while True:
            # A. Read Serial GPS data
            if ser.in_waiting > 0:
                line = ser.readline().decode('ascii', errors='replace')
                gps_data = parse_nmea(line)
                if gps_data:
                    curr_lat, curr_lon, curr_alt = gps_data

            # B. Status Dashboard
            sys.stdout.write(f"\rLat: {curr_lat:.5f} | Lon: {curr_lon:.5f} | Alt: {curr_alt}m | Photos: {count}")
            sys.stdout.flush()

            # C. Capture Logic
            if (time.time() - last_photo_time) > IMAGE_INTERVAL and curr_lat != 0:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{OUTPUT_FOLDER}/img_{timestamp}_{count}.jpg"
                
                # Capture directly to file
                picam2.capture_file(filename)
                
                # Inject Metadata
                inject_metadata(filename, curr_lat, curr_lon, curr_alt)
                
                print(f"\n[Captured] {filename}")
                count += 1
                last_photo_time = time.time()

            time.sleep(0.01) # Small sleep to prevent CPU hogging

    except KeyboardInterrupt:
        print("\nMission Ended.")
    finally:
        picam2.stop()
        ser.close()

if __name__ == "__main__":
    main()