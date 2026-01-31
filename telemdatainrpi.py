import serial
import pynmea2
import time
import board
import adafruit_bmp280

# 1. Setup Sensors
i2c = board.I2C()
bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)

# UPDATED: Foxeer M10Q 250 default baud rate is 115200
gps_ser = serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=1)

# Telemetry (Laptop link)
telem_ser = serial.Serial('/dev/ttyUSB0', baudrate=57600, timeout=1)

print("Ardra System: Foxeer M10Q + BMP280 Active")

def get_data():
    alt = round(bmp280.altitude, 2)
    
    # Read GPS - M10 chips output at 10Hz by default
    line = gps_ser.readline().decode('ascii', errors='replace')
    lat, lon = "0.0", "0.0"
    
    # M10 modules use GN/GP prefixes for NMEA
    if '$G' in line and 'RMC' in line:
        try:
            msg = pynmea2.parse(line)
            lat, lon = msg.latitude, msg.longitude
        except:
            pass
            
    return f"{time.strftime('%H:%M:%S')},{lat},{lon},{alt}\n"

try:
    while True:
        csv_data = get_data()
        telem_ser.write(csv_data.encode('utf-8'))
        print(f"Sent: {csv_data.strip()}")
        time.sleep(0.1) # Matches 10Hz output of Foxeer GPS

except KeyboardInterrupt:
    gps_ser.close()
    telem_ser.close()