import requests
import subprocess
import json
import os
import re
from . import config

try:
    from . import mcp_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    
import asyncio

class GokuEngine:
    def __init__(self):
        self.mode = "online"
        self.history = []
        self.mcp_clients = {}
        self.mcp_tools = []
        
        # Initialize MCP clients if available
        if MCP_AVAILABLE:
            for name, cfg in config.MCP_SERVERS.items():
                if hasattr(mcp_client, 'MCPClient'):
                    client = mcp_client.MCPClient(name, cfg.get("command"), cfg.get("args", []), cfg.get("env"))
                    self.mcp_clients[name] = client

    async def initialize_mcp(self):
        """Connect to MCP servers and fetch tools."""
        for name, client in self.mcp_clients.items():
            if await client.connect():
                tools = await client.list_tools_schema()
                self.mcp_tools.extend(tools)
                # ui.console.print(f"[dim]Connected to MCP server: {name}[/dim]")

    def set_mode(self, mode):
        if mode in ["online", "offline"]:
            self.mode = mode
            return True
        return False

    def clear_history(self):
        self.history = []

    def _get_online_response(self, messages):
        headers = {"Content-Type": "application/json"}
        if config.HF_TOKEN:
            headers["Authorization"] = f"Bearer {config.HF_TOKEN}"
        # New HF Router API (OpenAI-compatible)
        API_URL = "https://router.huggingface.co/v1/chat/completions"
        
        # Merge native tools with MCP tools
        all_tools = goku_tools.TOOLS_SCHEMA + self.mcp_tools
        
        payload = {
            "model": config.DEFAULT_HF_MODEL,
            "messages": messages,
            "max_tokens": 1024,
            "tools": all_tools,
            "tool_choice": "auto",
            "stream": False
        }

        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Try to get more details from the error response
            error_details = ""
            try:
                error_json = response.json()
                error_details = f": {error_json.get('error', {}).get('message', str(error_json))}"
            except:
                error_details = f": {response.text[:200]}"
            raise Exception(f"Online API error: {e}{error_details}")
        except Exception as e:
            raise Exception(f"Online API error: {str(e)}")

    def _get_offline_response(self, prompt):
        if not config.LLAMA_CPP_BIN.exists():
            raise FileNotFoundError("llama.cpp binary not found. Run 'goku setup' to install offline support.")
        if not config.MODEL_PATH.exists():
            raise FileNotFoundError("Model file not found. Run 'goku setup' to download the model.")

        full_prompt = ""
        for msg in self.history[-config.SESSION_MEMORY_MAX:]:
             full_prompt += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
        full_prompt += f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

        cmd = [
            str(config.LLAMA_CPP_BIN),
            "-m", str(config.MODEL_PATH),
            "-p", f"{self.SYSTEM_PROMPT}\nUser: {prompt}\nAssistant:",
            "-n", "512",
            "--ctx-size", "2048"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise Exception(f"Offline error: {e.stderr}")

    SYSTEM_PROMPT = """You are Goku, a friendly AI assistant.

### PERSONALITY:
Chat naturally like a helpful friend. Be warm, casual, and conversational.

### EXAMPLES:
User: "hi" → You: "Hey! What's up?"
User: "how are you?" → You: "I'm doing great! How about you?"
User: "who are you?" → You: "I'm Goku, your AI assistant. I can help with files, commands, and general questions. What do you need?"

### TOOLS YOU HAVE:
- `list_files(directory)` - Browse folders
- `read_file(file_path)` - Read files
- `run_command(command)` - Execute terminal commands
- `get_os_info()` - Check system info
- Plus any connected MCP tools (use them when relevant!)

### CRITICAL RULES:

**1. NEVER use tools without asking first**
   - For greetings/chat: Just respond naturally, DON'T use any tools
   - For questions: Answer with your knowledge, OFFER tools if helpful
   - For actions: Ask clarifying questions, then ask "May I proceed?"

**2. Conversation Flow for Actions:**
   User: "Create a folder"
   You: "Sure! What should I name it?"
   User: "test"
   You: "I'll create a folder called 'test' in the current directory. Should I go ahead?"
   User: "Yes"
   You: *NOW use run_command*

**3. Keep responses brief and natural**
   - Don't list all your capabilities unless asked
   - Don't mention function names like `get_os_info` in casual chat
   - Sound human, not like a manual"""

    async def generate_async(self, prompt, status_obj=None):
        """Async version of generate to support MCP."""
        try:
            if self.mode == "offline":
                # Wrap synchronous offline call
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self._get_offline_response, prompt)
                self.history.append({"role": "user", "content": prompt})
                self.history.append({"role": "assistant", "content": response})
                return response, None

            # Online Agentic Loop
            current_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            for msg in self.history[-config.SESSION_MEMORY_MAX:]:
                current_messages.append(msg)
            current_messages.append({"role": "user", "content": prompt})

            while True:
                # Wrap synchronous request
                loop = asyncio.get_event_loop()
                res_json = await loop.run_in_executor(None, self._get_online_response, current_messages)
                
                message = res_json["choices"][0]["message"]
                
                # Check for and display thoughts/reasoning
                thought = message.get("reasoning_content") or message.get("thought") or message.get("reasoning")
                content = message.get("content", "")
                
                if not thought and content:
                    import re
                    for tag in ["thought", "reasoning"]:
                        match = re.search(f"<{tag}>(.*?)</{tag}>", content, re.DOTALL | re.IGNORECASE)
                        if match:
                            thought = match.group(1).strip()
                            content = content.replace(match.group(0), "").strip()
                            break

                # Thought is captured but not displayed to keep UI clean

                if "tool_calls" not in message or not message["tool_calls"]:
                    final_text = content.strip()
                    self.history.append({"role": "user", "content": prompt})
                    self.history.append({"role": "assistant", "content": final_text})
                    return final_text, None

                # Handle tool calls
                current_messages.append(message)
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    func_args = json.loads(tool_call["function"]["arguments"])
                    
                    from . import ui
                    if status_obj:
                        status_obj.stop()
                    
                    ui.show_tool_execution(func_name, func_args)
                    
                    # Execute tool - check if it's native or MCP
                    if "__" in func_name:
                        # MCP Tool (server__tool)
                        server_name = func_name.split("__")[0]
                        if server_name in self.mcp_clients:
                            result = await self.mcp_clients[server_name].call_tool(func_name, func_args)
                        else:
                            result = f"Error: MCP server '{server_name}' not found."
                    else:
                        # Native tool
                        result = goku_tools.execute_tool(func_name, func_args)
                    
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": func_name,
                        "content": result
                    })
                    
                    if status_obj:
                        status_obj.start()
                        status_obj.update("[bold green]Thinking...")

        except Exception as e:
            return None, str(e)

    def generate(self, prompt, status_obj=None):
        """Wrapper to run async generate in sync context if needed, but CLI should be async."""
        return asyncio.run(self.generate_async(prompt, status_obj))
