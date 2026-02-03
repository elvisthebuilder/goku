#!/bin/bash

# Goku Termux Agent Installer (Client only)
GOKU_DIR="$HOME/.goku-agent"
BIN_DIR="$HOME/.local/bin"

echo "🐉 Installing Goku AI Agent Client..."

# 1. Install dependencies
echo "Installing system dependencies..."
pkg update && pkg install -y python python-pip git 

# 2. Setup directory
mkdir -p "$GOKU_DIR"
mkdir -p "$BIN_DIR"

# 3. Clone or copy files
# In a real install, we'd clone from GitHub
# For now we assume we are in the repo
cp -r client "$GOKU_DIR/"
cp requirements.txt "$GOKU_DIR/"

# 4. Install python dependencies
echo "Installing Python requirements..."
pip install -r "$GOKU_DIR/requirements.txt" --break-system-packages

# 5. Create executable
echo "Creating goku command..."
cat > "$BIN_DIR/goku" <<EOF
#!/bin/bash
export PYTHONPATH="\$HOME/.goku-agent:\$PYTHONPATH"
python3 \$HOME/.goku-agent/client/app.py "\$@"
EOF

chmod +x "$BIN_DIR/goku"

echo "------------------------------------------------"
echo "✅ Goku Client installed successfully!"
echo "Make sure $BIN_DIR is in your PATH."
echo "Type 'goku' to start."
echo "------------------------------------------------"
