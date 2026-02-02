from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.status import Status

import json
console = Console()

def print_welcome():
    welcome_text = Text("Welcome to Goku AI Agent", style="bold cyan")
    console.print(Panel(welcome_text, subtitle="Type /help for commands", border_style="bright_blue"))

def print_help():
    help_text = """
    [bold yellow]Available Commands:[/bold yellow]
    - [cyan]/mode online[/cyan]  : Switch to Online mode (HF API)
    - [cyan]/mode offline[/cyan] : Switch to Offline mode (llama.cpp)
    - [cyan]/token <key>[/cyan]   : Save your HuggingFace API Token
    - [cyan]/setup[/cyan]         : Install offline support (llama.cpp)
    - [cyan]/update[/cyan]        : Update Goku to the latest version
    - [cyan]/clear[/cyan]         : Clear session history
    - [cyan]/retry[/cyan]         : Retry the last generation
    - [cyan]/exit[/cyan]          : Quit goku
    - [cyan]/help[/cyan]          : Show this help message
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

def get_user_input():
    # Use Prompt which prevents editing the prefix
    from rich.prompt import Prompt
    return Prompt.ask("[bold blue]You[/bold blue]")

from rich.box import ROUNDED
from rich.columns import Columns

# Store the last thought to display it as a collapsible panel
last_thought = {"text": "", "shown": False}

def show_loading():
    return console.status("[bold green]Thinking...", spinner="dots")

def show_thought(status, thought):
    """Display thought in the status temporarily, and save it for later permanent display"""
    global last_thought
    if not thought.strip():
        return
    # Truncate thought if it's too long for status line
    clean_thought = thought.strip()
    display_thought = clean_thought[:100] + "..." if len(clean_thought) > 100 else clean_thought
    status.update(f"[dim]💭 {display_thought}[/dim]\n[bold green]Formulating response...")
    
    # Save full thought for display after response
    last_thought = {"text": clean_thought, "shown": False}

def show_thought_panel():
    """Display the saved thought as a collapsible panel after the response"""
    global last_thought
    if last_thought["text"] and not last_thought["shown"]:
        # Create a collapsible-looking panel
        thought_text = last_thought["text"]
        console.print(Panel(
            f"[dim]{thought_text}[/dim]",
            title="💭 Thought Process",
            border_style="dim",
            padding=(0, 1),
            expand=False
        ))
        last_thought["shown"] = True

def show_tool_execution(tool_name, args):
    console.print(f"[bold cyan]🔧 Executing: {tool_name}[/bold cyan] [dim]{json.dumps(args)}[/dim]")


def request_permission(command):
    # Stop any active status while asking for permission
    console.print(Panel(f"[bold red]⚠️ COMMAND REQUIRES PERMISSION[/bold red]\n\n[yellow]{command}[/yellow]", border_style="red"))
    choice = console.input("[bold white]Allow this command? (y/n): [/bold white]").lower()
    return choice == 'y'
