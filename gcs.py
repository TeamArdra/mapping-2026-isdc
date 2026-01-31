import serial
import csv
import time
from datetime import datetime

# --- CONFIGURATION ---
SERIAL_PORT = 'COM6'  # You mentioned COM6 in your previous message
BAUD_RATE = 57600     # Must match the 'telem_ser' baudrate on your RPi
CSV_FILENAME = 'ardra_flight_log.csv'

def log_data():
    print(f"--- ARDRA GROUND STATION ---")
    print(f"Listening on {SERIAL_PORT} at {BAUD_RATE} baud...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        
        with open(CSV_FILENAME, mode='a', newline='') as file:
            writer = csv.writer(file)
            # Header
            if file.tell() == 0:
                writer.writerow(["Laptop_Time", "RPi_Time", "Lat", "Lon", "Alt_m"])

            while True:
                if ser.in_waiting > 0:
                    # Read the CSV line sent by the Pi
                    raw_data = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if raw_data:
                        # Split the CSV: [Time, Lat, Lon, Alt]
                        parts = raw_data.split(',')
                        
                        if len(parts) >= 4:
                            # Add a laptop timestamp for local reference
                            local_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            full_row = [local_time] + parts
                            
                            writer.writerow(full_row)
                            file.flush() # Forces save to disk immediately
                            
                            print(f"[{local_time}] GPS: {parts[1]}, {parts[2]} | Alt: {parts[3]}m")

    except Exception as e:
        print(f"Connection Error: {e}")
    except KeyboardInterrupt:
        print("\nSession Saved. Closing...")

if __name__ == "__main__":
    log_data()