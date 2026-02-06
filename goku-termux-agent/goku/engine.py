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

    async def close(self):
        """Disconnect from all MCP servers."""
        for client in self.mcp_clients.values():
            try:
                await client.close()
            except Exception:
                pass

    def set_mode(self, mode):
        if mode in ["online", "offline"]:
            self.mode = mode
            return True
        return False

    def clear_history(self):
        self.history = []

    def list_models(self):
        """Fetch available models from the active provider."""
        provider_name = config.get_active_provider()
        provider_cfg = config.PROVIDERS.get(provider_name, config.PROVIDERS[config.DEFAULT_PROVIDER])
        
        # Determine models endpoint
        if provider_name == "anthropic":
            return ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        
        if provider_name == "ollama":
            # If it's a known ollama endpoint like /api/generate, use /api/tags
            if "api/generate" in provider_cfg["url"]:
                base_url = provider_cfg["url"].split("/api/generate")[0]
                url = f"{base_url}/api/tags"
            elif "v1" in provider_cfg["url"]:
                base_url = provider_cfg["url"].split("/v1")[0]
                url = f"{base_url}/api/tags" # Fallback to native for better listing
            else:
                url = f"{provider_cfg['url'].rsplit('/', 1)[0]}/tags"
        else:
            base_url = provider_cfg["url"].rsplit("/", 2)[0] # remove /chat/completions
            url = f"{base_url}/models"
        token = config.get_token(provider_name)
        
        headers = {"Content-Type": "application/json"}
        if token:
             headers["Authorization"] = f"Bearer {token}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 401:
                return [f"Error: Unauthorized (401). Please check your API key for {provider_name}."]
            if response.status_code == 404:
                return [f"Error: Models endpoint not found (404). The provider {provider_name} may not support listing models at this URL."]
            
            response.raise_for_status()
            data = response.json()
            # OpenAI format: {"data": [{"id": "model-name", ...}]}
            if "data" in data and isinstance(data["data"], list):
                models = [m["id"] for m in data["data"]]
                return sorted(models)
            # Ollama (tags) format fallback: {"models": [{"name": "...", ...}]}
            if "models" in data and isinstance(data["models"], list):
                models = [m.get("name") or m.get("id") for m in data["models"]]
                return sorted(filter(None, models))
                
            return []
        except Exception as e:
            return [f"Error fetching models: {e}"]

    def _get_langchain_prompt(self, messages, all_tools):
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        
        # Serialize tools for the model to see
        tools_instruction = ""
        if all_tools:
            tools_instruction = "\n\nAVAILABLE TOOLS:\n"
            for t in all_tools:
                tools_instruction += f"- {t['function']['name']}: {t['function']['description']}\n"
                tools_instruction += f"  Args: {json.dumps(t['function']['parameters'])}\n"
            tools_instruction += "\nTo use a tool, output a single JSON LIST in your message: [{\"id\": \"call_1\", \"function\": {\"name\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}}}]\n"
            tools_instruction += "Only use the tools listed above. If no tool is needed, respond with normal text.\n"

        lc_messages = []
        system_injected = False
        
        for m in messages:
            role = m['role'].lower()
            content = m['content']
            
            if role == "system":
                lc_messages.append(SystemMessage(content=content + tools_instruction))
                system_injected = True
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
                
        if not system_injected:
            lc_messages.insert(0, SystemMessage(content=self.SYSTEM_PROMPT + tools_instruction))
            
        return lc_messages

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
        
        # Use LangChain for message structuring
        lc_messages = self._get_langchain_prompt(messages, all_tools)

        # Handle different payload formats (still need raw HTTP for now to avoid bulky LC provider installs)
        if provider_name == "anthropic":
            # Anthropic Messages API format
            anthropic_messages = []
            system_msg = ""
            for msg in lc_messages:
                if msg.type == "system":
                    system_msg += msg.content
                elif msg.type == "human":
                    anthropic_messages.append({"role": "user", "content": msg.content})
                elif msg.type == "ai":
                    anthropic_messages.append({"role": "assistant", "content": msg.content})
            
            payload = {
                "model": provider_cfg["model"],
                "max_tokens": 2048,
                "messages": anthropic_messages,
                "system": system_msg,
                "tools": self._convert_tools_to_anthropic(all_tools) if all_tools else None,
            }
        elif "api/generate" in provider_cfg["url"]:
            # Ollama /api/generate format (Raw completion)
            prompt = ""
            for msg in lc_messages:
                role = "system" if msg.type == "system" else "user" if msg.type == "human" else "assistant"
                prompt += f"<|im_start|>{role}\n{msg.content}<|im_end|>\n"
            prompt += "<|im_start|>assistant\n"
            
            payload = {
                "model": provider_cfg["model"],
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": 4096}
            }
        else:
            # OpenAI / Chat format
            raw_messages = []
            for msg in lc_messages:
                role = "system" if msg.type == "system" else "user" if msg.type == "human" else "assistant"
                raw_messages.append({"role": role, "content": msg.content})
                
            payload = {
                "model": provider_cfg["model"],
                "messages": raw_messages,
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
            
            # Normalize Ollama /api/generate response
            if "response" in res_data and "done" in res_data:
                 return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": res_data["response"],
                            "tool_calls": None
                        }
                    }]
                }
            
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

    def _normalize_anthropic_response(self, data):
        """Convert Anthropic response to OpenAI-compatible format."""
        if not data or "content" not in data:
            return {"choices": [{"message": {"role": "assistant", "content": "...", "tool_calls": None}}]}
            
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

    def _get_offline_response(self, prompt, history=None):
        if not config.LLAMA_CPP_BIN.exists():
            raise FileNotFoundError("llama.cpp binary not found. Run 'goku setup' to install offline support.")
        if not config.MODEL_PATH.exists():
            raise FileNotFoundError("Model file not found. Run 'goku setup' to download the model.")

        full_prompt = ""
        # Use provided history or fallback to class history
        hist_msgs = history if history is not None else self.history[-config.SESSION_MEMORY_MAX:]
        
        for msg in hist_msgs:
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
            # We remove --log-disable as it sometimes causes "invalid argument: -q" on custom builds
            # and instead rely on aggressive manual filtering of stdout/stderr.
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            
            # Combine stdout and stderr for filtering as banners can leak to either
            full_output = (result.stdout + "\n" + result.stderr).strip()
            
            # If stdout is empty but we have content in stderr (like "Assistant: ...")
            if not output and "Assistant:" in full_output:
                output = full_output
            
            # 1. Extreme cleanup: Extract only what follows the final "Assistant:" marker
            if "Assistant:" in output:
                output = output.split("Assistant:")[-1].strip()
            
            # 2. Filter out llama.cpp generic banners (multi-line)
            output = re.sub(r"build\s*:\s*.*?\n", "", output)
            output = re.sub(r"model\s*:\s*.*?\n", "", output)
            output = re.sub(r"modalities\s*:\s*.*?\n", "", output)
            output = re.sub(r"system_info\s*:\s*.*?\n", "", output)
            
            # 3. Strip prompt/generation stats usually enclosed in brackets
            output = re.sub(r"\[ Prompt: .*? \]", "", output)
            output = re.sub(r"\[ Generation: .*? \]", "", output)
            
            # 4. Strip persona fragments if model echoed them
            output = re.sub(r"> You are Goku.*?\n", "", output, flags=re.DOTALL)
            output = re.sub(r"### PERSONA:.*?\n", "", output, flags=re.DOTALL)
            output = re.sub(r"### CRITICAL RULES:.*?\n", "", output, flags=re.DOTALL)
            
            return output.strip()
        except subprocess.CalledProcessError as e:
            # If it still fails, it might be a real error or the "invalid argument"
            err_msg = e.stderr.strip()
            if "invalid argument" in err_msg:
                 # Fallback attempt: basic invocation if flags are the issue
                 try:
                     fallback_cmd = [str(config.LLAMA_CPP_BIN), "-m", str(config.MODEL_PATH), "-p", prompt, "-n", "128"]
                     res = subprocess.run(fallback_cmd, capture_output=True, text=True)
                     return res.stdout.strip()
                 except:
                     pass
            raise Exception(f"Offline error: {err_msg}")

    SYSTEM_PROMPT = """You are Goku, a powerful and friendly AI Coding Assistant.

### PERSONA:
You are an expert software engineer and a helpful companion. You write clean, modular, and documented code.
You are capable of full-stack development, debugging, and system administration.
You should be conversational: if a request is ambiguous or you're unsure of the goal, ask for clarification.
If the request is clear and actionable (e.g., "Search for X", "Check file Y", "Execute command Z"), proceed directly and efficiently using your tools.

### CRITICAL RULES:
1. **Explore & Execute**: Use tools to understand the codebase and perform tasks. If a task requires external info or file ops, YOU MUST USE A TOOL.
2. **Conversational Balance**: Be direct for explicit commands. Be inquisitive for vague requests.
3. **Explicit Paths**: Always state the *full absolute path* of any file you are about to read, write, or search.
4. **User Consent**: Ask the user before creating new files or directories: "I'm about to create a file at [path], is that okay?"
5. **Interact**: Be concise. NEVER output raw function/tool tags or JSON in your response text.

### REASONING & CHAIN-OF-THOUGHT:
- **FORCED REASONING**: BEFORE you take any action or provide a final answer, you MUST enclose your internal reasoning inside <thought> tags.
- Within <thought>, analyze the intent, evaluate the plan, and outline the tool calls.

Always prioritize clarity and correctness.
"""

    async def generate_async(self, prompt, status_obj=None):
        """Async version of generate to support MCP."""
        try:
            if self.mode == "offline":
                # Use a shorter history for offline to stay snappy
                offline_history = self.history[-3:] # Only last 3 turns
                
                # Wrap synchronous offline call
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self._get_offline_response, prompt, offline_history)
                
                # REPAIR: If model echoed its instructions (common in small offline models)
                if "> You are Goku" in response:
                     response = response.split("### PERSONA:")[-1].split("### CRITICAL RULES:")[-1].strip()
                     # If still messy, try split by last known marker
                     if "Assistant:" in response:
                          response = response.split("Assistant:")[-1].strip()
                
                self.history.append({"role": "user", "content": prompt})
                self.history.append({"role": "assistant", "content": response})
                return response, None

            # Persist user prompt immediately to prevent context loss on failure
            self.history.append({"role": "user", "content": prompt})
            
            # Prepare this turn's ongoing messages (not yet in permanent history)
            turn_messages = []
            steps_taken = 0
            MAX_STEPS = 10
            
            while steps_taken < MAX_STEPS:
                steps_taken += 1

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
                
                # Update UI with thought if present
                from . import ui
                if thought and status_obj:
                    ui.show_thought(status_obj, thought)

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
                
                # REPAIR: Autoset tool_calls from XML or JSON if native tools failed (common in some open models)
                if not message.get("tool_calls"):
                     import re
                     
                     from . import ui
                     content_to_scan = message["content"]
                     
                     code_block_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", content_to_scan, re.DOTALL)
                     if code_block_match:
                         json_match = code_block_match
                     else:
                         # Fallback: Capture any JSON array that looks like it has objects
                         json_match = re.search(r'\[\s*\{.*?\}\s*\]', content_to_scan, re.DOTALL)
                     
                     if json_match:
                         try:
                             potential_json = json_match.group(0)
                             inferred_calls = json.loads(potential_json)
                             if isinstance(inferred_calls, list):
                                 normalized_calls = []
                                 for call in inferred_calls:
                                     if isinstance(call, dict) and "name" in call and "arguments" in call:
                                         normalized_calls.append({
                                             "id": call.get("id", f"call_{len(normalized_calls)}"),
                                             "type": "function",
                                             "function": {
                                                 "name": call["name"],
                                                 "arguments": json.dumps(call["arguments"]) if isinstance(call["arguments"], (dict, list)) else str(call["arguments"])
                                             }
                                         })
                                     elif isinstance(call, dict) and "function" in call:
                                         normalized_calls.append(call)
                                 message["tool_calls"] = normalized_calls if normalized_calls else None
                                 # Strip the JSON from content
                                 message["content"] = message["content"].replace(potential_json, "").strip()
                                 if not message["content"]: message["content"] = "..."
                         except:
                             pass # JSON parse failed, fall through to XML check

                     # 2. Try XML format if JSON failed
                     if not message.get("tool_calls") and "<" in message["content"]:
                         # Regex for self-closing XML tool tags: <tool_name arg1="val1" ... />
                         # We'll use a more robust regex that handles newlines and attributes
                         xml_tools = re.findall(r'<(\w+)\s+([^>]*?)/>', message["content"], re.DOTALL)
                         if xml_tools:
                             inferred_calls = []
                             for name, args_str in xml_tools:
                                 # Parse attributes: key="value"
                                 args = {}
                                 for key, val in re.findall(r'(\w+)="([^"]*)"', args_str):
                                     args[key] = val
                                 
                                 # Map to schema if possible, or just pass as is
                                 inferred_calls.append({
                                     "id": f"call_{len(inferred_calls)}",
                                     "type": "function",
                                     "function": {
                                         "name": name,
                                         "arguments": json.dumps(args)
                                     }
                                 })
                             
                             if inferred_calls:
                                 # Strip the XML tags from content so user doesn't see them as text
                                 for name, args_str in xml_tools:
                                     message["content"] = message["content"].replace(f"<{name} {args_str}/>", "").strip()
                                 
                                 # Strip common model hallucinated interruption messages
                                 message["content"] = message["content"].replace("[Response interrupted by a tool use result. Only one tool may be used at a time and should be placed at the end of the message.]", "").strip()
                                 
                                 if not message["content"]: message["content"] = "..."
                                 message["tool_calls"] = inferred_calls
                
                # Standardize assistant message
                clean_msg = {
                    "role": "assistant",
                    "content": message["content"]
                }
                
                if message.get("tool_calls"):
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
                        args_obj = tool_call["function"].get("arguments", "{}")
                        if isinstance(args_obj, dict):
                            func_args = args_obj
                        else:
                            func_args = json.loads(args_obj) if args_obj else {}
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

            return "Error: Maximum task steps reached. The task may be too complex or got stuck in a loop.", None

        except Exception as e:
            return None, str(e)

    def generate(self, prompt, status_obj=None):
        """Wrapper to run async generate in sync context if needed, but CLI should be async."""
        return asyncio.run(self.generate_async(prompt, status_obj))
