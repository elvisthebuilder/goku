from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.status import Status

import json
console = Console()

def print_welcome():
    welcome_text = Text("Goku AI Agent", style="bold cyan")
    console.print(Panel(welcome_text, subtitle="Type /help for commands", border_style="blue", padding=(0, 2)))

def print_help():
    help_text = """
    [bold yellow]Available Commands:[/bold yellow]
    - [cyan]/mode [online|offline][/cyan] : Switch between API and Local modes
    - [cyan]/online[/cyan] / [cyan]/offline[/cyan]      : Shortcuts to switch online/offline
    - [cyan]/provider [name][/cyan]        : List or switch AI providers
    - [cyan]/url <url>[/cyan]           : Set custom API URL for current provider
    - [cyan]/search [provider][/cyan]        : List or switch search providers
    - [cyan]/token [provider] <key>[/cyan] : Save an API token (defaults to current provider)
    - [cyan]/model <name>[/cyan]           : Change the active model for current provider
    - [cyan]/models[/cyan]                  : List available models for the active provider
    - [cyan]/setup[/cyan]                  : Install offline support (llama.cpp)
    - [cyan]/update[/cyan]                 : Update Goku to the latest version
    - [cyan]/clear[/cyan]                  : Clear session history
    - [cyan]/retry[/cyan]                  : Retry the last generation
    - [cyan]/exit[/cyan]                   : Quit goku
    - [cyan]/help[/cyan]                   : Show this help message
    """
    console.print(help_text)

def print_status(mode, is_online=True):
    status_str = "ONLINE" if mode == "online" else "OFFLINE"
    color = "green" if mode == "online" else "yellow"
    console.print(f"[bold]Status:[/bold] [{color}]{status_str}[/{color}]")

def show_error(message):
    console.print(f"[bold red]Error:[/bold red] {message}")

def show_assistant_response(text):
    md = Markdown(text)
    console.print(Panel(md, title="Goku", border_style="green"))

# Persistent session for chat history
_chat_session = None

def _get_chat_session():
    global _chat_session
    if _chat_session is None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
        _chat_session = PromptSession(history=InMemoryHistory())
    return _chat_session

async def get_user_input_async():
    """Async input that supports cursor directions, history, and more via prompt_toolkit."""
    from prompt_toolkit.styles import Style
    from prompt_toolkit.patch_stdout import patch_stdout
    
    # Simple style to match our current UI
    style = Style.from_dict({
        'prompt': 'bold #3b82f6', # blue
    })
    
    session = _get_chat_session()
    
    try:
        # Use patch_stdout so ui.console.print calls from other tasks (like status) work
        with patch_stdout():
            result = await session.prompt_async("You: ", style=style)
            return result.strip()
    except EOFError:
        return "/exit"
    except KeyboardInterrupt:
        return ""

async def ask_async(message, style_name='prompt'):
    """Generic async prompt helper using the persistent session."""
    from prompt_toolkit.styles import Style
    from prompt_toolkit.patch_stdout import patch_stdout
    
    style = Style.from_dict({
        'prompt': 'bold #eab308', # yellow
    })
    
    session = _get_chat_session()
    
    try:
        with patch_stdout():
            # Use HTML/formatted message if desired, or just raw string
            result = await session.prompt_async(message, style=style)
            return result.strip()
    except (EOFError, KeyboardInterrupt):
        return ""

def get_user_input():
    """Legacy sync wrapper (not used by main loop anymore)"""
    from rich.prompt import Prompt
    return Prompt.ask("[bold blue]You[/bold blue]")

from rich.box import ROUNDED
from rich.columns import Columns

# Store the last thought to display it as a collapsible panel
last_thought = {"text": "", "shown": False}

from . import config

from rich.console import Group
from rich.spinner import Spinner
from collections import deque

class ThoughtStream:
    """
    Manages a live stream of thought lines that fades/scrolls (rolling window).
    Uses a Live display to show transient thoughts + spinner.
    """
    def __init__(self, max_height=5):
        self.max_height = max_height
        self.lines = deque(maxlen=max_height)
        self.live = None
        self.spinner = Spinner("dots", text="[bold green]Thinking...[/bold green]")
    
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        # transient=True ensures it disappears when done!
        self.live = Live(self.get_renderable(), console=console, refresh_per_second=12, transient=True)
        self.live.start()

    def stop(self):
        if self.live:
            self.live.stop()
            self.live = None

    def update(self, text):
        if not text: return
        
        # Smart handling: If it's a status update (contains "Thinking"), update spinner text
        # Otherwise, treat it as a thought line
        if "Thinking..." in text:
             self.spinner.text = text
        else:
             # Add new text to our rolling buffer
             for line in text.split('\n'):
                 if line.strip():
                     self.lines.append(line.strip())
        
        if self.live:
            self.live.update(self.get_renderable())

    def get_renderable(self):
        # Create text block from lines with fading opacity look (simulated via dims)
        text_group = Text()
        
        # Render past lines (dimmed)
        for i, line in enumerate(list(self.lines)):
            # Last line is bright, previous are dim
            style = "italic blue" if i == len(self.lines) - 1 else "dim blue"
            text_group.append(f"🧠 {line}\n", style=style)
            
        return Group(
            text_group,
            self.spinner
        )

# Global stream instance for ease of use
_current_stream = None

def show_loading():
    """Returns a ThoughtStream context manager."""
    return ThoughtStream(max_height=6)

def show_thought(status_obj, thought):
    """Update the active ThoughtStream if available."""
    if not config.SHOW_THOUGHTS:
        return
        
    # Check if status_obj is actually our ThoughtStream
    if isinstance(status_obj, ThoughtStream):
        status_obj.update(thought)
    elif hasattr(status_obj, "update"):
        # Fallback for standard Rich Status (legacy support)
        status_obj.update(f"[italic blue]🧠 {thought}[/italic blue]\n[bold green]Thinking...")

def show_thought_panel():
    pass

def show_tool_execution(tool_name, args):
    console.print(f"[bold cyan]🔧 Executing: {tool_name}[/bold cyan] [dim]{json.dumps(args)}[/dim]")


def request_permission(command):
    # Stop any active status while asking for permission
    console.print(Panel(f"[bold red]⚠️ COMMAND REQUIRES PERMISSION[/bold red]\n\n[yellow]{command}[/yellow]", border_style="red"))
    choice = console.input("[bold white]Allow this command? (y/n): [/bold white]").lower()
    return choice == 'y'
