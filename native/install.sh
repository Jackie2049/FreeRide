#!/bin/bash
#
# FreeRide Installation Script
#
# This script:
# 1. Builds the Chrome extension
# 2. Configures Native Messaging
# 3. Sets up the CLI
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EXTENSION_DIR="$PROJECT_DIR/extension"
NATIVE_DIR="$SCRIPT_DIR"
CLI_DIR="$PROJECT_DIR/cli"

echo "=== FreeRide Installation ==="
echo ""

# Step 1: Build Chrome extension
echo "[1/4] Building Chrome extension..."
cd "$EXTENSION_DIR"

if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo "Building extension..."
npm run build

if [ ! -d "dist" ] || [ ! -f "dist/background.js" ] || [ ! -f "dist/content.js" ]; then
    echo "ERROR: Build failed - required files not found in dist/"
    exit 1
fi
echo "✓ Extension built successfully"
echo ""

# Step 2: Configure Native Messaging
echo "[2/4] Configuring Native Messaging..."

# Make native_host.py executable
chmod +x "$NATIVE_DIR/native_host.py"

# Determine browser config directory
BROWSER=""
if [ -d "$HOME/.config/google-chrome" ]; then
    BROWSER="chrome"
    NATIVE_HOST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
elif [ -d "$HOME/.config/chromium" ]; then
    BROWSER="chromium"
    NATIVE_HOST_DIR="$HOME/.config/chromium/NativeMessagingHosts"
elif [ -d "$HOME/.config/microsoft-edge" ]; then
    BROWSER="edge"
    NATIVE_HOST_DIR="$HOME/.config/microsoft-edge/NativeMessagingHosts"
else
    echo "Warning: Could not detect browser, defaulting to Chromium"
    BROWSER="chromium"
    NATIVE_HOST_DIR="$HOME/.config/chromium/NativeMessagingHosts"
fi

mkdir -p "$NATIVE_HOST_DIR"

# Create native host manifest
MANIFEST_DEST="$NATIVE_HOST_DIR/com.freeride.native_host.json"

cat > "$MANIFEST_DEST" << EOF
{
  "name": "com.freeride.native_host",
  "description": "FreeRide Native Messaging Host",
  "path": "$NATIVE_DIR/native_host.py",
  "type": "stdio",
  "allowed_origins": []
}
EOF

echo "✓ Native Messaging configured at: $MANIFEST_DEST"
echo "  Browser detected: $BROWSER"
echo ""

# Step 3: Setup CLI
echo "[3/4] Setting up CLI..."

# Make CLI executable
chmod +x "$CLI_DIR/freeride.py"

# Create wrapper script
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/freeride" << 'WRAPPER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/freeride.py"

# Check if running from project directory
if [ -f "$PYTHON_SCRIPT" ]; then
    python3 "$PYTHON_SCRIPT" "$@"
else
    # Use installed version
    python3 /home/zhaozifeng/cc-workspace/FreeRide/cli/freeride.py "$@"
fi
WRAPPER

chmod +x "$BIN_DIR/freeride"

echo "✓ CLI installed to: $BIN_DIR/freeride"
echo ""

# Step 4: Print instructions
echo "[4/4] Final Setup Instructions"
echo ""
echo "================================"
echo ""
echo "STEP A: Load Chrome Extension"
echo "--------------------------------"
echo "1. Open $BROWSER"
echo "2. Go to: chrome://extensions/"
echo "3. Enable 'Developer mode' (toggle in top right)"
echo "4. Click 'Load unpacked'"
echo "5. Select this directory:"
echo "   $EXTENSION_DIR"
echo "6. After loading, note the 'Extension ID' shown below the extension name"
echo ""
echo "STEP B: Configure Extension ID"
echo "--------------------------------"
echo "7. Edit the Native Messaging manifest:"
echo "   $MANIFEST_DEST"
echo ""
echo "8. Add your Extension ID to allowed_origins:"
echo "   \"allowed_origins\": [\"chrome-extension://YOUR_EXTENSION_ID/\"]"
echo ""
echo "   Example (replace YOUR_EXTENSION_ID):"
echo "   \"allowed_origins\": [\"chrome-extension://abcdefghijklmnopqrstuvwxyz123456/\"]"
echo ""
echo "STEP C: Restart Browser"
echo "--------------------------------"
echo "9. Completely close and restart $BROWSER"
echo ""
echo "STEP D: Start Native Host"
echo "--------------------------------"
echo "10. In a terminal, start the native host:"
echo "    python3 $NATIVE_DIR/native_host.py"
echo ""
echo "STEP E: Test"
echo "--------------------------------"
echo "11. Open https://www.doubao.com/"
echo "12. In another terminal, run:"
echo "    freeride ask \"Hello, who are you?\""
echo ""
echo "================================"
echo ""

# Check if PATH includes bin dir
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "NOTE: Add $BIN_DIR to your PATH:"
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
    echo "  Or add to ~/.bashrc:"
    echo "  echo 'export PATH=\"\$PATH:$BIN_DIR\"' >> ~/.bashrc"
    echo ""
fi

echo "Installation complete!"
