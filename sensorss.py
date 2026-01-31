import serial
import pynmea2
import csv
import time
from datetime import datetime

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyAMA3'
BAUD_RATE = 57600
CSV_FILENAME = 'flight_log_combined.csv'

# ADJUST THIS: What text does your altimeter line start with?
ALTIMETER_KEYWORD = "ALT:" 

def log_combined_data():
    # Variables to hold the "Current State"
    current_alt = 0.0
    current_lat = 0.0
    current_lon = 0.0
    current_sats = 0
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Listening on {SERIAL_PORT}...")
        print(f"Looking for GPS (NMEA) and Altimeter lines starting with '{ALTIMETER_KEYWORD}'")

        with open(CSV_FILENAME, mode='a', newline='') as file:
            writer = csv.writer(file)
            
            # Header
            if file.tell() == 0:
                writer.writerow(["Timestamp", "Latitude", "Longitude", "Altitude(m)", "Satellites", "Raw_Source"])

            while True:
                if ser.in_waiting > 0:
                    try:
                        raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
                        
                        # --- CASE 1: It is the ALTIMETER ---
                        if raw_line.startswith(ALTIMETER_KEYWORD):
                            # Example line: "ALT: 150.5"
                            # We split by ':' and take the second part
                            try:
                                data_part = raw_line.split(':')[1] 
                                current_alt = float(data_part.strip())
                                print(f"-> Altimeter Update: {current_alt}m")
                            except (IndexError, ValueError):
                                pass # formatting error, ignore

                        # --- CASE 2: It is the GPS (NMEA) ---
                        elif raw_line.startswith('$') and 'GGA' in raw_line:
                            try:
                                msg = pynmea2.parse(raw_line)
                                current_lat = msg.latitude
                                current_lon = msg.longitude
                                current_sats = msg.num_sats
                                
                                # TRIGGER: We write to CSV when GPS updates (usually 1Hz - 5Hz)
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                row = [timestamp, current_lat, current_lon, current_alt, current_sats, "GPS_TRIG"]
                                writer.writerow(row)
                                file.flush()
                                
                                print(f"[{timestamp}] SAVED: Lat:{current_lat:.5f} Lon:{current_lon:.5f} Alt:{current_alt}m")
                                
                            except pynmea2.ParseError:
                                continue

                    except ValueError:
                        continue
                        
    except KeyboardInterrupt:
        print("\nLogging Stopped.")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    log_combined_data()