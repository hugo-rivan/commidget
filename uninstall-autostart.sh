#!/bin/bash
PLIST="$HOME/Library/LaunchAgents/com.hugo.commidget.plist"
launchctl bootout "gui/$(id -u)/com.hugo.commidget" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
if [ -f "$PLIST" ]; then
  rm "$PLIST"
  echo "✅ commidget LaunchAgent removed."
else
  echo "No LaunchAgent found at $PLIST."
fi
