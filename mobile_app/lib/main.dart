import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
// Timezone packages for Scheduling
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;
import 'package:flutter_timezone/flutter_timezone.dart';
import 'firebase_options.dart';

// --- NEW IMPORT: The Screen we just created ---
import 'wifi_setup.dart';

// --- NOTIFICATION PLUGIN SETUP ---
final FlutterLocalNotificationsPlugin flutterLocalNotificationsPlugin =
    FlutterLocalNotificationsPlugin();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  // 1. Initialize Timezones (Required for Scheduled Alarms)
  tz.initializeTimeZones();
  final String timeZoneName = await FlutterTimezone.getLocalTimezone();
  tz.setLocalLocation(tz.getLocation(timeZoneName));

  // 2. Initialize Notifications
  const AndroidInitializationSettings initializationSettingsAndroid =
      AndroidInitializationSettings('@mipmap/ic_launcher');
  const InitializationSettings initializationSettings = InitializationSettings(
    android: initializationSettingsAndroid,
  );

  await flutterLocalNotificationsPlugin.initialize(
    initializationSettings,
    onDidReceiveNotificationResponse: (details) {
      print("Notification Tapped: ${details.payload}");
    },
  );

  runApp(const AquaScaleApp());
}

class AquaScaleApp extends StatelessWidget {
  const AquaScaleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'AquaScale Pro',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF121212),
        primarySwatch: Colors.cyan,
        useMaterial3: true,
      ),
      home: const TankListScreen(),
    );
  }
}

// --- DATA MODEL ---
class Tank {
  String id;
  String name;
  Tank({required this.id, required this.name});
  Map<String, dynamic> toJson() => {'id': id, 'name': name};
  factory Tank.fromJson(Map<String, dynamic> json) =>
      Tank(id: json['id'], name: json['name']);
}

// ==========================================
// SCREEN 1: HOME (Global Listener)
// ==========================================
class TankListScreen extends StatefulWidget {
  const TankListScreen({super.key});

  @override
  State<TankListScreen> createState() => _TankListScreenState();
}

class _TankListScreenState extends State<TankListScreen> {
  List<Tank> myTanks = [];
  final Map<String, StreamSubscription> _listeners = {};

  // Stores the last unique report ID to prevent spam, but allow updates
  String _lastReportID = "";

  @override
  void initState() {
    super.initState();
    _requestNotificationPermissions();
    _loadTanks();
  }

  @override
  void dispose() {
    for (var sub in _listeners.values) {
      sub.cancel();
    }
    super.dispose();
  }

  void _requestNotificationPermissions() {
    flutterLocalNotificationsPlugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.requestNotificationsPermission();
  }

  Future<void> _loadTanks() async {
    final prefs = await SharedPreferences.getInstance();
    final String? data = prefs.getString('my_tanks_v2');
    if (data != null) {
      final List<dynamic> decoded = jsonDecode(data);
      setState(() {
        myTanks = decoded.map((e) => Tank.fromJson(e)).toList();
      });
      // Start listening to all tanks immediately
      for (var tank in myTanks) {
        _startListeningToTank(tank);
      }
    }
  }

  // --- THE GLOBAL LISTENER (With Timestamp Logic) ---
  void _startListeningToTank(Tank tank) {
    if (_listeners.containsKey(tank.id)) return;

    // --- FIX: Listen to the 'notification' node, not 'daily_report' ---
    final ref = FirebaseDatabase.instance.ref().child(
      'users/${tank.id}/notification',
    );

    final sub = ref.onValue.listen((event) async {
      final data = event.snapshot.value as Map?;
      if (data != null) {
        // Use the timestamp as the unique ID to prevent double-notifying
        String timestamp = data['timestamp']?.toString() ?? "";
        String title = data['title'] ?? "AquaScale Update";
        String body = data['body'] ?? "New data available.";

        if (timestamp != _lastReportID && timestamp.isNotEmpty) {
          if (mounted) {
            setState(
              () => _lastReportID = timestamp,
            ); // Mark this timestamp as seen

            _showImmediateNotification("${tank.name}: $title", body);
          }
        }
      }
    });

    _listeners[tank.id] = sub;
  }

