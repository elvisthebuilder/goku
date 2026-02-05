
import sys
import os
from pathlib import Path

# Mock config
class Config:
    HOME = Path.home()
    GOKU_DIR = HOME / ".goku"
    BIN_DIR = GOKU_DIR / "bin"
    LLAMA_CPP_BIN = BIN_DIR / "llama-cli"
    MODELS_DIR = GOKU_DIR / "models"
    MODEL_PATH = MODELS_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"

config = Config()

SYSTEM_PROMPT = "You are Goku..."
prompt = "hi"

cmd = [
    str(config.LLAMA_CPP_BIN),
    "-m", str(config.MODEL_PATH),
    "-p", f"{SYSTEM_PROMPT}\nUser: {prompt}\nAssistant:",
    "-n", "512",
    "--ctx-size", "2048",
    "--log-disable",
    "--no-display-prompt"
]

print(f"Command: {' '.join(cmd)}")
