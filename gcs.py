import serial
import csv
import time
from datetime import datetime
import os

# --- CONFIGURATION ---
SERIAL_PORT = 'COM6'  # Matches your telemetry connection
BAUD_RATE = 57600     # Matches the RPi telemetry baud rate
FILENAME = 'ardra_telemetry_log.csv'

def start_gcs():
    print(f"--- ARDRA GROUND STATION LOGGER ---")
    print(f"Listening on {SERIAL_PORT}...")
    
    try:
        # Initialize Serial
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        
        # Open file in 'append' mode
        file_exists = os.path.isfile(FILENAME)
        
        with open(FILENAME, mode='a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header only if the file is being created for the first time
            if not file_exists:
                writer.writerow(["Laptop_Timestamp", "RPi_Time", "Lat", "Lon", "Alt_m"])
            
            print(f"Success! Saving data to: {os.path.abspath(FILENAME)}")
            print("Waiting for data stream...")

            while True:
                if ser.in_waiting > 0:
                    try:
                        # Read the incoming line from the RPi
                        raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
                        
                        if raw_line:
                            # The RPi sends: Timestamp, Lat, Lon, Alt
                            parts = raw_line.split(',')
                            
                            if len(parts) >= 4:
                                # Create a local timestamp for the laptop
                                local_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                
                                # Combine local time with RPi data
                                full_row = [local_now] + parts
                                
                                # Append to CSV
                                writer.writerow(full_row)
                                csvfile.flush()  # Force write to disk immediately
                                
                                # Display to user
                                print(f"[{local_now}] DATA: Lat {parts[1]}, Lon {parts[2]} | Alt: {parts[3]}m")
                            else:
                                print(f"Malformed data received: {raw_line}")
                                
                    except Exception as e:
                        print(f"Error parsing line: {e}")
                
                time.sleep(0.01) # Yield CPU

    except serial.SerialException as e:
        print(f"ERROR: Could not open {SERIAL_PORT}. Check connection or if another app is using it.")
        print(f"Details: {e}")
    except KeyboardInterrupt:
        print("\nLogging stopped by user. CSV file saved.")

if __name__ == "__main__":
    start_gcs()