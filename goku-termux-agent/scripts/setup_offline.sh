#!/bin/bash

# Configuration
GOKU_DIR="$HOME/.goku"
BIN_DIR="$GOKU_DIR/bin"
MODELS_DIR="$GOKU_DIR/models"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_FILE="$MODELS_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"

echo "=== Goku Offline Setup ==="

# Install dependencies
echo "[1/4] Installing system dependencies..."
pkg install -y clang make cmake git python libopenblas 

# Build llama.cpp
echo "[2/4] Building llama.cpp..."
mkdir -p "$GOKU_DIR/src"
cd "$GOKU_DIR/src"
if [ ! -d "llama.cpp" ]; then
    git clone https://github.com/ggerganov/llama.cpp
fi
cd llama.cpp
mkdir -p build
cd build
cmake .. -DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS
make -j$(nproc) llama-cli

mkdir -p "$BIN_DIR"
cp bin/llama-cli "$BIN_DIR/"

# Download model
echo "[3/4] Downloading model (1.1GB)..."
mkdir -p "$MODELS_DIR"
if [ ! -f "$MODEL_FILE" ]; then
    curl -L "$MODEL_URL" -o "$MODEL_FILE"
fi

echo "[4/4] Done!"
echo "Offline support is now ready."
