import subprocess
from flask import Flask, request, jsonify, render_template_string
import time
import sys
import os

app = Flask(__name__)

# ==========================================
# 1. HTML TEMPLATE (For Browser Access)
# ==========================================
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AquaScale Setup</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: white; padding: 20px; text-align: center; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 12px; margin: auto; max-width: 400px; }
        input, button { width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px; border: none; box-sizing: border-box; }
        input { background: #333; color: white; }
        button { background: #00bcd4; color: black; font-weight: bold; cursor: pointer; }
        h2 { color: #00bcd4; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🌊 Connect AquaScale</h2>
        <p>Enter your home WiFi details below.</p>
        <form action="/connect_html" method="POST">
            <input type="text" name="ssid" placeholder="WiFi Name (SSID)" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">CONNECT DEVICE</button>
        </form>
    </div>
</body>
</html>
"""

# ==========================================
# 2. HELPER FUNCTION: CONNECT WIFI
# ==========================================
def connect_to_wifi(ssid, password):
    print(f"🔗 Attempting connection to: {ssid}")
    
    if not ssid or not password:
        return False, "Missing SSID or Password"

    try:
        # 1. Delete old profile if it exists (prevents duplicates)
        subprocess.run(["sudo", "nmcli", "con", "delete", ssid], capture_output=True)
        
        # 2. Create the new connection
        # We wrap this in a shell command that waits slightly, then reboots
        # This ensures the HTTP response gets back to the phone BEFORE the Pi dies.
        cmd = f"nmcli dev wifi connect '{ssid}' password '{password}'"
        
        # Background task: Sleep 2s -> Run Connect -> Sleep 5s -> Reboot
        full_cmd = f"sleep 2; sudo {cmd}; sleep 5; sudo reboot"
        subprocess.Popen(full_cmd, shell=True)
        
        return True, "Saved! Device is rebooting..."
        
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. ROUTES
# ==========================================

@app.route('/')
def home():
    """Serves the HTML page for browser users"""
    return render_template_string(HTML_PAGE)

@app.route('/connect_html', methods=['POST'])
def connect_html():
    """Handles the Form Submit from the Browser"""
    ssid = request.form.get('ssid')
    password = request.form.get('password')
    
    success, message = connect_to_wifi(ssid, password)
    
    if success:
        return f"<h1 style='color:green; text-align:center; padding-top:50px;'>✅ {message}</h1>"
    else:
        return f"<h1 style='color:red; text-align:center; padding-top:50px;'>❌ Error: {message}</h1>"

@app.route('/api/connect', methods=['POST'])
def api_connect():
    """Handles the JSON Request from your Flutter App"""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No JSON received"}), 400
        
    ssid = data.get('ssid')
    password = data.get('password')
    
    success, message = connect_to_wifi(ssid, password)
    
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message}), 500

if __name__ == '__main__':
    # Run on Port 80 (Standard Web Port)
    # Host '0.0.0.0' allows external access from the phone
    app.run(host='0.0.0.0', port=80)
