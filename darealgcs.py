import socket
import struct
import csv
import time
from datetime import datetime
import os

# --- CONFIGURATION ---
# Use '0.0.0.0' to listen on all available network interfaces
UDP_IP = "0.0.0.0"  
UDP_PORT = 5005
FILENAME = 'ardra_telemetry_log.csv'

# This MUST match the '!dfff' format used in your RPi script
# ! = Network (Big-endian), d = Double (8 bytes), f = Float (4 bytes)
DATA_FORMAT = '!dfff' 

def start_gcs():
    print(f"--- ARDRA UDP GROUND STATION LOGGER ---")
    print(f"Listening for UDP packets on port {UDP_PORT}...")
    
    # Initialize UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    # Open file in 'append' mode
    file_exists = os.path.isfile(FILENAME)
    
    try:
        with open(FILENAME, mode='a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header
            if not file_exists:
                writer.writerow(["Laptop_Timestamp", "RPi_Unix_Time", "Lat", "Lon", "Alt_m"])
            
            print(f"Success! Saving data to: {os.path.abspath(FILENAME)}")

            while True:
                # 1. Receive binary packet (buffer size 1024 is plenty for 20 bytes)
                data, addr = sock.recvfrom(1024)
                
                try:
                    # 2. Unpack the "columns" from binary
                    # decoded = (timestamp, lat, lon, alt)
                    decoded = struct.unpack(DATA_FORMAT, data)
                    
                    # 3. Create local timestamp
                    local_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    
                    # 4. Save and Print
                    full_row = [local_now] + list(decoded)
                    writer.writerow(full_row)
                    csvfile.flush()
                    
                    print(f"[{local_now}] From {addr[0]} | Lat: {decoded[1]:.6f}, Lon: {decoded[2]:.6f} | Alt: {decoded[3]}m")
                    
                except Exception as e:
                    print(f"Error unpacking packet: {e}")

    except KeyboardInterrupt:
        print("\nLogging stopped. CSV file saved.")
    finally:
        sock.close()

if __name__ == "__main__":
    start_gcs()