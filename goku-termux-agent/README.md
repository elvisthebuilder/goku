# Goku Termux AI Agent 🐉

`goku` is a powerful, production-ready hybrid AI agent designed specifically for Termux (and standard Linux). It integrates **LangChain** for robust prompt management and **MCP (Model Context Protocol)** for extensible tool use.

## Features

- **🧠 LangChain Powered**: Superior prompt orchestration and conversational reasoning.
- **🛠️ Full Tool-Use**: Capable of searching the web, searching code, reading/writing files, and running shell commands.
- **🔌 MCP Support**: Easily extend capabilities by connecting to external MCP servers.
- **🌓 Hybrid Mode**: Seamlessly switch between high-performance cloud models (Anthropic, OpenAI, Ollama) and private local models.
- **💎 Premium UI**: Beautiful terminal interface using `rich` with markdown support and syntax highlighting.
- **🚀 One-Command Install**: Installs globally using a hardened bash script.

## 🚀 Quick Install

Run this command:

```bash
git clone https://github.com/elvisthebuilder/goku-termux-agent.git && cd goku-termux-agent && bash install.sh
```

After installation, just type:
```bash
goku
```

## 🔄 Updating

To get the latest engine improvements:

```bash
cd goku-termux-agent
git pull
bash install.sh
```

## 📶 Offline Support

To use goku without internet, download the model and build `llama.cpp`:

```bash
goku setup
```
*Note: This downloads a 1-2GB model and builds binaries. Ensure you have sufficient free space.*

## Usage

Start the agent:
```bash
goku
```

### ⌨️ Slash Commands
Goku features a rich set of control commands to customize your experience:

- **Mode & Environment**
    - `/mode <online|offline>`: Switch between cloud models and local execution.
    - `/clear`: Clear chat history and refresh the UI.
    - `/retry`: Repeat the last query (useful if an API failed).
    - `/help`: Show descriptions of all available commands.
    - `/exit`: Exit the agent.

- **AI Provider & Model Management**
    - `/provider [name]`: List available providers or switch (e.g., `openai`, `anthropic`, `ollama`).
    - `/models`: List all available models for your active provider.
    - `/model <name|number>`: Quickly set your active model.
    - `/url [url]`: View or set a custom API endpoint (e.g., for local Ollama instances).

- **Tools & MCP**
    - `/search [name]`: List or switch the web search engine (DuckDuckGo, Brave, Bing, etc.).
    - `/mcp <list|reload>`: Manage connected Model Context Protocol servers.
    - `/token [provider] [key]`: Securely save API keys for models or search tools. Type `/token help` for a guide.

- **System**
    - `/setup`: Run the offline setup wizard.
    - `/update`: Check for git updates and re-install automatically.

## Configuration

Goku stores its config in `~/.goku/config.json`. You can also set tokens via environment variables like `HF_TOKEN`, `OPENAI_API_KEY`, etc.

## License
MIT
