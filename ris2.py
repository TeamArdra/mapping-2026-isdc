#!/usr/bin/env python3

import time
import serial
import board
import adafruit_bmp280
from gps3 import agps3

# Initialize I2C for BMP280
i2c = board.I2C()

# Try both common BMP280 addresses
try:
    bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)
    print("BMP280 found at address 0x76")
except:
    try:
        bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x77)
        print("BMP280 found at address 0x77")
    except:
        print("ERROR: BMP280 not found on I2C bus!")
        print("Run 'sudo i2cdetect -y 1' to check connections")
        exit(1)

bmp280.sea_level_pressure = 1013.25

# Initialize GPS
gps_socket = agps3.GPSDSocket()
data_stream = agps3.DataStream()
gps_socket.connect()
gps_socket.watch()

# Initialize Telemetry Serial
# Change '/dev/ttyUSB0' to your telemetry port
try:
    telemetry = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)
    print("Telemetry connected on /dev/ttyUSB0")
except:
    print("ERROR: Cannot open telemetry port /dev/ttyUSB0")
    print("Check 'ls /dev/ttyUSB*' for available ports")
    exit(1)

print("Raspberry Pi Drone Telemetry Started!")
print("Waiting for GPS fix...")

def read_gps():
    """Read GPS data"""
    for new_data in gps_socket:
        if new_data:
            data_stream.unpack(new_data)
    
    latitude = data_stream.lat if data_stream.lat != 'n/a' else 0.0
    longitude = data_stream.lon if data_stream.lon != 'n/a' else 0.0
    altitude = data_stream.alt if data_stream.alt != 'n/a' else 0.0
    speed = data_stream.speed if data_stream.speed != 'n/a' else 0.0
    
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        altitude = float(altitude)
        speed = float(speed) * 3.6
    except:
        latitude = 0.0
        longitude = 0.0
        altitude = 0.0
        speed = 0.0
    
    return latitude, longitude, altitude, speed

def send_telemetry():
    """Read sensors and send data via telemetry"""
    
    # Read BMP280
    temperature = bmp280.temperature
    pressure = bmp280.pressure
    altitude_bmp = bmp280.altitude
    
    # Read GPS
    lat, lon, alt_gps, speed = read_gps()
    
    satellites = 0
    try:
        if data_stream.mode != 'n/a':
            satellites = int(data_stream.mode)
    except:
        satellites = 0
    
    # Format data packet
    data_packet = (
        f"START,"
        f"{temperature:.2f},"
        f"{pressure:.2f},"
        f"{altitude_bmp:.2f},"
        f"{lat:.6f},"
        f"{lon:.6f},"
        f"{satellites},"
        f"{alt_gps:.2f},"
        f"{speed:.2f}"
        f",END\n"
    )
    
    telemetry.write(data_packet.encode())
    print(f"Sent: {data_packet.strip()}")
    
    if lat != 0.0 and lon != 0.0:
        print("GPS: LOCKED")
    else:
        print("GPS: SEARCHING...")

# Main loop
try:
    while True:
        send_telemetry()
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\nStopping telemetry...")
    telemetry.close()
    gps_socket.close()