import subprocess
import time
import socket
import os
import sys

# ==========================================
# CONFIGURATION
# ==========================================
# Make sure these filenames match exactly what you have on your Pi
AI_SCRIPT = "/home/cycheng248/AquaScale/main_pi.py"       # The script that runs the camera/AI
SETUP_SCRIPT = "/home/cycheng248/AquaScale/wifi_portal.py" # The script that runs the web server
VENV_PYTHON = "/home/cycheng248/AquaScale/venv/bin/python"

def check_internet():
    """
    Tries to connect to Google's DNS server (8.8.8.8).
    If successful, we have internet.
    """
    try:
        # Connect to 8.8.8.8 on port 53 (DNS) with a 3-second timeout
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def start_setup_mode():
    """
    Called when NO internet is found.
    1. Turns ON the Hotspot.
    2. Runs the Web Server so the user can connect.
    """
    print("⚠️  No Internet Detected.")
    print("🔄 Starting SETUP MODE (Hotspot: AquaScale_TANK_XXX)...")
    
    # Force the Hotspot to start (since we set autoconnect=no)
    subprocess.run(["sudo", "nmcli", "con", "up", "Hotspot"])
    
    # Run the Portal Script (This blocks the program until the user reboots)
    os.system(f"sudo {VENV_PYTHON} {SETUP_SCRIPT}")

def start_normal_mode():
    """
    Called when Internet IS found.
    1. Turns OFF the Hotspot (to save WiFi bandwidth).
    2. Runs the main AI script.
    """
    print("✅ Internet Connected!")
    print("🚀 Starting NORMAL MODE (AI Engine)...")
    
    # Ensure Hotspot is OFF so it doesn't interfere with the connection
    subprocess.run(["sudo", "nmcli", "con", "down", "Hotspot"], capture_output=True)
    
    # Run the Main AI Script
    os.system(f"{VENV_PYTHON} {AI_SCRIPT}")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("⏳ Boot Manager Started...")
    print("⏳ Waiting 15 seconds for OS to connect to saved WiFi...")
    
    # Critical Delay: Give the Pi time to auto-connect to known networks
    time.sleep(15)
    
    # Check 1: Do we have internet?
    if check_internet():
        start_normal_mode()
    else:
        # Double Check: Wait 5 more seconds just in case
        print("❌ First check failed. Retrying in 5s...")
        time.sleep(5)
        
        if check_internet():
            start_normal_mode()
        else:
            # If still no internet, give up and start Hotspot
            start_setup_mode()
