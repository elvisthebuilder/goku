import os
import json
from pathlib import Path

# Paths
HOME = Path.home()
GOKU_DIR = HOME / ".goku"
MODELS_DIR = GOKU_DIR / "models"
BIN_DIR = GOKU_DIR / "bin"
LLAMA_CPP_BIN = BIN_DIR / "llama-cli"

# Online Configuration
DEFAULT_HF_MODEL = "microsoft/Phi-3.5-mini-instruct" 
CONFIG_FILE = GOKU_DIR / "config.json"

def load_token():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f).get("hf_token")
        except:
            pass
    return os.getenv("HF_TOKEN")

def save_token(token):
    GOKU_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"hf_token": token}, f)

HF_TOKEN = load_token()

# Offline Configuration
DEFAULT_GGUF_MODEL = "Qwen2.5-1.5B-Instruct-GGUF"
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_PATH = MODELS_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"

# Settings
SESSION_MEMORY_MAX = 10
