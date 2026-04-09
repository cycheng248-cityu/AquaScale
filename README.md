<<<<<<< HEAD
# AquaScale: Autonomous Biological Edge Monitor (Public Beta)

AquaScale is a high-speed, computer-vision-based system designed for non-invasive monitoring of fish biomass, health, and activity in aquaculture environments. Optimized for the **Raspberry Pi 5**, this system utilizes NCNN-accelerated inference to provide real-time population analytics.

### Current Beta Status (Validated March 2026)
Following a rigorous 9-day validation phase, the system has achieved the following benchmarks:
* **Biomass Accuracy**: 92.6% (Validated against 27.0g physical target).
* **Health Metrics**: Stable Fulton’s K-Index tracking in the 1.4 – 2.0 "Optimal" range.
* **Activity Monitoring**: Jitter-free velocity tracking at 0.2 BL/s using speed-based deadzones.
* **Operational Autonomy**: 100% self-healing via Systemd daemons and automated daily reboots.

### Key Technical Features
* **Statistical Filtering**: Implements a **70th-percentile extraction model** to overcome natural fish-schooling occlusion, significantly outperforming standard median-based counts.
* **Physics-Informed AI**: Integrated regression mathematics to correct for water refraction and lens distortion in real-time.
* **True-Time Velocity**: A custom activity monitor that uses actual time deltas (`time.time()`) to isolate biological movement from AI bounding-box jitter.
* **NCNN Acceleration**: Optimized for edge deployment, providing over **7,500 samples per hour** on a standard Raspberry Pi 5.

### Prerequisites
* **Hardware**: Raspberry Pi 5 (8GB recommended) with active cooling.
* **Camera**: Dual-camera setup (Top-Down and Side-View).
* **Python Version**: Tested on **Python 3.11** (standard for Raspberry Pi OS Bookworm).

### Installation
1. **Clone the repository**:
   ```bash
   git clone [https://github.com/cycheng248-cityu/AquaScale.git](https://github.com/cycheng248-cityu/AquaScale.git)```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt```

### Contributing to the Beta
We are seeking aquaculture professionals and developers to test the framework in diverse environments.

* **Species Diversity**: Testing the 70th-percentile logic on different fish body shapes.

* **Turbidity Limits**: Defining the limits of optical accuracy in various water conditions.

* **Hardware Expansion**: Contributions for Hailo-8 NPU integration to support high-density tank scaling.

Disclaimer: This is a beta-release intended for research and testing. Please ensure all hardware is properly waterproofed before tank deployment.
   


For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
>>>>>>> eeb3e4e (feat: integrate flutter mobile app into system)
