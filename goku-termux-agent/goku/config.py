import os
import json
from pathlib import Path

# Paths
HOME = Path.home()
GOKU_DIR = HOME / ".goku"
MODELS_DIR = GOKU_DIR / "models"
BIN_DIR = GOKU_DIR / "bin"
LLAMA_CPP_BIN = BIN_DIR / "llama-cli"

# Online Configuration: Providers and Models
CONFIG_FILE = GOKU_DIR / "config.json"

PROVIDERS = {
    "huggingface": {
        "url": "https://router.huggingface.co/v1/chat/completions",
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "token_env": "HF_TOKEN"
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "token_env": "OPENAI_API_KEY"
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "model": "claude-3-5-sonnet-20240620",
        "token_env": "ANTHROPIC_API_KEY"
    },
    "ollama": {
        "url": "https://ollama.com/api/generate",
        "model": "qwen3-coder:480b",
        "token_env": "OLLAMA_API_KEY"
    },
    "github": {
        "url": "https://models.github.ai/inference/chat/completions",
        "model": "gpt-4o",
        "token_env": "GITHUB_TOKEN"
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-1.5-flash",
        "token_env": "GEMINI_API_KEY"
    }
}



DEFAULT_PROVIDER = "huggingface"

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(data):
    GOKU_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_active_provider():
    return load_config().get("active_provider", DEFAULT_PROVIDER)

def set_active_provider(name):
    if name in PROVIDERS:
        cfg = load_config()
        cfg["active_provider"] = name
        save_config(cfg)
        return True
    return False

def get_token(provider=None):
    if not provider:
        provider = get_active_provider()
    
    # Check config file
    cfg = load_config()
    tokens = cfg.get("tokens", {})
    if provider in tokens:
        return tokens[provider]
    
    # Check old hf_token key for backward compatibility
    if provider == "huggingface" and cfg.get("hf_token"):
        return cfg.get("hf_token")

    # Check env var
    env_var = PROVIDERS.get(provider, {}).get("token_env")
    if env_var:
        return os.getenv(env_var)
    return None

def save_token(token, provider=None):
    if not provider:
        provider = get_active_provider()
    
    cfg = load_config()
    tokens = cfg.get("tokens", {})
    tokens[provider] = token
    cfg["tokens"] = tokens
    save_config(cfg)

def save_url(url, provider=None):
    if not provider:
        provider = get_active_provider()
    
    cfg = load_config()
    urls = cfg.get("urls", {})
    urls[provider] = url
    cfg["urls"] = urls
    save_config(cfg)
    
    # Update current session
    if provider in PROVIDERS:
        PROVIDERS[provider]["url"] = url

def save_model(model, provider=None):
    if not provider:
        provider = get_active_provider()
    
    cfg = load_config()
    models = cfg.get("models", {})
    models[provider] = model
    cfg["models"] = models
    save_config(cfg)
    
    # Update current session
    if provider in PROVIDERS:
        PROVIDERS[provider]["model"] = model

# Backward compatibility
# Load saved configuration overrides
_cfg = load_config()
_saved_models = _cfg.get("models", {})
for _p, _m in _saved_models.items():
    if _p in PROVIDERS:
        PROVIDERS[_p]["model"] = _m

_saved_urls = _cfg.get("urls", {})
for _p, _u in _saved_urls.items():
    if _p in PROVIDERS:
        PROVIDERS[_p]["url"] = _u

HF_TOKEN = get_token("huggingface")
DEFAULT_HF_MODEL = PROVIDERS["huggingface"]["model"]

# Search Providers
SEARCH_PROVIDERS = {
    "brave": {
        "token_env": "BRAVE_API_KEY",
        "description": "Brave Search API"
    },
    "google": {
        "token_env": "GOOGLE_API_KEY", 
        "description": "Google Custom Search API"
    },
    "bing": {
        "token_env": "BING_SUBSCRIPTION_KEY",
        "description": "Bing Web Search API"
    },
    "duckduckgo": {
        "token_env": None,
        "description": "DuckDuckGo (No key required)"
    }
}
DEFAULT_SEARCH_PROVIDER = "brave"

def get_active_search_provider():
    return load_config().get("active_search_provider", DEFAULT_SEARCH_PROVIDER)

def set_active_search_provider(name):
    if name in SEARCH_PROVIDERS:
        cfg = load_config()
        cfg["active_search_provider"] = name
        save_config(cfg)
        return True
    return False

def get_search_token(provider=None):
    if not provider:
        provider = get_active_search_provider()
        
    cfg = load_config()
    tokens = cfg.get("tokens", {})
    if provider in tokens:
        return tokens[provider]
        
    # Check env var
    env_var = SEARCH_PROVIDERS.get(provider, {}).get("token_env")
    if env_var:
        return os.getenv(env_var)
    return None

def get_brave_key():
    return get_search_token("brave")

def load_mcp_servers():
    """Load MCP server configurations."""
    
    # Determine server path: Check local dev first, then installed path
    script_dir = Path(__file__).parent.parent # goku/config.py -> goku/
    dev_server_path = script_dir / "servers" / "internet.py"
    
    final_server_path = os.path.join(str(GOKU_DIR), "goku/servers/internet.py")
    if dev_server_path.exists():
        final_server_path = str(dev_server_path)

    defaults = {
        "internet": {
            "command": "python3",
            "args": [final_server_path],
            "env": {"PYTHONPATH": str(script_dir.parent)} # Point to repo root
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
SHOW_THOUGHTS = True
