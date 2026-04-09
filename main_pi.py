import cv2
import numpy as np
import os
import time
import math
import threading
import sys
import datetime
import bezier
from ultralytics import YOLO
from scipy.optimize import linear_sum_assignment

# IoT & Web
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, Response
import subprocess
import re

# ==========================================
# 0. PORT CLEANER (Prevents "Address in Use" crash)
# ==========================================
print("Sweeping Port 5000...")
os.system("fuser -k 5000/tcp > /dev/null 2>&1")
time.sleep(1) 
print("Port 5000 clear. Booting system...")

# ========================================================
# 1. IOT CONFIGURATION & CLOUDFLARE URL SETTING & GLOBALS
# ========================================================
CRED_PATH = "/home/cycheng248/AquaScale/serviceAccountKey.json"
TANK_ID = "TANK_001" 
DATABASE_URL = "https://aquascale-36cc0-default-rtdb.firebaseio.com/" 

try:
    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
    ref = db.reference(f'users/{TANK_ID}')
    print(f"Firebase Connected: {TANK_ID}")
except Exception as e:
    print(f" Firebase Error: {e}")
    sys.exit(1)

def start_cloudflared_tunnel():
    print("Starting Cloudflare Tunnel...")
    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:5000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    url_pattern = re.compile(r"https://[\w-]+\.trycloudflare\.com")
    url_found = False
    try:
        for line in process.stdout:
            if not url_found:
                match = url_pattern.search(line)
                if match:
                    base_url = match.group(0)
                    full_stream_url = base_url + "/video_feed"
                    print(f"\n PUBLIC URL GENERATED: {base_url}")
                    
                    ref = db.reference(f'users/{TANK_ID}')
                    ref.update({
                        "stream_url": full_stream_url,
                        "last_boot_time": str(datetime.datetime.now())
                    })
                    print(" URL Uploaded to Firebase!\n")
                    url_found = True
    except Exception as e:
        print(f" Tunnel Error: {e}")

PARAMS = {
    "tank_length": 45.0, "tank_width": 27.0, "tank_height": 30.0,
    "water_depth": 24.0, "glass_thickness": 0.5,
    "top_cam_distance": 45.0, "side_cam_distance": 30.0,
    "n_air": 1.0, "n_water": 1.33, "n_glass": 1.5, "water_density": 1.0,
    "act_thresh_low": 0.5, "act_thresh_high": 3.0,
    "feeding_time": "15:00", 
}

frame_lock = threading.Lock() 
global_frame_final = None
latest_frame_top = None 
latest_frame_side = None

TOP_CAM_ID = 0
SIDE_CAM_ID = 2 
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# ==========================================
# 2. REAL-TIME CONFIG LISTENER
# ==========================================
def listen_for_config_changes():
    def listener(event):
        if event.data and isinstance(event.data, dict):
            for key, value in event.data.items():
                if key == 'length': PARAMS["tank_length"] = float(value)
                elif key == 'width': PARAMS["tank_width"] = float(value)
                elif key == 'height': PARAMS["tank_height"] = float(value)
                elif key == 'cam_top_dist': PARAMS["top_cam_distance"] = float(value)
                elif key == 'cam_side_dist': PARAMS["side_cam_distance"] = float(value)
            try:
                full_data = db.reference(f'users/{TANK_ID}/config').get()
                if full_data:
                    h = full_data.get('feed_hour', 15)
                    m = full_data.get('feed_minute', 0)
                    PARAMS["feeding_time"] = f"{h:02d}:{m:02d}"
            except: pass
    db.reference(f'users/{TANK_ID}/config').listen(listener)

