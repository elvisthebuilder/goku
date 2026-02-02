import os
import json
import subprocess
from pathlib import Path

def list_files(directory="."):
    """Lists files and directories in the given path."""
    try:
        path = Path(directory)
        items = list(path.iterdir())
        res = f"Contents of {directory}:\n"
        for item in items:
            prefix = "📁 " if item.is_dir() else "📄 "
            res += f"{prefix}{item.name}\n"
        return res
    except Exception as e:
        return f"Error listing files: {str(e)}"

def read_file(file_path):
    """Reads the text content of a specified file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            # Truncate if too long for context
            if len(content) > 2000:
                return content[:2000] + "\n... [TRUNCATED]"
            return content
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"

def run_command(command):
    """Executes a shell command and returns the output."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        out = result.stdout if result.stdout else ""
        err = result.stderr if result.stderr else ""
        return f"STDOUT:\n{out}\nSTDERR:\n{err}\nExit Code: {result.returncode}"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def get_os_info():
    """Returns basic information about the user's OS and device."""
    import platform
    import json
    info = {
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "termux": "PREFIX" in os.environ
    }
    return json.dumps(info, indent=2)


# Define tool schemas for the AI
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Lists all files and folders in a specified directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The directory path to list. Defaults to current directory ('.')."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the text content of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Executes a shell command in the terminal. Use this for OS interactions, installing packages, or running scripts. This is a HIGH PRIVILEGE action.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact shell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_os_info",
            "description": "Returns details about the user's OS, device, and environment (like if it's Termux).",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

def execute_tool(name, args, permission_callback=None):
    """Dispatcher for tool execution. The AI will handle confirmations conversationally."""
    if name == "run_command":
        return run_command(args.get("command", ""))
    elif name == "list_files":
        return list_files(**args)
    elif name == "read_file":
        return read_file(**args)
    elif name == "get_os_info":
        return get_os_info()
    return f"Tool {name} not found."
