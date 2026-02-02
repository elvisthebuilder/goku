from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.status import Status

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
    return console.input("[bold blue]You > [/bold blue]")

def show_loading():
    return console.status("[bold green]Thinking...")
