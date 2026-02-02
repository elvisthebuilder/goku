import requests
import subprocess
import json
import os
import re
from . import config

from . import tools as goku_tools

class GokuEngine:
    def __init__(self):
        self.mode = "online"
        self.history = []

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
        
        payload = {
            "model": config.DEFAULT_HF_MODEL,
            "messages": messages,
            "max_tokens": 1024,
            "tools": goku_tools.TOOLS_SCHEMA,
            "tool_choice": "auto",
            "stream": False
        }

        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
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

        cmd = [str(config.LLAMA_CPP_BIN), "-m", str(config.MODEL_PATH), "-p", full_prompt, "-n", "256", "--quiet", "--no-display-prompt"]
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

    def generate(self, prompt, status_obj=None):
        try:
            if self.mode == "offline":
                response = self._get_offline_response(prompt)
                self.history.append({"role": "user", "content": prompt})
                self.history.append({"role": "assistant", "content": response})
                return response, None

            # Online Agentic Loop
            current_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            for msg in self.history[-config.SESSION_MEMORY_MAX:]:
                current_messages.append(msg)
            current_messages.append({"role": "user", "content": prompt})

            while True:
                res_json = self._get_online_response(current_messages)
                message = res_json["choices"][0]["message"]
                
                # Check for and display thoughts/reasoning
                thought = message.get("reasoning_content") or message.get("thought") or message.get("reasoning")
                content = message.get("content", "")
                
                if not thought and content:
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
                    
                    # Execute tool - AI handles confirmations conversationally
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