# ==========================================
# 3. PHYSICS & MATH LOGIC
# ==========================================
def top_camera_regression(length_xy, thickness, depth):
    top_cam = PARAMS["top_cam_distance"]
    tank_l = PARAMS["tank_length"]
    tank_h = PARAMS["tank_height"]
    n_air, n_water = PARAMS["n_air"], PARAMS["n_water"]
    
    length_temp = length_xy / 2
    thickness_temp = thickness / 2
    fish_to_camera = top_cam + depth
    
    l_common = (length_temp / fish_to_camera) * top_cam
    t_common = (thickness_temp / fish_to_camera) * top_cam
    
    theta_air_l = math.atan(length_temp / fish_to_camera)
    theta_water_l = math.asin(n_air * math.sin(theta_air_l) / n_water)
    l_reduced = math.tan(theta_water_l) * depth
    actual_length_pixel = 2 * (l_common + l_reduced)
    
    theta_air_t = math.atan(thickness_temp / fish_to_camera)
    theta_water_t = math.asin(n_air * math.sin(theta_air_t) / n_water)
    t_reduced = math.tan(theta_water_t) * depth
    actual_thickness_pixel = 2 * (t_common + t_reduced)
    
    ref_scale = fish_to_camera / (top_cam - (tank_h - depth))
    cm_per_pixel = tank_l / FRAME_WIDTH 
    return (actual_length_pixel * ref_scale * cm_per_pixel), (actual_thickness_pixel * ref_scale * cm_per_pixel) 

def side_camera_regression(length_z, height, distance):
    side_cam = PARAMS["side_cam_distance"]
    glass_thk = PARAMS["glass_thickness"]
    tank_l = PARAMS["tank_length"]
    n_air, n_water, n_glass = PARAMS["n_air"], PARAMS["n_water"], PARAMS["n_glass"]
    
    length_temp = length_z / 2
    height_temp = height / 2
    fish_to_camera = side_cam + glass_thk + distance
    
    l_common = (length_temp / fish_to_camera) * side_cam
    h_common = (height_temp / fish_to_camera) * side_cam
    
    theta_air_h = math.atan(height_temp / fish_to_camera)
    val_gh = min(1.0, max(-1.0, n_air * math.sin(theta_air_h) / n_glass))
    h_reduced_1 = math.tan(math.asin(val_gh)) * glass_thk
    val_wh = min(1.0, max(-1.0, n_glass * math.sin(math.asin(val_gh)) / n_water))
    h_reduced_2 = math.tan(math.asin(val_wh)) * distance
    actual_height_pixel = 2 * (h_common + h_reduced_1 + h_reduced_2)
    
    actual_length_ref = actual_height_pixel / side_cam * fish_to_camera 
    actual_length_z = actual_length_ref * (tank_l / FRAME_WIDTH) 
    actual_height_ref = actual_height_pixel / side_cam * fish_to_camera
    actual_height = actual_height_ref * (tank_l / FRAME_WIDTH)
    return actual_length_z, actual_height

def calc_physics_metrics(side_kpts, side_box, top_kpts, top_box):
    # --- FIXED: SCALE NCNN 640 KEYPOINTS BACK TO 640x480 ---
    # NCNN outputs coordinates mapped to the 640x640 imgsz, squishing the vertical axis
    scale_y = 480 / 640 
    
    nodes = np.asfortranarray([
        [top_kpts[0][0], top_kpts[4][0], top_kpts[1][0]], 
        [top_kpts[0][1] * scale_y, top_kpts[4][1] * scale_y, top_kpts[1][1] * scale_y]
    ])
    curve = bezier.Curve(nodes, degree=2)
    raw_length_xy = curve.length
    
    # Scale Y coordinates for thickness and height calculations
    t2_y, t3_y = top_kpts[2][1] * scale_y, top_kpts[3][1] * scale_y
    raw_thickness = np.linalg.norm(np.array([top_kpts[2][0], t2_y]) - np.array([top_kpts[3][0], t3_y]))
    
    distance_cm = (((top_box[1] * scale_y) + (top_box[3] * scale_y)) / 2) * PARAMS["tank_width"] / FRAME_HEIGHT

    # --- HARD DISTANCE FILTER ---
    # Delete outliers: Fish closer than 5cm to the glass distort the optics.
    if distance_cm < 5.0 or distance_cm > (PARAMS["tank_width"] - 2.0):
        return 0, 0, 0 

    raw_length_z = abs(side_kpts[0][0] - side_kpts[1][0])
    s2_y, s3_y = side_kpts[2][1] * scale_y, side_kpts[3][1] * scale_y
    raw_height = np.linalg.norm(np.array([side_kpts[2][0], s2_y]) - np.array([side_kpts[3][0], s3_y]))
    
    depth_cm = (FRAME_HEIGHT - (((side_box[1] * scale_y) + (side_box[3] * scale_y)) / 2)) * PARAMS["tank_height"] / FRAME_HEIGHT

    real_len_xy, real_thick = top_camera_regression(raw_length_xy, raw_thickness, depth_cm)
    real_len_z, real_h = side_camera_regression(raw_length_z, raw_height, distance_cm)
    
    # Use the max of the two calculated lengths as per standard methodology
    final_l = max(real_len_xy, real_len_z)
    
    return final_l, real_thick, real_h

