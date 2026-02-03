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

    SYSTEM_PROMPT = """You are Goku, a powerful AI Coding Assistant.

### PERSONA:
You are an expert software engineer and helpful friend. You write clean, modular, and documented code.
You are capable of full-stack development, debugging, and system administration.

### CRITICAL RULES:
1. **Explore**: Use tools to understand the codebase before making changes.
2. **Plan**: Think and explain your approach before editing.
3. **Edit**: Use the provided file editing tools for efficiency and safety.
4. **Interact**: Be concise, helpful, and never output raw internal tool tags. Use the official tool-calling API.

Always prioritize clarity and correctness."""

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

            # Prepare this turn's messages
            turn_messages = [{"role": "user", "content": prompt}]
            
            while True:
                # Merge history with the current ongoing turn
                api_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
                api_messages += self.history[-config.SESSION_MEMORY_MAX:]
                api_messages += turn_messages

                # Call online API
                loop = asyncio.get_event_loop()
                res_json = await loop.run_in_executor(None, self._get_online_response, api_messages)
                
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
                
                # IMPORTANT: Ensure content is never truly empty for the assistant
                # (Some routers like HF fail on {"role": "assistant", "content": ""})
                if not content and not message.get("tool_calls"):
                    content = "..." # Minimal visible content
                
                message["content"] = content
                
                # Standardize assistant message for this turn's logical history
                clean_msg = {
                    "role": "assistant",
                    "content": message["content"] if message["content"] else ""
                }
                if "tool_calls" in message:
                    clean_msg["tool_calls"] = message["tool_calls"]
                    # Fix malformed arguments
                    for tc in clean_msg["tool_calls"]:
                         if "function" in tc:
                              args = tc["function"].get("arguments")
                              if args is None or args == "null":
                                   tc["function"]["arguments"] = "{}"

                # Add assistant message to the current turn
                turn_messages.append(clean_msg)

                if not message.get("tool_calls"):
                    final_text = content.strip() if content else "..."
                    # Turn complete! Persist the entire turn to permanent history
                    self.history.extend(turn_messages)
                    return final_text, None
                
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
                    turn_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": func_name,
                        "content": str(result) if result else "Tool execution produced no output."
                    })
                    
                    if status_obj:
                        status_obj.start()
                        status_obj.update("[bold green]Thinking...")

        except Exception as e:
            return None, str(e)

    def generate(self, prompt, status_obj=None):
        """Wrapper to run async generate in sync context if needed, but CLI should be async."""
        return asyncio.run(self.generate_async(prompt, status_obj))