  Future<void> _showImmediateNotification(String title, String body) async {
    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
          'aquascale_report',
          'AquaScale Reports',
          importance: Importance.max,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        );
    const NotificationDetails details = NotificationDetails(
      android: androidDetails,
    );
    await flutterLocalNotificationsPlugin.show(
      DateTime.now().millisecond, // Unique ID
      title,
      body,
      details,
    );
  }

  Future<void> _saveTanks() async {
    final prefs = await SharedPreferences.getInstance();
    final String data = jsonEncode(myTanks.map((e) => e.toJson()).toList());
    await prefs.setString('my_tanks_v2', data);
  }

  void _addTank(String id, String nickname) {
    if (id.isEmpty) return;
    if (myTanks.any((t) => t.id == id)) return;
    Tank newTank = Tank(
      id: id.toUpperCase(),
      name: nickname.isEmpty ? "Tank ${myTanks.length + 1}" : nickname,
    );
    setState(() {
      myTanks.add(newTank);
    });
    _saveTanks();
    _startListeningToTank(newTank);
  }

  void _deleteTank(int index) {
    Tank t = myTanks[index];
    _listeners[t.id]?.cancel();
    _listeners.remove(t.id);
    setState(() => myTanks.removeAt(index));
    _saveTanks();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("MY TANKS", style: GoogleFonts.oswald(letterSpacing: 1.5)),
        centerTitle: true,
        // --- ADDED: The Setup Button in the top right ---
        actions: [
          IconButton(
            icon: const Icon(Icons.wifi_find, color: Colors.cyanAccent),
            tooltip: "Connect New Device",
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => WifiSetupScreen()),
              );
            },
          ),
        ],
      ),
      body: myTanks.isEmpty
          ? const Center(
              child: Text(
                "No tanks connected.",
                style: TextStyle(color: Colors.grey),
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: myTanks.length,
              itemBuilder: (context, index) {
                final tank = myTanks[index];
                return Card(
                  color: const Color(0xFF1E1E1E),
                  margin: const EdgeInsets.only(bottom: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(15),
                  ),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: Colors.cyan.withOpacity(0.2),
                      child: const Icon(Icons.videocam, color: Colors.cyan),
                    ),
                    title: Text(
                      tank.name,
                      style: GoogleFonts.oswald(fontSize: 20),
                    ),
                    subtitle: Text(
                      "ID: ${tank.id}",
                      style: const TextStyle(color: Colors.grey),
                    ),
                    trailing: const Icon(
                      Icons.arrow_forward_ios,
                      size: 16,
                      color: Colors.grey,
                    ),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => DashboardScreen(
                          tankId: tank.id,
                          tankName: tank.name,
                        ),
                      ),
                    ),
                    onLongPress: () => _deleteTank(index),
                  ),
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddDialog,
        backgroundColor: Colors.cyan,
        child: const Icon(Icons.add, color: Colors.black),
      ),
    );
  }

  void _showAddDialog() {
    final idCtrl = TextEditingController();
    final nameCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF2C2C2C),
        title: const Text("Track New Pi"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: idCtrl,
              decoration: const InputDecoration(
                labelText: "Tank ID (e.g. TANK_001)",
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: nameCtrl,
              decoration: const InputDecoration(
                labelText: "Nickname",
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () {
              _addTank(idCtrl.text.trim(), nameCtrl.text.trim());
              Navigator.pop(context);
            },
            child: const Text("Add to List"),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// SCREEN 2: DASHBOARD (Auto-Stream Fix)
// ==========================================
class DashboardScreen extends StatefulWidget {
  final String tankId;
  final String tankName;
  const DashboardScreen({
    super.key,
    required this.tankId,
    required this.tankName,
  });

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late DatabaseReference _dbRef;
  String streamUrl = ""; // Starts empty, waits for Firebase

  String lastUpdated = "Waiting...";
  String comment = "Connecting to AI...";
  double biomass = 0.0;
  double kIndex = 0.0;
  double activity = 0.0;

  @override
  void initState() {
    super.initState();
    _dbRef = FirebaseDatabase.instance.ref().child('users/${widget.tankId}');
    _setupRealtimeListener();
  }

  void _setupRealtimeListener() {
    _dbRef.onValue.listen((event) {
      final data = event.snapshot.value as Map?;
      if (data == null) return;

      if (mounted) {
        setState(() {
          // --- FIX: GRAB STREAM URL AUTOMATICALLY ---
          if (data.containsKey('stream_url')) {
            String newUrl = data['stream_url'].toString();
            // Only update if it's different to prevent flickering
            if (newUrl != streamUrl) {
              streamUrl = newUrl;
              print("NEW STREAM URL RECEIVED: $streamUrl");
            }
          }

          // --- GRAB REPORT DATA ---
          if (data.containsKey('daily_report')) {
            final report = data['daily_report'] as Map;
            biomass =
                double.tryParse(report['final_biomass'].toString()) ?? 0.0;
            kIndex = double.tryParse(report['final_k_index'].toString()) ?? 0.0;
            activity =
                double.tryParse(report['final_activity'].toString()) ?? 0.0;
            comment = report['comment'] ?? "No Alert";
            lastUpdated = report['date'] ?? "";
          }
        });
      }
    });
  }

  // Helpers for labels and colors
  String _getHealthLabel(double k) {
    if (k == 0) return "--";
    if (k < 1.0) return "Skinny";
    if (k > 3.0) return "Chunky";
    return "Healthy";
  }

  Color _getHealthColor(double k) {
    if (k == 0) return Colors.grey;
    if (k < 1.0 || k > 3.0) return Colors.redAccent;
    return Colors.greenAccent;
  }

  String _getActivityLabel(double act) {
    if (act == 0) return "Still";
    if (act < 0.5) return "Resting";
    if (act > 3.0) return "Frenzy";
    return "Cruising";
  }

  Color _getActivityColor(double act) {
    if (act == 0) return Colors.grey;
    if (act < 0.5) return Colors.orangeAccent;
    if (act > 3.0) return Colors.redAccent;
    return Colors.greenAccent;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.tankName),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => SettingsScreen(tankId: widget.tankId),
              ),
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // --- VIDEO PLAYER (Auto-Loads streamUrl) ---
            TankVideoPlayer(url: streamUrl),

            // --- METRICS GRID ---
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12.0),
              child: GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                childAspectRatio: 1.4,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                children: [
                  _buildCard(
                    "Biomass",
                    "${biomass.toStringAsFixed(1)}g",
                    Icons.scale,
                    Colors.white,
                    Colors.orangeAccent,
                  ),
                  _buildCard(
                    "Health",
                    _getHealthLabel(kIndex),
                    Icons.favorite,
                    _getHealthColor(kIndex),
                    _getHealthColor(kIndex),
                  ),
                  _buildCard(
                    "Activity (BL/s)",
                    activity.toStringAsFixed(1),
                    Icons.speed,
                    _getActivityColor(activity),
                    _getActivityColor(activity),
                  ),
                  _buildCard(
                    "Last Scan",
                    lastUpdated.isEmpty ? "--" : lastUpdated.substring(5),
                    Icons.calendar_today,
                    Colors.white,
                    Colors.purpleAccent,
                  ),
                ],
              ),
            ),

            // --- AI COMMENT BOX ---
            Container(
              margin: const EdgeInsets.all(12),
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF1E1E1E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white10),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: const [
                      Icon(Icons.auto_awesome, color: Colors.cyan, size: 20),
                      SizedBox(width: 8),
                      Text(
                        "AI ANALYSIS",
                        style: TextStyle(color: Colors.grey, fontSize: 12),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    comment,
                    style: GoogleFonts.roboto(fontSize: 16, height: 1.4),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCard(
    String title,
    String value,
    IconData icon,
    Color valueColor,
    Color iconColor,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E1E),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: iconColor, size: 28),
          const SizedBox(height: 8),
          Text(
            value,
            style: GoogleFonts.oswald(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: valueColor,
            ),
          ),
          Text(title, style: const TextStyle(color: Colors.grey, fontSize: 12)),
        ],
      ),
    );
  }
}

