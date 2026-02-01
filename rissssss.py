#!/usr/bin/env python3

import time
import serial
import board
import adafruit_bmp280

# Initialize I2C for BMP280
i2c = board.I2C()

try:
    bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)
    print("✓ BMP280 found at address 0x76")
except:
    try:
        bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x77)
        print("✓ BMP280 found at address 0x77")
    except:
        print("✗ ERROR: BMP280 not found!")
        exit(1)

bmp280.sea_level_pressure = 1013.25

# Initialize Telemetry Serial
# Try ttyAMA0 first, then ttyAMA1
TELEM_PORT = '/dev/ttyAMA2'
TELEM_BAUD = 57600

try:
    telemetry = serial.Serial(TELEM_PORT, TELEM_BAUD, timeout=1)
    print(f"✓ Telemetry connected on {TELEM_PORT}")
except:
    TELEM_PORT = '/dev/ttyAMA2'
    try:
        telemetry = serial.Serial(TELEM_PORT, TELEM_BAUD, timeout=1)
        print(f"✓ Telemetry connected on {TELEM_PORT}")
    except Exception as e:
        print(f"✗ ERROR: Cannot open telemetry")
        print(f"   Tried: /dev/ttyAMA0 and /dev/ttyAMA1")
        print(f"   Error: {e}")
        exit(1)

print("\n" + "="*50)
print("🚁 Raspberry Pi Telemetry - BMP280 Only")
print("="*50 + "\n")

def send_telemetry():
    """Read BMP280 and send data via telemetry"""
    
    # Read BMP280
    temperature = bmp280.temperature
    pressure = bmp280.pressure
    altitude = bmp280.altitude
    
    # Format data packet (simplified - BMP280 only)
    # Format: START,temp,pressure,altitude,END
    data_packet = (
        f"START,"
        f"{temperature:.2f},"
        f"{pressure:.2f},"
        f"{altitude:.2f}"
        f",END\n"
    )
    
    # Send via telemetry
    telemetry.write(data_packet.encode())
    
    # Debug print
    print(f"📡 Sent: {data_packet.strip()}")

# Main loop
try:
    while True:
        send_telemetry()
        time.sleep(1)  # Send every 1 second
        
except KeyboardInterrupt:
    print("\n" + "="*50)
    print("🛑 Stopping telemetry...")
    print("="*50)
    telemetry.close()