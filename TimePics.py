import time
import os
import subprocess
from datetime import datetime

# ================= CONFIGURATION =================
OUTPUT_FOLDER = "/home/pi/Downloads/mission_data"
INTERVAL = 2.0         # Seconds between photos
SHUTTER_SPEED = 1000   # 1000 = Sunny, 4000 = Cloudy

# =================================================

def wait_for_time_sync():
    """
    Blocks the program until the system year is correct (>= 2026).
    This proves NTP sync has happened.
    """
    print("--- WAITING FOR TIME SYNC ---")
    print("Please turn on your Mobile Hotspot...")
    
    while True:
        current_year = datetime.now().year
        # If year is 2026 or later, we are synced!
        if current_year >= 2026:
            print(f"Time Synced! Current time: {datetime.now()}")
            break
        
        # Feedback loop
        print(f"Current System Year: {current_year} (Waiting for internet...)", end='\r')
        time.sleep(1)

def main():
    # 1. Wait for valid time
    wait_for_time_sync()

    # 2. Create Folder
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    
    print(f"\n--- MISSION STARTED ---")
    print(f"Saving to: {OUTPUT_FOLDER}")
    
    frame_count = 0
    
    try:
        while True:
            start_time = time.time()
            
            # 3. Generate Filename with REAL Time
            # Format: img_20260201_103001_500.jpg (Includes milliseconds for precision)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"{OUTPUT_FOLDER}/img_{timestamp}.jpg"
            
            # 4. Capture Command (RPi V3 Optimized)
            cmd = [
                "rpicam-still",
                "-o", filename,
                "-t", "10",            # Instant capture
                "--nopreview",
                "--shutter", str(SHUTTER_SPEED),
                "--width", "4608",     # V3 Max Width
                "--height", "2592",    # V3 Max Height
                "--autofocus-mode", "manual", # Lock focus
                "--lens-position", "1.0"      # Focus on infinity
            ]
            
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print(f"Captured: {filename}")
            frame_count += 1
            
            # Precise Interval Logic
            elapsed = time.time() - start_time
            sleep_time = max(0, INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nMission Stopped.")

if __name__ == "__main__":
    main()