def estimate_mass(l, t, h):
    # Ellipsoidal model
    vol = (0.27 + 0.01*l - 0.03*t + 0.17*h) * math.pi / 6 * l * t * h
    return PARAMS["water_density"] * vol

# ==========================================
# 4. UTILS & SCHEDULER
# ==========================================
class ActivityMonitor:
    def __init__(self):
        self.prev_centers = [] 
        self.speeds = []
        self.last_time = time.time() # NEW: Track actual time

    def update(self, detections):
        current_time = time.time()
        time_delta = current_time - self.last_time
        self.last_time = current_time
        
        current_centers = []
        current_lengths = []
        
        for fish in detections:
            box = fish['box']
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            length_px = math.hypot(box[2] - box[0], box[3] - box[1])
            current_centers.append((cx, cy))
            current_lengths.append(length_px)

        # GUARD: If no previous data, OR if the time gap is huge (e.g., a new day started)
        if not self.prev_centers or not current_centers or time_delta <= 0 or time_delta > 5.0:
            self.prev_centers = current_centers
            return 0.0

        cost_matrix = np.zeros((len(self.prev_centers), len(current_centers)))
        for i, prev in enumerate(self.prev_centers):
            for j, curr in enumerate(current_centers):
                cost_matrix[i, j] = math.hypot(prev[0] - curr[0], prev[1] - curr[1])

        r_inds, c_inds = linear_sum_assignment(cost_matrix)
        frame_speeds = []
        
        for r, c in zip(r_inds, c_inds):
            dist_pixels = cost_matrix[r, c]
            body_len = current_lengths[c]
            
            if body_len > 0 and dist_pixels < (body_len * 5):
                
                raw_bl_per_sec = (dist_pixels / body_len) / time_delta
                
                if raw_bl_per_sec < 0.05: 
                    bl_per_sec = 0.0
                else:
                    bl_per_sec = raw_bl_per_sec
                    
                frame_speeds.append(bl_per_sec)

        avg_speed = np.mean(frame_speeds) if frame_speeds else 0.0
        
        if frame_speeds:
            self.speeds.append(avg_speed)

        self.prev_centers = current_centers
        return avg_speed

    def get_median(self):
        # Return the median activity of the ENTIRE time window
        if not self.speeds: return 0.0
        return float(np.median(self.speeds))


class ThreadedCamera:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ret, self.frame = self.cap.read()
        self.running = True
        self.lock = threading.Lock()
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.running:
            if self.cap.isOpened():
                self.ret, self.frame = self.cap.read()
            else:
                time.sleep(0.1)
            time.sleep(0.005) 

    def read(self):
        with self.lock:
            return self.ret, self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        self.cap.release()

def get_clean_detections(results):
    data = []
    if results.keypoints is None or results.boxes is None: return data
    for box, kpts in zip(results.boxes, results.keypoints):
        b = box.xyxy[0].cpu().numpy()
        if (b[2]-b[0])*(b[3]-b[1]) < 500: continue 
        k = kpts.data[0].cpu().numpy()
        match_x = k[0][0] if k[0][2] > 0.5 else (b[0]+b[2])/2
        data.append({'box': b, 'kpts': k, 'match_x': match_x})
    return data

