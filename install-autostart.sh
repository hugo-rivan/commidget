#!/bin/bash
# Install commidget as a LaunchAgent so it runs at login.
# Note: the plist uses /bin/sh -c with an inline command rather than calling a
# wrapper script under ~/Documents — macOS TCC blocks launchd from executing
# script files in ~/Documents/~/Desktop/~/Downloads.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.hugo.commidget.plist"
UID_NUM="$(id -u)"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.hugo.commidget</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/sh</string>
      <string>-c</string>
      <string>cd "$DIR" &amp;&amp; exec ./.venv/bin/python ./commidget.py</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>StandardOutPath</key><string>$DIR/commidget.log</string>
    <key>StandardErrorPath</key><string>$DIR/commidget.log</string>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
      <key>LANG</key><string>en_US.UTF-8</string>
    </dict>
    <key>LimitLoadToSessionType</key><string>Aqua</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID_NUM/com.hugo.commidget" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"
echo "✅ commidget installed and started. Look for ⎇ in your menu bar."
echo "   Logs: $DIR/commidget.log"
echo "   Uninstall: ./uninstall-autostart.sh"