// --- ISOLATED VIDEO PLAYER CLASS ---
class TankVideoPlayer extends StatefulWidget {
  final String url;
  const TankVideoPlayer({super.key, required this.url});

  @override
  State<TankVideoPlayer> createState() => _TankVideoPlayerState();
}

class _TankVideoPlayerState extends State<TankVideoPlayer> {
  WebViewController? _controller;

  @override
  void didUpdateWidget(TankVideoPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Only reload if the URL ACTUALLY changes.
    if (widget.url != oldWidget.url && widget.url.isNotEmpty) {
      _loadStream();
    }
  }

  @override
  void initState() {
    super.initState();
    _loadStream();
  }

  void _loadStream() {
    if (widget.url.isEmpty) return;
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.black)
      ..loadRequest(Uri.parse(widget.url));
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 240,
      width: double.infinity,
      margin: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.cyan.withOpacity(0.3)),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: _controller == null
            ? const Center(child: CircularProgressIndicator(color: Colors.cyan))
            : WebViewWidget(controller: _controller!),
      ),
    );
  }
}

// ==========================================
// SCREEN 3: SETTINGS (WITH ALARM SCHEDULER)
// ==========================================
class SettingsScreen extends StatefulWidget {
  final String tankId;
  const SettingsScreen({super.key, required this.tankId});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _lenCtrl = TextEditingController();
  final _widthCtrl = TextEditingController();
  final _heightCtrl = TextEditingController();
  final _camTopCtrl = TextEditingController();
  final _camSideCtrl = TextEditingController();
  final _urlCtrl = TextEditingController();
  TimeOfDay _feedingTime = const TimeOfDay(hour: 12, minute: 0);