def is_inference_window():
    """STRICT 1-HOUR WINDOW: Returns True ONLY between [FeedingTime - 1 Hour] and [FeedingTime]"""
    now = datetime.datetime.now()
    try:
        f_hour, f_min = map(int, str(PARAMS["feeding_time"]).split(':'))
        feed_dt = now.replace(hour=f_hour, minute=f_min, second=0, microsecond=0)
        
        # Set explicitly to 1 hour for the final test
        start_window = feed_dt - datetime.timedelta(minutes=30)
        
        if start_window <= now < feed_dt:
            return True, now.minute
        return False, now.minute
    except:
        return False, 0

# ==========================================
# 5. FLASK SERVER
# ==========================================
app = Flask(__name__)
global_jpeg_bytes = None

def generate_frames():
    while True:
        with frame_lock:
            if global_jpeg_bytes is None:
                time.sleep(0.01)
                continue
            current_bytes = global_jpeg_bytes
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + current_bytes + b'\r\n')
        time.sleep(0.03)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ==========================================
# 6. MAIN AI LOOP
# ==========================================
def run_video_renderer(cam_t, cam_s):
    global global_jpeg_bytes, latest_frame_top, latest_frame_side
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank_frame, "CAMERA OFFLINE", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    while True:
        ret_t, frame_t = cam_t.read()
        ret_s, frame_s = cam_s.read()
        if not ret_t or frame_t is None: frame_t = blank_frame.copy()
        if not ret_s or frame_s is None: frame_s = blank_frame.copy()

        with frame_lock:
            latest_frame_top = frame_t.copy()
            latest_frame_side = frame_s.copy()

        try:
            if frame_s.shape[1] != frame_t.shape[1]:
                frame_s = cv2.resize(frame_s, (frame_t.shape[1], frame_t.shape[0]))
            combined = cv2.vconcat([frame_t, frame_s])
            ret, buffer = cv2.imencode('.jpg', combined, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if ret:
                with frame_lock:
                    global_jpeg_bytes = buffer.tobytes()
        except Exception as e: pass
        time.sleep(0.02)

def run_ai_worker():
    global latest_frame_top, latest_frame_side
    print("Loading PyTorch (.ncnn) Model...")
    
    # 1. ENFORCE NCNN MODEL
    model_path = '/home/cycheng248/AquaScale/best_ncnn_model'
    model = YOLO(model_path, task='pose') 
    
    activity_mon = ActivityMonitor()
    hourly_k = []
    hourly_biomass = [] 
    last_report_date = None
    last_minute_checked = -1

    while True:
        with frame_lock:
            if latest_frame_top is None or latest_frame_side is None: 
                time.sleep(0.1)
                continue
            snap_t = latest_frame_top.copy()
            snap_s = latest_frame_side.copy()

        now = datetime.datetime.now()
        in_window, current_minute = is_inference_window()
        
        # Run inference logic during the 1-hour window
        if in_window:
            res_t = model.predict(snap_t, verbose=False, imgsz=640, half=True, conf=0.3)[0]
            res_s = model.predict(snap_s, verbose=False, imgsz=640, half=True, conf=0.3)[0]
            
            top_fish = get_clean_detections(res_t)
            side_fish = get_clean_detections(res_s)
            activity_mon.update(top_fish)
            
            if len(top_fish) > 0 and len(side_fish) > 0:
                cost_matrix = np.zeros((len(top_fish), len(side_fish)))
                for i, t in enumerate(top_fish):
                    for j, s in enumerate(side_fish):
                        cost_matrix[i, j] = abs(t['match_x'] - s['match_x'])
                
                r_inds, c_inds = linear_sum_assignment(cost_matrix)
                
                # --- FIXED: POPULATION AVERAGES FOR K-INDEX ---
                frame_masses = []
                frame_lengths = []
                
                for r, c in zip(r_inds, c_inds):
                    if cost_matrix[r, c] < 50:
                        t_dat = top_fish[r]
                        s_dat = side_fish[c]
                        
                        # calc_physics_metrics now includes the distance guard and scale fix
                        l, t, h = calc_physics_metrics(s_dat['kpts'], s_dat['box'], t_dat['kpts'], t_dat['box'])
                        
                        # Only add to list if the distance guard didn't reject the fish
                        if l > 0 and t > 0 and h > 0:
                            m = estimate_mass(l, t, h)
                            frame_masses.append(m)
                            frame_lengths.append(l)
                
                if frame_masses and frame_lengths: 
                    # Biomass is the TOTAL mass in the frame
                    hourly_biomass.append(sum(frame_masses))
                    
                    # K-Index uses the AVERAGE mass and AVERAGE length of the frame
                    avg_mass = np.mean(frame_masses)
                    avg_length = np.mean(frame_lengths)
                    
                    if avg_length > 0:
                        frame_k = 10000.0 * (avg_mass / (avg_length ** 3))
                        hourly_k.append(frame_k)


        if last_minute_checked != current_minute:
            if (last_minute_checked % 5 == 0) and in_window:
                print(f" Window Active. Samples collected: {len(hourly_biomass)}")
            last_minute_checked = current_minute
            
        # 3. DAILY REPORT TRIGGER
        try:
            feed_str = str(PARAMS["feeding_time"])
            f_hour, f_min = map(int, feed_str.split(':'))
            
            target_time = now.replace(hour=f_hour, minute=f_min, second=0, microsecond=0)
            today_str = str(datetime.date.today())
            
            if now >= target_time and last_report_date != today_str:
                
                # GUARD: Ensure we don't upload empty results
                if len(hourly_biomass) < 50:
                    print(f"Waiting for more data... current samples: {len(hourly_biomass)}")
                    time.sleep(30) 
                    continue 

                print("1-Hour Window Complete. Processing Final Metrics...")
                
                # --- PERCENTILE METHOD LOGIC ---
                
                # 1. Calculate Biomass using Percentile
                if hourly_biomass:
                    final_mass = float(np.percentile(hourly_biomass,67))
                else:
                    final_mass = 0.0

                # 2. Calculate K-Index using Median of the Population Averages
                if hourly_k:
                    final_k = float(np.median(hourly_k))
                else:
                    final_k = 0.0
                
                final_act = activity_mon.get_median()

                # Generate the health comment
                comment = "Analysis Complete."
                if final_mass == 0: comment = "No fish detected today."
                elif final_k < 1.0: comment = "Fish are skinny. Increase protein."
                elif final_k > 3.0: comment = "Fish are overweight. Reduce feed."
                
                # Push the final results to Firebase
                ref.child('daily_report').set({
                    "date": today_str,
                    "final_biomass": round(final_mass, 1),
                    "final_k_index": round(final_k, 2),
                    "final_activity": round(final_act, 1),
                    "comment": comment
                })
                
                print(f"RESULTS UPLOADED for {today_str} | Biomass: {round(final_mass, 1)}g | K-Index: {round(final_k, 2)} | Activity: {round(final_act, 1)}")
                
                # THIS TRIGGERS THE APP NOTIFICATION
                ref.child('notification').update({
                    "title": "Feeding Time!",
                    "body": f"Biomass check complete: {round(final_mass, 1)}g recorded.",
                    "timestamp": str(now),
                    "status": "unread"
                })
                
                print(f"NOTIFICATION SENT: {today_str}")
                last_report_date = today_str
                hourly_k, hourly_biomass = [], []
                activity_mon.speeds = []
                
        except Exception as e:
            print(f"Report Error: {e}")
            
        time.sleep(0.1)

if __name__ == '__main__':
    cam_top = ThreadedCamera(TOP_CAM_ID)
    cam_side = ThreadedCamera(SIDE_CAM_ID)
    time.sleep(2.0)

    threading.Thread(target=listen_for_config_changes, daemon=True).start()
    threading.Thread(target=run_video_renderer, args=(cam_top, cam_side), daemon=True).start()
    threading.Thread(target=run_ai_worker, daemon=True).start()
    threading.Thread(target=start_cloudflared_tunnel, daemon=True).start()

    print(f"\nSYSTEM READY: {TANK_ID}")
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
