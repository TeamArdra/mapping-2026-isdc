import serial

# The Pi 5 uses /dev/ttyAMA0 or /dev/serial0 for GPIO UART
# Ensure baudrate matches your Foxeer (default is usually 9600 or 115200)
ser = serial.Serial('/dev/serial0', 9600, timeout=1)

print("--- Reading GPS Coordinates ---")

try:
    while True:
        line = ser.readline().decode('ascii', errors='replace')
        # We look for the Recommended Minimum Navigation Information (RMC) string
        if "$GNRMC" in line or "$GPRMC" in line:
            data = line.split(',')
            if data[2] == 'A':  # 'A' means the GPS has a valid signal lock
                # Latitude: DDMM.MMMM
                lat = data[3]
                # Longitude: DDDMM.MMMM
                lon = data[5]
                print(f"Status: Fixed | Lat: {lat} {data[4]} | Lon: {lon} {data[6]}")
            else:
                print("Status: Searching for Satellites...")
except KeyboardInterrupt:
    ser.close()
    print("\nStopped.")