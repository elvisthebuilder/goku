import os
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
    """Reads the content of a specified file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            # Truncate if too long for context
            if len(content) > 2000:
                return content[:2000] + "\n... [TRUNCATED]"
            return content
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"

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
    }
]

def execute_tool(name, args):
    """Dispatcher for tool execution."""
    if name == "list_files":
        return list_files(**args)
    elif name == "read_file":
        return read_file(**args)
    return f"Tool {name} not found."
