import 'dart:convert'; // To wrap data in JSON format
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http; // To send the command to the Pi

class WifiSetupScreen extends StatefulWidget {
  @override
  _WifiSetupScreenState createState() => _WifiSetupScreenState();
}

class _WifiSetupScreenState extends State<WifiSetupScreen> {
  // Controllers capture what the user types
  final TextEditingController _ssidController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isLoading = false; // Shows the spinner when sending data
  String _statusMessage = ""; // Shows Success/Error messages

  // --- THE CORE LOGIC ---
  Future<void> _sendCredentialsToPi() async {
    // 1. Basic Validation
    if (_ssidController.text.isEmpty || _passwordController.text.isEmpty) {
      setState(() {
        _statusMessage = "❌ Please enter both WiFi Name and Password.";
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _statusMessage = "Sending data to AquaScale...";
    });

    // 2. The Pi's IP Address (Fixed Gateway IP)
    // When connected to the Hotspot, the Pi is ALWAYS 10.42.0.1
    final String piUrl = 'http://10.42.0.1/api/connect';

    try {
      print("🚀 Connecting to: $piUrl");

      // 3. Send the HTTP POST Request
      final response = await http
          .post(
            Uri.parse(piUrl),
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({
              "ssid": _ssidController.text.trim(), // The WiFi Name
              "password": _passwordController.text.trim(), // The WiFi Password
            }),
          )
          .timeout(Duration(seconds: 10)); // Fail if Pi doesn't answer in 10s

      // 4. Handle Response
      if (response.statusCode == 200) {
        // Success: The Pi received the data and is rebooting
        setState(() {
          _statusMessage =
              "✅ Success! Device is rebooting...\nYour phone will disconnect shortly.";
        });
      } else {
        // Server Error: The Pi rejected it (rare)
        setState(() {
          _statusMessage = "❌ Server Error: ${response.body}";
        });
      }
    } catch (e) {
      // Network Error: Phone is likely not connected to AquaScale WiFi
      setState(() {
        _statusMessage =
            "❌ Connection Failed.\nAre you connected to 'AquaScale_TANK_XXX'?";
        print("Error: $e");
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("Connect Device")),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.wifi_tethering, size: 80, color: Colors.blue),
            SizedBox(height: 20),
            Text(
              "Enter the WiFi details you want the AquaScale to use.",
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: Colors.grey[700]),
            ),
            SizedBox(height: 30),

            // WiFi Name Input
            TextField(
              controller: _ssidController,
              decoration: InputDecoration(
                labelText: "WiFi Name (SSID)",
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.wifi),
              ),
            ),
            SizedBox(height: 15),

            // Password Input
            TextField(
              controller: _passwordController,
              obscureText: true, // Hide password
              decoration: InputDecoration(
                labelText: "WiFi Password",
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.lock),
              ),
            ),
            SizedBox(height: 30),

            // Connect Button
            _isLoading
                ? CircularProgressIndicator()
                : SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: ElevatedButton(
                      onPressed: _sendCredentialsToPi,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blue,
                        foregroundColor: Colors.white,
                      ),
                      child: Text(
                        "CONNECT DEVICE",
                        style: TextStyle(fontSize: 18),
                      ),
                    ),
                  ),

            SizedBox(height: 20),
            // Status Message (Success/Error)
            Text(
              _statusMessage,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
                color: _statusMessage.startsWith("❌")
                    ? Colors.red
                    : Colors.green,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
