import serial
import pynmea2
import csv
import time
from datetime import datetime
import sys

# ==========================================
# --- CONFIGURATION (EDIT THIS SECTION) ---
# ==========================================

# 1. PORT:
# WINDOWS: Use 'COM3', 'COM4', 'COM5', etc. (Check Device Manager)
# MAC/LINUX: Use '/dev/tty.usbserial-...' or '/dev/ttyUSB0'
SERIAL_PORT = 'COM6'  # <--- CHANGE THIS TO YOUR PORT

# 2. BAUD RATE:
# MicoAir LR900 default is 57600
BAUD_RATE = 57600             

# 3. ALTIMETER FORMAT:
# What does your altimeter text start with?
ALTIMETER_KEYWORD = "ALT:"

# 4. FILENAME:
CSV_FILENAME = 'telemetry_log.csv'

# ==========================================

def log_data():
    current_alt = 0.0
    current_lat = 0.0
    current_lon = 0.0
    current_sats = 0
    
    print(f"--- GROUND STATION LOGGER ---")
    print(f"Connecting to Telemetry on: {SERIAL_PORT}")
    print(f"Speed: {BAUD_RATE} baud")
    print(f"Saving data to: {CSV_FILENAME}")
    
    try:
        # Open Serial Connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("Success! Waiting for data stream...")

        # Open CSV file
        with open(CSV_FILENAME, mode='a', newline='') as file:
            writer = csv.writer(file)
            
            # Write Header if file is empty
            if file.tell() == 0:
                writer.writerow(["Timestamp", "Latitude", "Longitude", "Altitude(m)", "Satellites", "Type"])

            while True:
                if ser.in_waiting > 0:
                    try:
                        # Read line, decode, and strip whitespace
                        raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
                        
                        # Debug: Print raw data to screen so you know it's working
                        # print(f"Raw: {raw_line}") 

                        # --- CASE 1: Altimeter Data ---
                        if raw_line.startswith(ALTIMETER_KEYWORD):
                            try:
                                # Parse "ALT: 150.5"
                                data_part = raw_line.split(':')[1] 
                                current_alt = float(data_part.strip())
                                print(f"--> Alt Update: {current_alt}m")
                            except:
                                pass

                        # --- CASE 2: GPS Data (NMEA) ---
                        elif raw_line.startswith('$') and 'GGA' in raw_line:
                            try:
                                msg = pynmea2.parse(raw_line)
                                current_lat = msg.latitude
                                current_lon = msg.longitude
                                current_sats = msg.num_sats
                                
                                # Save to CSV
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                row = [timestamp, current_lat, current_lon, current_alt, current_sats, "SYNC"]
                                writer.writerow(row)
                                file.flush()
                                
                                print(f"[{timestamp}] SAVED: {current_lat:.5f}, {current_lon:.5f} | Alt: {current_alt}m")
                                
                            except pynmea2.ParseError:
                                continue

                    except ValueError:
                        continue
                    except Exception as e:
                        print(f"Error processing line: {e}")

    except serial.SerialException:
        print(f"\n[ERROR] Could not open {SERIAL_PORT}.")
        print("1. Check that the Telemetry USB is plugged in.")
        print("2. Check Device Manager to find the correct COM port (e.g., COM3, COM4).")
        print("3. Close any other software (like Mission Planner) using this port.")

    except KeyboardInterrupt:
        print("\nLog closed.")

if __name__ == "__main__":
    log_data()