import os
import pandas as pd
import piexif
from datetime import datetime, timedelta
from fractions import Fraction

# ================= CONFIGURATION =================
# 1. Path to your folder containing the images
IMAGE_FOLDER = r"C:\Users\YourName\Downloads\Mission_Images"

# 2. Path to your Betaflight Blackbox CSV export
CSV_FILE = r"C:\Users\YourName\Downloads\LOG00001.csv"

# 3. Timezone Adjustment
# GPS data is always UTC (Greenwich Mean Time).
# Your RPi photos are likely in your Local Time (e.g., India is +5.5 hours).
# Set this to the difference so they match.
TIMEZONE_OFFSET_HOURS = 5.5 

# ================= HELPER FUNCTIONS =================

def to_deg(value, loc):
    """Converts decimal degrees to DMS format for EXIF"""
    if value < 0: loc_value = loc[1]
    else: loc_value = loc[0]
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min_val = int(t1)
    sec = round((t1 - min_val) * 60, 4)
    return (deg, min_val, sec, loc_value)

def change_to_rational(number):
    """Converts float to rational fraction for EXIF"""
    value = abs(number)
    if value == 0: return (0, 1)
    f = Fraction(str(value)).limit_denominator(10000)
    return (f.numerator, f.denominator)

def inject_exif(filename, lat, lon, alt):
    """Writes GPS data into the image EXIF"""
    try:
        exif_dict = piexif.load(filename)
        
        lat_deg = to_deg(lat, ["N", "S"])
        lng_deg = to_deg(lon, ["E", "W"])
        
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: lat_deg[3].encode('utf-8'),
            piexif.GPSIFD.GPSLatitude: [change_to_rational(lat_deg[0]), change_to_rational(lat_deg[1]), change_to_rational(lat_deg[2])],
            piexif.GPSIFD.GPSLongitudeRef: lng_deg[3].encode('utf-8'),
            piexif.GPSIFD.GPSLongitude: [change_to_rational(lng_deg[0]), change_to_rational(lng_deg[1]), change_to_rational(lng_deg[2])],
            piexif.GPSIFD.GPSAltitudeRef: 1 if alt < 0 else 0,
            piexif.GPSIFD.GPSAltitude: change_to_rational(round(alt, 2))
        }
        
        exif_dict["GPS"] = gps_ifd
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, filename)
        print(f"Tagged: {os.path.basename(filename)} -> {lat}, {lon}")
        return True
    except Exception as e:
        print(f"Error tagging {filename}: {e}")
        return False

# ================= MAIN LOGIC =================

def main():
    print("--- 1. Loading CSV Data ---")
    # Read CSV. We assume Betaflight headers.
    # Note: Betaflight often uses "GPS_coord[0]" for Lat and "GPS_coord[1]" for Lon
    try:
        df = pd.read_csv(CSV_FILE, low_memory=False)
        
        # Clean column names (strip whitespace)
        df.columns = df.columns.str.strip()
        
        # Check if we have the right columns
        required_cols = ['GPS_coord[0]', 'GPS_coord[1]']
        if not all(col in df.columns for col in required_cols):
            print(f"ERROR: CSV missing columns. Found: {df.columns}")
            print("Did you export 'GPS_coord' and 'GPS_time' from Blackbox Explorer?")
            return

        # Create a "Datetime" column from the CSV GPS time
        # Betaflight CSV usually has 'GPS_time' as a combined number or string. 
        # We need to construct a robust datetime object.
        # This part depends HEAVILY on your CSV format.
        # Assuming you have a 'Date' and 'Time' column or similar.
        # IF NOT, we will match by comparing "Time of Day" only.
        
        print(f"Loaded {len(df)} rows. Processing timestamps...")
        
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        return

    print("\n--- 2. Processing Images ---")
    
    files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.jpg', '.jpeg'))]
    
    for f in files:
        # Parse timestamp from filename: img_20260201_103001_500.jpg
        try:
            # Remove "img_" prefix and ".jpg" suffix
            time_str = f.replace("img_", "").replace(".jpg", "")
            # Parse format: YYYYMMDD_HHMMSS_mmm
            # We only really need up to seconds for matching
            time_part = time_str.split("_") 
            date_str = time_part[0] # 20260201
            hms_str = time_part[1]  # 103001
            
            img_time = datetime.strptime(f"{date_str}{hms_str}", "%Y%m%d%H%M%S")
            
            # Convert Image Time (Local) to GPS Time (UTC) for matching
            # If Image is IST (+5.5), subtract 5.5 to get UTC
            target_utc_time = img_time - timedelta(hours=TIMEZONE_OFFSET_HOURS)
            
            # Format target time to match CSV format (HH:MM:SS)
            # This is a naive "closest match" search.
            # We look for the CSV row where the GPS Time is closest to our Target Time.
            
            # NOTE: Betaflight CSV often splits time into "GPS_time" (e.g. 14003000 for 14:00:30.00)
            # We will convert the CSV time column to a comparable format on the fly for this row.
            
            # --- SEARCH LOGIC ---
            # We assume the CSV has a column that represents time. 
            # If your CSV export has 'GPS_time' (format HHMMSSMM), let's use that.
            
            # Finding the closest row:
            # We'll filter the dataframe for rows roughly matching the hour/minute first to speed it up
            target_hour = target_utc_time.hour
            target_minute = target_utc_time.minute
            target_second = target_utc_time.second
            
            # Construct a number to match Betaflight 'GPS_time' format (HHMMSSmm) roughly
            # Example: 10:30:05 -> 10300500
            search_val = (target_hour * 10000000) + (target_minute * 100000) + (target_second * 1000)
            
            # Find closest value in the 'GPS_time' column
            if 'GPS_time' in df.columns:
                # Find index of closest match
                closest_idx = (df['GPS_time'] - search_val).abs().idxmin()
                row = df.loc[closest_idx]
                
                # Extract Data (Betaflight coordinates are often integers, divide by 1e7)
                # E.g. 123456789 -> 12.3456789
                lat = float(row['GPS_coord[0]']) / 10000000.0
                lon = float(row['GPS_coord[1]']) / 10000000.0
                alt = float(row['GPS_altitude']) if 'GPS_altitude' in df.columns else 0.0
                
                # Check for "Zero" data (no lock)
                if lat == 0 and lon == 0:
                    print(f"Skipping {f}: GPS log has no lock at this time.")
                    continue
                    
                # Write to Image
                full_path = os.path.join(IMAGE_FOLDER, f)
                inject_exif(full_path, lat, lon, alt)
                
            else:
                print("Error: Column 'GPS_time' not found in CSV. Please re-export CSV with GPS Time included.")
                break
                
        except Exception as e:
            print(f"Skipping {f}: Could not parse filename timestamp. ({e})")
            continue

    print("\n--- Done! ---")

if __name__ == "__main__":
    main()