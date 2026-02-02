import requests
import subprocess
import json
import os
from . import config

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

    def _get_online_response(self, prompt):
        headers = {}
        # Always reload from config in case it was updated via /token
        if config.HF_TOKEN:
            headers["Authorization"] = f"Bearer {config.HF_TOKEN}"
        
        # Simple HF Inference API call
        API_URL = f"https://api-inference.huggingface.co/models/{config.DEFAULT_HF_MODEL}"
        
        # Build prompt with history
        full_prompt = ""
        for msg in self.history[-config.SESSION_MEMORY_MAX:]:
            full_prompt += f"{msg['role']}: {msg['content']}\n"
        full_prompt += f"user: {prompt}\nassistant:"

        try:
            response = requests.post(API_URL, headers=headers, json={"inputs": full_prompt, "parameters": {"max_new_tokens": 256}}, timeout=10)
            response.raise_for_status()
            res_json = response.json()
            if isinstance(res_json, list) and len(res_json) > 0:
                text = res_json[0].get("generated_text", "")
                # Extract only the newly generated part if it includes the prompt
                if "assistant:" in text:
                    return text.split("assistant:")[-1].strip()
                return text.strip()
            return "Unexpected response from HF API."
        except Exception as e:
            raise Exception(f"Online error: {str(e)}")

    def _get_offline_response(self, prompt):
        if not config.LLAMA_CPP_BIN.exists():
            raise FileNotFoundError("llama.cpp binary not found. Run 'goku setup' to install offline support.")
        if not config.MODEL_PATH.exists():
            raise FileNotFoundError("Model file not found. Run 'goku setup' to download the model.")

        # Build prompt for chat
        full_prompt = ""
        for msg in self.history[-config.SESSION_MEMORY_MAX:]:
             full_prompt += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
        full_prompt += f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

        cmd = [
            str(config.LLAMA_CPP_BIN),
            "-m", str(config.MODEL_PATH),
            "-p", full_prompt,
            "-n", "256",
            "--quiet",
            "--no-display-prompt"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise Exception(f"Offline error: {e.stderr}")

    def generate(self, prompt):
        try:
            if self.mode == "online":
                response = self._get_online_response(prompt)
            else:
                response = self._get_offline_response(prompt)
            
            self.history.append({"role": "user", "content": prompt})
            self.history.append({"role": "assistant", "content": response})
            return response, None
        except Exception as e:
            return None, str(e)
