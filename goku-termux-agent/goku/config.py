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
DEFAULT_HF_MODEL = "meta-llama/Llama-3.3-70B-Instruct" 
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

def load_mcp_servers():
    """Load MCP server configurations."""
    defaults = {
        "internet": {
            "command": "python3",
            "args": [os.path.join(str(GOKU_DIR), "goku/servers/internet.py")],
            "env": {"PYTHONPATH": str(GOKU_DIR)}
        }
    }
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                servers = data.get("mcp_servers", {})
                if not servers:
                    return defaults
                return servers
        except:
            pass
    return defaults

def save_mcp_server(name, config):
    """Save a new MCP server configuration."""
    GOKU_DIR.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                current_data = json.load(f)
        except:
            pass
    
    servers = current_data.get("mcp_servers", {})
    servers[name] = config
    current_data["mcp_servers"] = servers
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(current_data, f, indent=4)

def remove_mcp_server(name):
    """Remove an MCP server configuration."""
    if not CONFIG_FILE.exists():
        return False
        
    try:
        with open(CONFIG_FILE, 'r') as f:
            current_data = json.load(f)
    except:
        return False
        
    servers = current_data.get("mcp_servers", {})
    if name in servers:
        del servers[name]
        current_data["mcp_servers"] = servers
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current_data, f, indent=4)
        return True
    return False

MCP_SERVERS = load_mcp_servers()

# Offline Configuration
DEFAULT_GGUF_MODEL = "Qwen2.5-1.5B-Instruct-GGUF"
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_PATH = MODELS_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"

# Settings
SESSION_MEMORY_MAX = 10
