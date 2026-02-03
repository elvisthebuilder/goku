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
        provider_name = config.get_active_provider()
        provider_cfg = config.PROVIDERS.get(provider_name, config.PROVIDERS[config.DEFAULT_PROVIDER])
        
        url = provider_cfg["url"]
        token = config.get_token(provider_name)
        
        headers = {"Content-Type": "application/json"}
        if token:
            if provider_name == "anthropic":
                headers["x-api-key"] = token
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {token}"
        
        # Merge native tools with MCP tools
        all_tools = goku_tools.TOOLS_SCHEMA + self.mcp_tools
        
        # Handle different payload formats
        if provider_name == "anthropic":
            # Anthropic Messages API format
            anthropic_messages, system_msg = self._convert_messages_to_anthropic(messages)
            payload = {
                "model": provider_cfg["model"],
                "max_tokens": 2048,
                "messages": anthropic_messages,
                "system": system_msg,
                "tools": self._convert_tools_to_anthropic(all_tools) if all_tools else None,
            }
        else:
            # OpenAI / HF / GitHub / Ollama format
            payload = {
                "model": provider_cfg["model"],
                "messages": messages,
                "max_tokens": 2048,
                "tools": all_tools if all_tools else None,
                "tool_choice": "auto" if all_tools else None,
                "stream": False
            }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            res_data = response.json()
            
            # Normalize response format
            if provider_name == "anthropic":
                return self._normalize_anthropic_response(res_data)
            return res_data
            
        except requests.exceptions.HTTPError as e:
            error_details = ""
            try:
                error_json = response.json()
                error_details = f": {error_json.get('error', {}).get('message', str(error_json))}"
            except:
                error_details = f": {response.text[:200]}"
            raise Exception(f"Online API error ({provider_name}): {e}{error_details}")
        except Exception as e:
            raise Exception(f"Online API error ({provider_name}): {str(e)}")

    def _convert_messages_to_anthropic(self, messages):
        """Convert OpenAI standard messages to Anthropic's specific format."""
        anthropic_messages = []
        system_msg = None
        
        for m in messages:
            role = m["role"]
            content = m.get("content", "")
            
            if role == "system":
                system_msg = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                # Convert tool_calls if present
                if "tool_calls" in m:
                    anthropic_content = []
                    if content and content != "...":
                        anthropic_content.append({"type": "text", "text": content})
                    
                    for tc in m["tool_calls"]:
                        anthropic_content.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"])
                        })
                    anthropic_messages.append({"role": "assistant", "content": anthropic_content})
                else:
                    anthropic_messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                # Anthropic groups tool results into a USER message following the assistant's tool_use
                # If the previous message was a user message and had tool_results, append to it.
                # Otherwise, create a new user message.
                result_block = {
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": content
                }
                
                if anthropic_messages and anthropic_messages[-1]["role"] == "user" and isinstance(anthropic_messages[-1]["content"], list):
                     anthropic_messages[-1]["content"].append(result_block)
                else:
                     anthropic_messages.append({"role": "user", "content": [result_block]})
                     
        return anthropic_messages, system_msg

    def _convert_tools_to_anthropic(self, tools):
        """Convert OpenAI tool schema to Anthropic tool schema."""
        anthropic_tools = []
        for t in tools:
            if t["type"] == "function":
                f = t["function"]
                anthropic_tools.append({
                    "name": f["name"],
                    "description": f["description"],
                    "input_schema": f["parameters"]
                })
        return anthropic_tools

    def _normalize_anthropic_response(self, data):
        """Convert Anthropic response to OpenAI-compatible format."""
        # data["content"] is a list of blocks
        text_content = ""
        tool_calls = []
        
        for block in data.get("content", []):
            if block["type"] == "text":
                text_content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"])
                    }
                })
        
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": text_content,
                    "tool_calls": tool_calls if tool_calls else None
                }
            }]
        }

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
1. **Explore**: Use tools to understand the codebase.
2. **Plan**: Explain your approach before editing.
3. **Edit**: Use provided tools for all file operations.
4. **Interact**: Be concise. NEVER output raw function/tool tags or JSON in your response text. Use the official tool-calling API.

Always prioritize clarity and correctness. No preamble, just results or tool calls.
"""

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

            # Persist user prompt immediately to prevent context loss on failure
            self.history.append({"role": "user", "content": prompt})
            
            # Prepare this turn's ongoing messages (not yet in permanent history)
            turn_messages = []
            
            while True:
                # Construct combined messages for the API call
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
                    # Strip any raw function tags or "name, {args}" patterns leaky models produce
                    # 1. Official-looking tags
                    content = re.sub(r"<function.*?>.*?(</function>|(?=<|$))", "", content, flags=re.DOTALL).strip()
                    # 2. Pattern: name, {"args": ...}
                    content = re.sub(r"\w+,\s*\{.*?\}(?=(\n|$))", "", content, flags=re.DOTALL).strip()
                    # 3. Final leaky checks
                    if "<function" in content:
                        content = content.split("<function")[0].strip()
                
                # IMPORTANT: Ensure content is never truly empty for the assistant
                message["content"] = content if content else "..."
                
                # Standardize assistant message
                clean_msg = {
                    "role": "assistant",
                    "content": message["content"]
                }
                
                if "tool_calls" in message:
                    # REPAIR: Fix misinterpreted tool calls (e.g. Router concatenates name and args)
                    fixed_tool_calls = []
                    for tc in message["tool_calls"]:
                         name = tc["function"].get("name", "")
                         args = tc["function"].get("arguments", "{}")
                         
                         if "," in name and "{" in name:
                              # Case: name="search_web,{\"query\": ...}"
                              parts = name.split(",", 1)
                              name = parts[0].strip()
                              if args in [None, "null", "", "{}"]:
                                   args = parts[1].strip()
                         
                         tc["function"]["name"] = name
                         tc["function"]["arguments"] = args if args not in [None, "null", ""] else "{}"
                         fixed_tool_calls.append(tc)
                    
                    clean_msg["tool_calls"] = fixed_tool_calls

                # Add assistant message to the turn messages
                turn_messages.append(clean_msg)

                if not message.get("tool_calls"):
                    final_text = content.strip() if content else "..."
                    # Turn complete! Save everything to permanent history
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
