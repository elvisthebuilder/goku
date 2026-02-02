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


def create_file(file_path, content):
    """Creates a new file with the given content."""
    try:
        path = Path(file_path)
        if path.exists():
            return f"Error: File {file_path} already exists. Use edit_file to modify it."
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"File created: {file_path}"
    except Exception as e:
        return f"Error creating file: {e}"

def edit_file(file_path, old_text, new_text):
    """Edits a file by replacing old_text with new_text. Safer than rewriting."""
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File {file_path} not found."
        
        content = path.read_text()
        if old_text not in content:
            return f"Error: The target string was not found in {file_path}. Please check exact matching."
        
        if content.count(old_text) > 1:
            return f"Error: The target string appears {content.count(old_text)} times. Match must be unique."

        new_content = content.replace(old_text, new_text)
        path.write_text(new_content)
        return f"File edited successfully: {file_path}"
    except Exception as e:
        return f"Error editing file: {e}"

def search_code(directory, query):
    """Recursively searches for a string in text files within a directory."""
    try:
        cmd = f"grep -r \"{query}\" \"{directory}\" | head -n 20"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if not result.stdout:
            return "No matches found."
        return result.stdout
    except Exception as e:
        return f"Error searching code: {e}"

def search_web(query):
    """Searches the web using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if not results:
                return "No results found."
            formatted = []
            for r in results:
                formatted.append(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n---")
            return "\n".join(formatted)
    except ImportError:
        return "Error: duckduckgo-search not installed. Run 'pip install duckduckgo-search'."
    except Exception as e:
        return f"Error searching web: {e}"

# Define tool schemas for the AI
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Path to directory (default: current)"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit file by replacing a unique string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file"},
                    "old_text": {"type": "string", "description": "Exact unique string to replace"},
                    "new_text": {"type": "string", "description": "New replacement string"}
                },
                "required": ["file_path", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search code files for a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Root directory"},
                    "query": {"type": "string", "description": "Search term"}
                },
                "required": ["directory", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to run"
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
            "description": "Get system information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dummy": {"type": "string", "description": "Unused"}
                },
                "required": []
            }
        }
    }
]

def execute_tool(name, args, permission_callback=None):
    """Dispatcher for tool execution. The AI will handle confirmations conversationally."""
    # Handle null or empty args
    if args is None:
        args = {}
    
    if name == "run_command":
        return run_command(args.get("command", ""))
    elif name == "list_files":
        return list_files(args.get("directory", "."))
    elif name == "read_file":
        return read_file(args.get("file_path", ""))
    elif name == "create_file":
        return create_file(args.get("file_path"), args.get("content"))
    elif name == "edit_file":
        return edit_file(args.get("file_path"), args.get("old_text"), args.get("new_text"))
    elif name == "search_code":
        return search_code(args.get("directory"), args.get("query"))
    elif name == "search_web":
        return search_web(args.get("query"))
    elif name == "get_os_info":
        return get_os_info()
    return f"Tool {name} not found."
