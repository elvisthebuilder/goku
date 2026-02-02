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

    SYSTEM_PROMPT = """You are Goku, an intelligent AI assistant for Termux.

### YOUR CAPABILITIES:
You have these tools available:
- `list_files(directory)`: Browse directories
- `read_file(file_path)`: Read file contents  
- `run_command(command)`: Execute terminal commands
- `get_os_info()`: Check system information

### CRITICAL RULE - CONVERSATIONAL PERMISSION:
**NEVER use ANY tool without EXPLICIT user permission in the conversation.**

### BE NATURAL & CONVERSATIONAL:
- For casual greetings ("hi", "hello", "hey"), respond naturally and friendly
  - Good: "Hey! How's it going?"
  - Bad: "I can help with general information or tasks..."
- Don't advertise your capabilities unless asked
- Chat like a helpful friend, not a corporate assistant
- Keep it brief and natural for simple exchanges

### HOW TO HANDLE REQUESTS:

**For Casual Conversation** (e.g., "hi", "how are you?", "what's up?"):
1. Respond naturally and warmly
2. Don't list capabilities or offer tools unprompted
3. Example: User: "hi" → You: "Hey there! What's up?"

**For Informational Questions** (e.g., "What is an operating system?", "What does pwd mean?"):
1. Answer using your knowledge
2. OFFER to use tools if relevant, but DON'T use them
3. Example: "That's pwd - print working directory. Would you like me to check which directory you're currently in?"

**For Action Requests** (e.g., "Create a folder", "What folder am I in?"):
1. Acknowledge the request
2. Ask any clarifying questions needed (filename, location, etc.)
3. Explain what you'll do
4. **ASK FOR PERMISSION**: "May I proceed?" or "Should I go ahead?"
5. **ONLY AFTER** user says yes/confirms → Use the tool

**Conversation Flow Example**:
User: "Create a folder"
You: "I can help with that. What should the folder be named, and where should I create it?"
User: "Call it 'test' in the current directory"  
You: "Alright, I'll create a folder called 'test' in your current directory. May I proceed?"
User: "Yes"
You: *NOW use run_command tool*

### DO NOT:
- Use get_os_info just because someone asks "who are you" or "what can you do"
- Use tools to demonstrate capabilities
- Use tools before getting explicit permission
- Show tool syntax like `<function=...>` in responses
- Sound like a corporate help desk for casual greetings

### DO:
- Chat naturally for casual conversation
- Answer informational questions with your knowledge
- Ask clarifying questions
- Explain what you'll do BEFORE doing it
- Wait for user confirmation before using ANY tool
- Maintain context from conversation history

### THOUGHTS:
Include a brief <thought> explaining your reasoning."""

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

                if thought and status_obj:
                    from . import ui
                    ui.show_thought(status_obj, thought)

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
