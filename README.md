# AquaScale: Full-Stack Aquaculture AI

AquaScale is an end-to-end Edge AI and mobile monitoring system designed to estimate the Biomass and K-Index of fish in real-time. By combining lightweight neural networks on edge hardware with a sleek mobile interface, this system provides actionable, 70th-percentile validated metrics for aquaculture management.

---

## System Architecture

This project operates as a Mono-Repo containing two primary engines:

* **`/edge_ai` (The Brain):** A Python-based inference engine built for the Raspberry Pi 5. It utilizes an optimized NCNN model to process tank data locally, achieving a validated **92.6% accuracy**.
* **`/mobile_app` (The Interface):** A cross-platform mobile application built with Flutter/Dart. It syncs with the Edge AI via Firebase to provide farm managers and beta testers with real-time dashboards and historical data tracking.

---

## Getting Started for Beta Testers

To run this full-stack system, you will need a Raspberry Pi 5 (or equivalent local machine) and a smartphone/emulator.

### 1. Database Setup (Crucial First Step)
For security reasons, public API keys are not included in this repository. You must connect your own Firebase instance:
1. Create a free project at [Firebase Console](https://console.firebase.google.com/).
2. Set up a Realtime Database or Firestore.
3. Keep your configuration credentials handy for the next steps.

### 2. Edge AI Setup (Raspberry Pi 5)
Navigate to the `edge_ai` folder to start the AI inference engine:

```bash
cd edge_ai
pip install -r requirements.txt
python main_pi.py
```

### 3. Mobile App Setup (Laptop/PC)
Navigate to the ```mobile_app``` folder to compile the Flutter interface:

```bash
cd mobile_app
flutter pub get
flutterfire configure
flutter run
```
---

## Security & Contribution Notes
* **API Keys** : Files such as firebase_options.dart and serviceAccountKey.json are strictly ignored via .gitignore to protect cloud databases. Never commit these files to a public branch.
* **Large Files**: Build directories (/build/) and Python environments (/venv/) are excluded to keep the repository lightweight and fast to clone.

---
Developed by: cycheng248-cityu (```cycheng248-c@my.cityu.edu.hk```)
