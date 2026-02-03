from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Static, RichLog
from textual.binding import Binding
from rich.markdown import Markdown
from rich.panel import Panel
import asyncio
import json

class GokuTUI(App):
    """A premium TUI for the Goku AI Agent."""
    
    CSS = """
    Screen {
        background: #000b1e;
    }
    
    #chat_pane {
        width: 70%;
        height: 100%;
        border-right: tall #003366;
        padding: 1;
    }
    
    #side_pane {
        width: 30%;
        height: 100%;
    }
    
    #logs_pane, #thought_pane {
        height: 50%;
        background: #00152a;
        padding: 1;
        border-bottom: solid #003366;
    }

    #thought_pane {
        background: #001c3d;
    }
    
    #input_box {
        dock: bottom;
        height: 3;
        border: solid #005cc5;
        background: #001a35;
    }
    
    .status_bar {
        dock: top;
        height: 1;
        background: #005cc5;
        color: white;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Exit", show=True),
        Binding("escape", "stop", "Stop", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("ctrl+k", "command_palette", "Palette", show=True),
        Binding("ctrl+t", "toggle_tools", "Tools", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Static("GOKU ONLINE | v2.0.0 | Branch: main", classes="status_bar")
        yield Header()
        with Horizontal():
            with Vertical(id="chat_pane"):
                self.chat_history = RichLog(id="chat_log", wrap=True, highlight=True, markup=True)
                yield self.chat_history
            with Vertical(id="side_pane"):
                with Vertical(id="thought_pane"):
                    yield Static("[bold magenta]💭 THOUGHT PROCESS[/bold magenta]\n", id="thought_title")
                    self.thought_log = RichLog(id="thought_log", wrap=True)
                    yield self.thought_log
                with Vertical(id="logs_pane"):
                    yield Static("[bold cyan]🔧 TOOL EXECUTION LOGS[/bold cyan]\n", id="logs_title")
                    self.tool_logs = RichLog(id="tool_log", wrap=True)
                    yield self.tool_logs
        yield Input(placeholder="Type your command here...", id="input_box")
        yield Footer()

    is_stopping = False

    async def action_stop(self) -> None:
        """Terminate the current action."""
        self.is_stopping = True
        self.tool_logs.write("[bold red]🛑 Stopping current action...[/bold red]")
        # Signal backend to stop (mocked for now)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        self.is_stopping = False
        # Clear input
        self.query_one("#input_box", Input).value = ""
        
        # Add to chat
        self.chat_history.write(f"\n[bold blue]You:[/bold blue] {user_text}")
        
        # Start response flow
        await self.simulate_response(user_text)

    async def simulate_response(self, text: str):
        self.thought_log.clear()
        self.thought_log.write("[italic]Thinking about the request...[/italic]")
        await asyncio.sleep(1)
        
        if self.is_stopping: return

        self.thought_log.write("1. Analyze user prompt\n2. Plan tool execution\n3. Formulate response")
        
        self.chat_history.write(f"\n[bold green]Goku:[/bold green] ", scroll_end=False)
        
        response_text = "I am processing your request using the split architecture server. Streaming tokens now..."
        for word in response_text.split():
            if self.is_stopping:
                self.chat_history.write("\n[bold red]── Action Terminated ──[/bold red]")
                break
            self.chat_history.write(f"{word} ", scroll_end=True)
            await asyncio.sleep(0.05)
        
        if not self.is_stopping:
            # Log a dummy tool execution
            self.tool_logs.write(f"[dim]Executing shell__run_command...[/dim]")
            self.tool_logs.write(f"[green]Done.[/green]")

    def action_clear(self) -> None:
        self.chat_history.clear()
        self.tool_logs.clear()
        self.thought_log.clear()

if __name__ == "__main__":
    app = GokuTUI()
    app.run()
