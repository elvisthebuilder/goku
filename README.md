# Goku Termux AI Agent

`goku` is a production-ready hybrid AI agent designed specifically for Termux. It works online (HuggingFace API) and offline (llama.cpp) to ensure you always have an AI companion in your pocket.

## Features

- **Hybrid Mode**: Seamlessly switch between high-performance Mistral online and private Qwen offline models.
- **Rich UI**: Beautiful terminal interface with markdown support and syntax highlighting.
- **Failover**: Automatically prompts to switch to offline mode if the internet is down.
- **Persistent History**: Maintain context during your chat session.

## 🚀 Quick Install

Run this command in Termux:

```bash
git clone https://github.com/elvisthebuilder/goku-termux-agent.git && cd goku-termux-agent && bash install.sh
```

After installation, just type:
```bash
goku
```
from any folder!

## 🔄 Updating

If you already have Goku installed and want the latest features:

```bash
cd goku-termux-agent
git pull
bash install.sh
```

To use goku without internet, you need to download the model and build `llama.cpp`:

```bash
goku setup
```
*Note: This will download a ~1GB model and build binaries. Ensure you have ~2GB free space.*

## Usage

Start the agent:
```bash
goku
```

### Commands
- `/mode online`: Use HuggingFace API (Default)
- `/mode offline`: Use local `llama.cpp`
- `/clear`: Clear chat history
- `/retry`: Retry last query
- `/help`: Show commands
- `/exit`: Exit the agent

## Configuration

You can set an optional HuggingFace token to avoid rate limits:
```bash
export HF_TOKEN="your_token_here"
```

## License
MIT
