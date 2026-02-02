import os
from pathlib import Path

# Paths
HOME = Path.home()
GOKU_DIR = HOME / ".goku"
MODELS_DIR = GOKU_DIR / "models"
BIN_DIR = GOKU_DIR / "bin"
LLAMA_CPP_BIN = BIN_DIR / "llama-cli"

# Online Configuration
DEFAULT_HF_MODEL = "Qwen/Qwen2.5-1.5B-Instruct" 
HF_TOKEN = os.getenv("HF_TOKEN")

# Offline Configuration
DEFAULT_GGUF_MODEL = "Qwen2.5-1.5B-Instruct-GGUF"
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_PATH = MODELS_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"

# Settings
SESSION_MEMORY_MAX = 10
