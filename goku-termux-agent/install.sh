#!/bin/bash

# Goku Termux Agent Installer
SOURCE_DIR=$(pwd)
GOKU_DIR="$HOME/.goku"

# Detect bin directory
if [ -n "$PREFIX" ]; then
    PREFIX_BIN="$PREFIX/bin"
else
    PREFIX_BIN="/usr/local/bin"
    # If not root, use ~/.local/bin
    if [ "$EUID" -ne 0 ]; then
        PREFIX_BIN="$HOME/.local/bin"
        mkdir -p "$PREFIX_BIN"
    fi
fi

echo "Installing Goku AI Agent..."

# Create Goku directory
mkdir -p "$GOKU_DIR"
cp -r "$SOURCE_DIR/goku" "$GOKU_DIR/"
cp -r "$SOURCE_DIR/scripts" "$GOKU_DIR/"
cp "$SOURCE_DIR/requirements.txt" "$GOKU_DIR/"

# Find the actual git root (where .git folder lives)
GIT_ROOT=$(cd "$SOURCE_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "$SOURCE_DIR")
echo "$GIT_ROOT" > "$GOKU_DIR/repo_path"

# Install dependencies
echo "Installing dependencies..."
if [ -n "$PREFIX" ]; then
    # In Termux, we try multiple names as mirrors vary
    pkg install -y python-requests python-rich 2>/dev/null
    pip install requests rich --break-system-packages 2>/dev/null
else
    # Standard Linux
    pip install requests rich --break-system-packages 2>/dev/null || pip install requests rich
fi

# Create the goku command
echo "Creating executable..."
cat > "$PREFIX_BIN/goku" <<EOF
#!/bin/bash
export PYTHONPATH="\$HOME/.goku:\$PYTHONPATH"
python3 -m goku.cli "\$@"
EOF

chmod +x "$PREFIX_BIN/goku"

echo "------------------------------------------------"
echo "✅ Goku installed successfully!"
if [[ ":$PATH:" != *":$PREFIX_BIN:"* ]]; then
    echo "⚠️  Note: $PREFIX_BIN is not in your PATH. Please add it."
fi
echo "Type 'goku' from any directory to start."
echo "Type 'goku setup' to install offline support."
echo "------------------------------------------------"
