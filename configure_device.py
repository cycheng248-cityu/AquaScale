import sys
import subprocess
import os

# CONFIGURATION
CONFIG_FILE = "device_id.txt"
DEFAULT_PASS = "aquascalepass"

def set_device_identity(new_id):
    # 1. Save ID to file (The Single Source of Truth)
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write(new_id.strip())
        print(f"✅ Identity Saved to file: {new_id}")
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return

    # 2. Configure Hotspot Name
    ssid_name = f"AquaScale_{new_id}"
    print(f"⚙️  Configuring Hotspot: {ssid_name}...")

    # Delete old hotspot profile if it exists (to avoid duplicates)
    subprocess.run(["sudo", "nmcli", "con", "delete", "Hotspot"], capture_output=True)

    # Create new Hotspot connection
    # con-name="Hotspot" (Internal Name for our scripts)
    # ssid="AquaScale_TANK_XXX" (External Name for users)
    cmd = [
        "sudo", "nmcli", "con", "add", 
        "type", "wifi", 
        "ifname", "wlan0", 
        "con-name", "Hotspot",
        "autoconnect", "yes", 
        "ssid", ssid_name
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

        # Set Security (WPA2) & Shared IP mode
        subprocess.run(["sudo", "nmcli", "con", "modify", "Hotspot", "802-11-wireless-security.key-mgmt", "wpa-psk"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["sudo", "nmcli", "con", "modify", "Hotspot", "802-11-wireless-security.psk", DEFAULT_PASS], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["sudo", "nmcli", "con", "modify", "Hotspot", "ipv4.method", "shared"], check=True, stdout=subprocess.DEVNULL)
        # Set priority low so it doesn't override known home WiFi
        subprocess.run(["sudo", "nmcli", "con", "modify", "Hotspot", "connection.autoconnect-priority", "-100"], check=True, stdout=subprocess.DEVNULL)

        print(f"🎉 SUCCESS! WiFi Name set to: {ssid_name}")
        print(f"🔑 Password set to: {DEFAULT_PASS}")

    except subprocess.CalledProcessError as e:
        print(f"❌ NetworkManager Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python configure_device.py TANK_ID")
        print("Example: python configure_device.py TANK_001")
    else:
        set_device_identity(sys.argv[1])
