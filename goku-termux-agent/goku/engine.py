import requests
import subprocess
import json
import os
import re
from . import config

from . import tools as goku_tools

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
            "max_tokens": 2048,
            "tools": all_tools,
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

    SYSTEM_PROMPT = """You are Goku, a powerful AI Coding Assistant.

### PERSONA:
You are an expert software engineer and helpful friend. You write clean, modular, and documented code.
You are capable of full-stack development, debugging, and system administration.

### TOOLS:
- `search_web(query)`: Search the internet for real-time information.
- `create_file(path, content)`: Create new files.
- `edit_file(path, old_text, new_text)`: Edit existing files safely.
- `search_code(directory, query)`: Search for code patterns.
- `list_files(directory)`: Explore directories.
- `read_file(path)`: Read file content.
- `run_command(cmd)`: Run shell commands.
- Plus any connected MCP tools (use them when relevant!)

### CRITICAL RULES:

**1. Coding Workflow:**
   - **Explore**: Use `list_files` and `search_code` to understand the codebase first.
   - **Plan**: Think about the changes before making them.
   - **Edit**: Use `edit_file` for small changes. Use `create_file` for new modules.
   - **Verify**: Always check your work (e.g., run the script or cat the file).

**2. Tool Usage:**
   - Prefer `edit_file` over `run_command` for editing code (it's safer).
   - Use `run_command` for execution, testing, and git operations.
   - Always ask permission before destructive actions or running commands.

**3. Interaction:**
   - Be concise but helpful.
   - If a request is vague, ask clarifying questions.
   - When writing code, return the full file content if creating it, or the specific diff if editing.
   - NEVER include raw internal tool/function calls (like <function=...>) in your response text. Use the proper tool call API instead.

### EXAMPLES:
User: "Fix the bug in main.py"
You: "I'll check main.py first." -> Call `read_file`
User: "Add a greet function."
You: "I'll add it using edit_file." -> Call `edit_file` with unique context string."""

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
            # Prepare initial messages with the system prompt
            current_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            # Limit history to prevent context overflow and reduce costs
            for msg in self.history[-config.SESSION_MEMORY_MAX:]:
                current_messages.append(msg)
            current_messages.append({"role": "user", "content": prompt})

            while True:
                # Call online API with current messages
                loop = asyncio.get_event_loop()
                res_json = await loop.run_in_executor(None, self._get_online_response, current_messages)
                
                message = res_json["choices"][0]["message"]
                
                # Check for and display thoughts/reasoning
                thought = message.get("reasoning_content") or message.get("thought") or message.get("reasoning")
                content = message.get("content", "")
                
                import re
                # Strip internal thoughts
                if not thought and content:
                    for tag in ["thought", "reasoning"]:
                        match = re.search(f"<{tag}>(.*?)</{tag}>", content, re.DOTALL | re.IGNORECASE)
                        if match:
                            thought = match.group(1).strip()
                            content = content.replace(match.group(0), "").strip()
                            break

                # Strip internal function calls from text (sometimes models echo them)
                if content:
                    # Catch both <function=name>{args} and <function call: name>{args}
                    content = re.sub(r"<function=.*?>.*?(?=(<|$))", "", content, flags=re.DOTALL).strip()
                    content = re.sub(r"<function call:.*?>.*?(?=(<|$))", "", content, flags=re.DOTALL).strip()
                    # Final cleanup if anything leaky remains
                    if "<function" in content:
                        content = content.split("<function")[0].strip()
                
                # IMPORTANT: Sync cleaned content back to message object so history is clean
                # Use empty string instead of None (more compatible)
                message["content"] = content if content else ""
                
                # Standardize assistant message for history
                clean_msg = {
                    "role": "assistant",
                    "content": message["content"]
                }
                if "tool_calls" in message:
                    clean_msg["tool_calls"] = message["tool_calls"]
                
                if not message.get("tool_calls"):
                    final_text = content.strip() if content else ""
                    # Record the full turn in history
                    self.history.append({"role": "user", "content": prompt})
                    self.history.append({"role": "assistant", "content": final_text})
                    return final_text, None

                # Append assistant tool-call message
                current_messages.append(clean_msg)
                
                # Execute each tool call and append tool result
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    # Handle potential malformed arguments
                    try:
                        args_str = tool_call["function"].get("arguments", "{}")
                        func_args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        func_args = {}
                    
                    from . import ui
                    if status_obj:
                        status_obj.stop()
                    
                    ui.show_tool_execution(func_name, func_args)
                    
                    # Tool execution routing
                    if "__" in func_name:
                        # MCP Tool
                        server_name = func_name.split("__")[0]
                        if server_name in self.mcp_clients:
                            result = await self.mcp_clients[server_name].call_tool(func_name, func_args)
                        else:
                            result = f"Error: MCP server '{server_name}' not found."
                    else:
                        # Native Tool
                        result = goku_tools.execute_tool(func_name, func_args)
                    
                    # Tool response must be role: tool
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": str(result)
                    })
                    
                    if status_obj:
                        status_obj.start()
                        status_obj.update("[bold green]Thinking...")

        except Exception as e:
            return None, str(e)

    def generate(self, prompt, status_obj=None):
        """Wrapper to run async generate in sync context if needed, but CLI should be async."""
        return asyncio.run(self.generate_async(prompt, status_obj))
