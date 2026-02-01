#!/usr/bin/env python3

import time
import serial
import board
import adafruit_bmp280
import pynmea2

# Initialize I2C for BMP280
i2c = board.I2C()

try:
    bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)
    print("BMP280 found at address 0x76")
except:
    try:
        bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x77)
        print("BMP280 found at address 0x77")
    except:
        print("ERROR: BMP280 not found!")
        exit(1)

bmp280.sea_level_pressure = 1013.25

# Initialize GPS Serial (CHANGE THIS to your GPS port)
try:
    gps_serial = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)
    print("GPS connected on /dev/ttyAMA0")
except:
    print("ERROR: Cannot open GPS port")
    exit(1)

# Initialize Telemetry Serial (CHANGE THIS to your telemetry port)
try:
    telemetry = serial.Serial('/dev/ttyUSB0', 57600, timeout=1)
    print("Telemetry connected on /dev/ttyUSB0")
except:
    print("ERROR: Cannot open telemetry port")
    exit(1)

print("Raspberry Pi Drone Telemetry Started!")

# GPS data variables
gps_lat = 0.0
gps_lon = 0.0
gps_alt = 0.0
gps_speed = 0.0
gps_sats = 0

def read_gps():
    """Read GPS NMEA data"""
    global gps_lat, gps_lon, gps_alt, gps_speed, gps_sats
    
    try:
        line = gps_serial.readline().decode('ascii', errors='replace')
        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
            msg = pynmea2.parse(line)
            if msg.lat and msg.lon:
                gps_lat = msg.latitude
                gps_lon = msg.longitude
                gps_alt = float(msg.altitude) if msg.altitude else 0.0
                gps_sats = int(msg.num_sats) if msg.num_sats else 0
        elif line.startswith('$GPRMC') or line.startswith('$GNRMC'):
            msg = pynmea2.parse(line)
            if msg.spd_over_grnd:
                gps_speed = float(msg.spd_over_grnd) * 1.852  # knots to km/h
    except:
        pass

def send_telemetry():
    """Read sensors and send data via telemetry"""
    
    # Read GPS
    read_gps()
    
    # Read BMP280
    temperature = bmp280.temperature
    pressure = bmp280.pressure
    altitude_bmp = bmp280.altitude
    
    # Format data packet
    data_packet = (
        f"START,"
        f"{temperature:.2f},"
        f"{pressure:.2f},"
        f"{altitude_bmp:.2f},"
        f"{gps_lat:.6f},"
        f"{gps_lon:.6f},"
        f"{gps_sats},"
        f"{gps_alt:.2f},"
        f"{gps_speed:.2f}"
        f",END\n"
    )
    
    telemetry.write(data_packet.encode())
    print(f"Sent: {data_packet.strip()}")
    
    if gps_lat != 0.0 and gps_lon != 0.0:
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
    gps_serial.close()