  @override
  void initState() {
    super.initState();
    _loadCurrentSettings();
  }

  void _loadCurrentSettings() async {
    final snapshot = await FirebaseDatabase.instance
        .ref()
        .child('users/${widget.tankId}')
        .get();
    if (snapshot.exists) {
      final data = snapshot.value as Map;
      if (data.containsKey('config')) {
        final config = data['config'] as Map;
        if (mounted) {
          setState(() {
            _lenCtrl.text = config['length']?.toString() ?? "";
            _widthCtrl.text = config['width']?.toString() ?? "";
            _heightCtrl.text = config['height']?.toString() ?? "";
            _camTopCtrl.text = config['cam_top_dist']?.toString() ?? "";
            _camSideCtrl.text = config['cam_side_dist']?.toString() ?? "";
            if (config['feed_hour'] != null) {
              _feedingTime = TimeOfDay(
                hour: int.parse(config['feed_hour'].toString()),
                minute: int.parse(config['feed_minute'].toString()),
              );
            }
          });
        }
      }
      if (data.containsKey('stream_url')) {
        _urlCtrl.text = data['stream_url'].toString();
      }
    }
  }

  // --- SCHEDULE THE ALARM ON THE PHONE ---
  Future<void> _scheduleDailyReminder(TimeOfDay time) async {
    await flutterLocalNotificationsPlugin.cancelAll(); // Clear old alarms

    // Calculate next occurrence
    final now = tz.TZDateTime.now(tz.local);
    var scheduledDate = tz.TZDateTime(
      tz.local,
      now.year,
      now.month,
      now.day,
      time.hour,
      time.minute,
    );

    // If time passed today, schedule for tomorrow
    if (scheduledDate.isBefore(now)) {
      scheduledDate = scheduledDate.add(const Duration(days: 1));
    }

    await flutterLocalNotificationsPlugin.zonedSchedule(
      0,
      'Time to Feed!',
      'Your AI Analysis Report is ready.',
      scheduledDate,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'aquascale_alarm',
          'Feeding Reminders',
          importance: Importance.max,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        ),
      ),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time, // Repeat Daily
    );
    print("⏰ Alarm Set for ${time.hour}:${time.minute}");
  }

  void _saveSettings() async {
    final ref = FirebaseDatabase.instance.ref().child('users/${widget.tankId}');
    ref.child('config').set({
      'length': _lenCtrl.text,
      'width': _widthCtrl.text,
      'height': _heightCtrl.text,
      'cam_top_dist': _camTopCtrl.text,
      'cam_side_dist': _camSideCtrl.text,
      'feed_hour': _feedingTime.hour,
      'feed_minute': _feedingTime.minute,
    });

    // Note: We don't save stream_url here anymore, the Pi does it.

    // Set the phone alarm immediately
    await _scheduleDailyReminder(_feedingTime);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Saved! Alarm set for ${_feedingTime.format(context)}"),
        ),
      );
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Tank Parameters")),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // --- READ ONLY URL FIELD ---
          TextField(
            controller: _urlCtrl,
            readOnly: true, // <--- LOCKED
            style: const TextStyle(color: Colors.cyanAccent),
            decoration: const InputDecoration(
              labelText: "Auto-Connected Stream",
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.link, color: Colors.cyan),
              filled: true,
              fillColor: Colors.black26,
            ),
          ),
          const SizedBox(height: 20),
          _buildInput("Length", _lenCtrl),
          _buildInput("Width", _widthCtrl),
          _buildInput("Height", _heightCtrl),
          _buildInput("Top Cam Dist", _camTopCtrl),
          _buildInput("Side Cam Dist", _camSideCtrl),
          const SizedBox(height: 20),
          ListTile(
            title: const Text("Feeding Time"),
            subtitle: const Text("Daily Phone Alarm"),
            trailing: Text(
              _feedingTime.format(context),
              style: const TextStyle(fontSize: 18, color: Colors.cyan),
            ),
            tileColor: Colors.white10,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
            onTap: () async {
              final picked = await showTimePicker(
                context: context,
                initialTime: _feedingTime,
              );
              if (picked != null) setState(() => _feedingTime = picked);
            },
          ),
          const SizedBox(height: 40),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.cyan,
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
            onPressed: _saveSettings,
            child: const Text(
              "SAVE CONFIGURATION",
              style: TextStyle(
                color: Colors.black,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInput(String label, TextEditingController ctrl) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10.0),
      child: TextField(
        controller: ctrl,
        keyboardType: TextInputType.number,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          filled: true,
          fillColor: Colors.white10,
        ),
      ),
    );
  }
}
