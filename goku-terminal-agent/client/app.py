
import asyncio
import json
import websockets
import os
import httpx
from datetime import datetime
from textual.app import App, ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, Input, Static, RichLog, Button, Label, Markdown, LoadingIndicator, RadioSet, RadioButton
from textual.containers import Container, Horizontal, Vertical, Grid, VerticalScroll, Center
from textual.binding import Binding
from textual.message import Message
from textual import on,work
from rich.markdown import Markdown as RichMarkdown
try:
    from client.theme import Theme
except ImportError:
    from theme import Theme

# --- Components ---

class ChatBubble(Static):
    """A styled chat bubble for messages."""
    
    def __init__(self, content: str, role: str = "agent", **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content_text = content
        self.timestamp = datetime.now().strftime("%H:%M")
        
    def compose(self) -> ComposeResult:
        with Vertical(classes=f"bubble_container {self.role}_container"):
            # Header with role and timestamp
            with Horizontal(classes="bubble_header"):
                if self.role == "agent":
                    yield Label("🐉 GOKU", classes="bubble_author agent_author")
                    yield Label(f" • {self.timestamp}", classes="bubble_time")
                else:
                    yield Label(f"{self.timestamp} • ", classes="bubble_time")
                    yield Label("YOU", classes="bubble_author user_author")
            
            # Content Body
            yield Static(RichMarkdown(self.content_text), classes=f"bubble_body {self.role}_body")

    def update_content(self, new_chunk: str):
        self.content_text += new_chunk
        body = self.query_one(f".{self.role}_body", Static)
        body.update(RichMarkdown(self.content_text))

class TypewriterTitle(Static):
    """Animated Title Component"""
    def on_mount(self) -> None:
        self.update("🐉 GOKU TERMINAL")

class StatusBadge(Static):
    """Online/Offline status indicator."""
    def __init__(self, status: str = "offline", **kwargs):
        super().__init__(**kwargs)
        self.status = status

    def render(self) -> str:
        icon = "●"
        color = Theme.STATUS_OFFLINE
        if self.status == "online":
            color = Theme.STATUS_ONLINE
        elif self.status == "busy":
            color = Theme.STATUS_BUSY
        return f"[{color}]{icon}[/] {self.status.upper()}"

class InputBar(Static):
    """Floating input bar at the bottom."""
    
    class Submitted(Message):
        def __init__(self, value: str):
            self.value = value
            super().__init__()

    def compose(self) -> ComposeResult:
        with Container(id="input_container"):
            yield Input(placeholder="Ask anything... (Hit Enter)", id="main_input")
            with Horizontal(id="input_hint"):
                yield Label("esc: stop | ctrl+k: cmd | ctrl+s: config", classes="hint_label")

    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted):
        event.stop()
        if event.value.strip():
            self.post_message(self.Submitted(event.value))
            event.input.value = ""

# --- Screens ---

class CommandPalette(ModalScreen):
    """Premium Command Palette (Ctrl+K)."""
    
    BINDINGS = [Binding("escape", "close_palette", "Close")]
    
    def compose(self) -> ComposeResult:
        with Container(id="palette_dialog", classes="panel"):
            with Vertical(id="palette_content"):
                yield Label("⚡ COMMAND MENU", id="palette_title")
                yield Input(placeholder="Search commands...", id="palette_search")
                
                with VerticalScroll(id="palette_list"):
                    yield Button("📊  System Status", id="cmd_status", classes="palette_btn")
                    yield Button("🧹  Clear Chat", id="cmd_clear", classes="palette_btn")
                    yield Button("⚙️  Configuration", id="cmd_config", classes="palette_btn")
                    yield Button("❌  Exit Goku", id="cmd_exit", classes="palette_btn")

    def action_close_palette(self):
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed):
        cmd = event.button.id
        if cmd == "cmd_clear":
            self.app.query_one("ChatInterface").clear_chat()
            self.app.pop_screen()
        elif cmd == "cmd_config":
            self.app.pop_screen()
            self.app.action_settings()
        elif cmd == "cmd_exit":
            self.app.exit()
        elif cmd == "cmd_status":
             self.app.notify("System is fully operational 🚀")
             self.app.pop_screen()

class SettingsScreen(ModalScreen):
    """Configuration Screen."""
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        with Container(id="settings_dialog", classes="panel"):
            with VerticalScroll(id="settings_content"):
                yield Label("⚙️  CONFIGURATION", id="settings_title")
                yield Label("OpenAI API Key", classes="settings_label")
                yield Input(placeholder="sk-...", id="openai_key", password=True)
                
                yield Label("Anthropic API Key", classes="settings_label")
                yield Input(placeholder="sk-ant-...", id="anthropic_key", password=True)
                
                yield Label("GitHub Personal Access Token", classes="settings_label")
                yield Input(placeholder="ghp_...", id="github_token", password=True)

                yield Label("Hugging Face Token", classes="settings_label")
                yield Input(placeholder="hf_...", id="hf_token", password=True)
                
                yield Label("Ollama Base URL", classes="settings_label")
                yield Input(placeholder="http://localhost:11434", id="ollama_url")
                
                with Horizontal(id="settings_actions"):
                    yield Button("Save Changes", variant="primary", id="save_btn")
                    yield Button("Cancel", id="cancel_btn")

    # Reuse logic from old app mostly, just cleaner UI
    async def on_mount(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://localhost:8000/config")
                if resp.status_code == 200:
                    config = resp.json()
                    self.query_one("#openai_key").value = config.get("OPENAI_API_KEY", "")
                    self.query_one("#anthropic_key").value = config.get("ANTHROPIC_API_KEY", "")
                    self.query_one("#github_token").value = config.get("GITHUB_TOKEN", "")
                    self.query_one("#hf_token").value = config.get("HF_TOKEN", "")
                    self.query_one("#ollama_url").value = config.get("OLLAMA_BASE_URL", "")
        except:
            pass # Silent fail on load

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save_btn":
            config = {
                "OPENAI_API_KEY": self.query_one("#openai_key").value,
                "ANTHROPIC_API_KEY": self.query_one("#anthropic_key").value,
                "GITHUB_TOKEN": self.query_one("#github_token").value,
                "HF_TOKEN": self.query_one("#hf_token").value,
                "OLLAMA_BASE_URL": self.query_one("#ollama_url").value,
            }
            try:
                async with httpx.AsyncClient() as client:
                    await client.post("http://localhost:8000/config", json=config)
                self.app.notify("Settings saved!")
            except:
                self.app.notify("Failed to save settings", severity="error")
            self.app.pop_screen()
        elif event.button.id == "cancel_btn":
            self.app.pop_screen()

class FirstRunWizard(ModalScreen):
    """Wizard for first-time setup."""
    
    def compose(self) -> ComposeResult:
        with Container(id="wizard_dialog", classes="panel"):
            with Vertical(id="wizard_content"):
                yield Label("👋 Welcome to Goku Terminal!", classes="wizard_title")
                yield Label("Select your primary AI Provider:", classes="wizard_label")
                
                with RadioSet(id="provider_select"):
                    yield RadioButton("OpenAI", id="opt_openai", value=True)
                    yield RadioButton("Anthropic", id="opt_anthropic")
                    yield RadioButton("Hugging Face", id="opt_huggingface")
                    yield RadioButton("GitHub Models", id="opt_github")
                    yield RadioButton("Ollama (Local)", id="opt_ollama")
                
                # Token inputs (hidden by default except active)
                with Vertical(id="token_inputs"):
                    yield Label("Enter API Key:", classes="wizard_label")
                    yield Input(placeholder="sk-...", id="wiz_token_input", password=True)
                
                with Horizontal(id="wizard_actions"):
                    yield Button("Save & Start", variant="primary", id="wiz_save")
                    yield Button("Skip Setup", id="wiz_skip")

    def on_radio_set_changed(self, event: RadioSet.Changed):
        # Update placeholder based on selection
        sel = event.pressed.id
        inp = self.query_one("#wiz_token_input", Input)
        if sel == "opt_openai":
            inp.placeholder = "sk-..."
        elif sel == "opt_anthropic":
            inp.placeholder = "sk-ant-..."
        elif sel == "opt_huggingface":
            inp.placeholder = "hf_..."
        elif sel == "opt_github":
             inp.placeholder = "ghp_..."
        elif sel == "opt_ollama":
             inp.placeholder = "http://localhost:11434"
             inp.value = "http://localhost:11434"

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "wiz_skip":
            self.app.pop_screen()
            return
        
        if event.button.id == "wiz_save":
            provider_radio = self.query_one("#provider_select", RadioSet).pressed.id
            token_val = self.query_one("#wiz_token_input", Input).value.strip()
            
            config_key = ""
            if provider_radio == "opt_openai": config_key = "OPENAI_API_KEY"
            elif provider_radio == "opt_anthropic": config_key = "ANTHROPIC_API_KEY"
            elif provider_radio == "opt_huggingface": config_key = "HF_TOKEN"
            elif provider_radio == "opt_github": config_key = "GITHUB_TOKEN"
            elif provider_radio == "opt_ollama": config_key = "OLLAMA_BASE_URL"
            
            # Save
            if token_val:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post("http://localhost:8000/config", json={config_key: token_val})
                    self.app.notify("Configuration Saved!")
                    
                    # Set active provider
                    provider_map = {
                        "opt_openai": "openai",
                        "opt_anthropic": "anthropic", 
                        "opt_huggingface": "huggingface",
                        "opt_github": "github",
                        "opt_ollama": "ollama"
                    }
                    self.app.active_provider = provider_map.get(provider_radio, "openai")
                    self.app.query_one(ChatInterface).add_message(ChatBubble(f"System ready! Active provider: **{self.app.active_provider}**", role="agent"))
                    
                except Exception as e:
                    self.app.notify(f"Error saving: {e}", severity="error")
            
            self.app.pop_screen()

# --- Main App ---

class ChatInterface(Static):
    """The main chat area."""
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat_scroll"):
            yield Label("Welcome to Goku Terminal Agent", classes="welcome_msg")
            yield Label("Try asking: 'Refactor this file' or 'Explain this code'", classes="welcome_sub")

    def add_message(self, bubble: ChatBubble):
        self.query_one("#chat_scroll").mount(bubble)
        bubble.scroll_visible()
    
    def clear_chat(self):
        self.query_one("#chat_scroll").remove_children()

class GokuApp(App):
    """Premium Terminal AI Agent."""
    
    CSS = Theme.CSS + """
    /* App Layout */
    #root_container {
        layout: grid;
        grid-size: 1 3;
        grid-rows: 3 1fr auto;
        height: 100%;
        background: $BG_APP;
    }

    #sidebar {
        display: none;
    }

    /* Main Chat Area */
    #main_area {
        width: 100%;
        height: 100%;
        layout: vertical;
        background: $BG_APP;
    }
    
    /* Header */
    #app_header {
        height: 100%;
        background: $BG_HEADER;
        border-bottom: wide $BORDER_DEFAULT;
        layout: horizontal;
        padding: 0 2;
        align: left middle;
    }

    #logo_text {
        text-style: bold;
        color: $TEXT_ACCENT;
    }

    #status_badge {
        margin-left: 2;
    }

    /* Chat Area */
    ChatInterface {
        height: 1fr;
        padding: 1 2;
    }
    
    #chat_scroll {
        scrollbar-gutter: stable;
    }

    .welcome_msg {
        text-align: center;
        margin-top: 4;
        text-style: bold;
        color: $TEXT_PRIMARY;
    }

    .welcome_sub {
        text-align: center;
        color: $TEXT_MUTED;
    }

    /* Bubbles */
    .bubble_container {
        height: auto;
        margin-bottom: 2;
    }

    .bubble_header {
        height: 1;
        margin-bottom: 0;
    }

    .bubble_body {
        padding: 1 2;
        background: $MSG_AGENT_BG;
        border: wide $BORDER_DEFAULT;
        color: $MSG_AGENT_TEXT;
        border-title-color: $TEXT_MUTED;
        height: auto;
    }
    
    .agent_container { align: left top; padding-right: 20; }
    .agent_author { color: $TEXT_ACCENT; text-style: bold; }
    
    .user_container { align: right top; padding-left: 20; }
    .user_body {
        background: $MSG_USER_BG;
        color: $MSG_USER_TEXT;
        border: wide $MSG_USER_BG; 
    }
    .user_author { color: $TEXT_PRIMARY; text-style: bold; }
    
    .bubble_time { color: $TEXT_MUTED; text-style: italic; }

    /* Input Area */
    #input_container {
        height: auto;
        padding: 1 4;
        background: $BG_HEADER;
        border-top: wide $BORDER_DEFAULT;
    }
    
    #main_input {
        border: none;
        background: $BG_INPUT;
        height: 3;
    }
    
    #input_hint {
        height: 1;
        color: $TEXT_MUTED;
        align: center middle;
        margin-top: 1;
    }

    /* Modals */
    #palette_dialog, #settings_dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        align: center middle;
        background: $BG_PANEL;
        border: wide $BORDER_ACCENT;
    }
    
    #palette_title, #settings_title {
        text-style: bold;
        color: $TEXT_ACCENT;
        margin-bottom: 1;
        text-align: center;
    }

    .palette_btn {
        width: 100%;
        margin-bottom: 1;
        content-align: left middle;
    }

    .settings_label {
        margin-top: 1;
        color: $TEXT_SECONDARY;
    }
    
    #settings_actions {
        margin-top: 2;
        align: center middle;
    }
    
    #settings_actions Button {
        margin: 0 1;
    }
    
    /* Wizard Styles */
    #wizard_dialog {
        width: 70;
        height: auto;
        padding: 2 4;
        align: center middle;
        background: $BG_PANEL;
        border: wide $BORDER_ACCENT;
    }
    
    .wizard_title {
        text-style: bold;
        color: $TEXT_ACCENT;
        text-align: center;
        margin-bottom: 2;
    }
    
    .wizard_label {
        color: $TEXT_SECONDARY;
        margin-top: 1;
        margin-bottom: 1;
    }
    
    #provider_select {
        height: auto;
        margin-bottom: 2;
        border: solid $BORDER_DEFAULT;
        padding: 1;
    }
    
    RadioButton {
        width: 100%;
        color: $TEXT_PRIMARY;
    }
    
    #wizard_actions {
        margin-top: 2;
        align: center middle;
    }
    
    #wizard_actions Button {
        margin: 0 1; 
    }
    """
    
    CSS = CSS.replace("$BG_APP", Theme.BG_APP)\
             .replace("$BG_HEADER", Theme.BG_HEADER)\
             .replace("$BG_PANEL", Theme.BG_PANEL)\
             .replace("$BG_INPUT", Theme.BG_INPUT)\
             .replace("$BORDER_DEFAULT", Theme.BORDER_DEFAULT)\
             .replace("$BORDER_FOCUS", Theme.BORDER_FOCUS)\
             .replace("$BORDER_ACCENT", Theme.BORDER_ACCENT)\
             .replace("$TEXT_PRIMARY", Theme.TEXT_PRIMARY)\
             .replace("$TEXT_SECONDARY", Theme.TEXT_SECONDARY)\
             .replace("$TEXT_MUTED", Theme.TEXT_MUTED)\
             .replace("$TEXT_ACCENT", Theme.TEXT_ACCENT)\
             .replace("$MSG_USER_BG", Theme.MSG_USER_BG)\
             .replace("$MSG_USER_TEXT", Theme.MSG_USER_TEXT)\
             .replace("$MSG_AGENT_BG", Theme.MSG_AGENT_BG)\
             .replace("$MSG_AGENT_TEXT", Theme.MSG_AGENT_TEXT)

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+k", "palette", "Command Palette"),
        Binding("ctrl+s", "settings", "Settings"),
    ]

    SERVER_URL = "ws://localhost:8000/ws/chat"

    def compose(self) -> ComposeResult:
        with Header(show_clock=True):
            pass # We'll do custom header mainly
        
        with Vertical(id="root_container"):
            # Custom Header
            with Horizontal(id="app_header"):
                yield Label("🐉 GOKU TERMINAL", id="logo_text")
                yield StatusBadge("online", id="status_badge")
            
            # Main Chat
            with Vertical(id="main_area"):
                yield ChatInterface()
            
            # Input
            yield InputBar()

    async def on_mount(self):
        self.ws = None
        self.active_provider = "openai" # Default
        self.call_system_connect()
        self.check_first_run()

    @work
    async def check_first_run(self):
        # Allow UI to mount first
        await asyncio.sleep(0.5)
        # Check if any provider keys are present
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://localhost:8000/config")
                if resp.status_code == 200:
                    config = resp.json()
                    keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN", "GITHUB_TOKEN", "OLLAMA_BASE_URL"]
                    has_keys = any(config.get(k) for k in keys)
                    if not has_keys:
                        # Show Wizard
                        self.push_screen(FirstRunWizard())
        except:
            pass

    @work
    async def call_system_connect(self):
        try:
            self.ws = await websockets.connect(self.SERVER_URL)
            self.notify("Connected to Backend System")
            self.query_one("#status_badge", StatusBadge).status = "online"
            self.query_one("#status_badge").refresh()
            
            async for message in self.ws:
                msg = json.loads(message)
                if msg.get("type") == "content":
                     if hasattr(self, "current_agent_bubble"):
                         self.current_agent_bubble.update_content(msg.get("content", ""))
                     else:
                         pass
        except:
             self.query_one("#status_badge", StatusBadge).status = "offline"
             self.query_one("#status_badge").refresh()
             self.notify("Server is OFFLINE", severity="error")

    @on(InputBar.Submitted)
    async def handle_submit(self, event: InputBar.Submitted):
        user_text = event.value.strip()
        chat = self.query_one(ChatInterface)
        
        # User Bubble
        chat.add_message(ChatBubble(user_text, role="user"))
        
        # SLASH COMMANDS HANDLER
        if user_text.startswith("/"):
            parts = user_text.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd == "/help":
                help_text = """
### Available Commands
- `/provider` : List or switch AI providers
- `/setup`    : Open configuration settings
- `/online`   : Check server status
- `/clear`    : Clear chat history
- `/exit`     : Quit application
                """
                chat.add_message(ChatBubble(help_text, role="agent"))
                return
            
            elif cmd == "/setup":
                self.action_settings()
                return

            elif cmd == "/clear":
                chat.clear_chat()
                return
            
            elif cmd == "/exit":
                self.exit()
                return

            elif cmd == "/provider":
                if not args:
                    chat.add_message(ChatBubble(f"Current Active Provider: **{self.active_provider}**\n\nTo switch, type: `/provider <name>`\n(options: openai, anthropic, huggingface, ollama, github)", role="agent"))
                else:
                    new_provider = args[0].lower()
                    if new_provider in ["openai", "anthropic", "huggingface", "ollama", "github"]:
                        self.active_provider = new_provider
                        self.notify(f"Provider switched to: {new_provider}")
                        chat.add_message(ChatBubble(f"✅ Active provider set to **{new_provider}**", role="agent"))
                    else:
                        chat.add_message(ChatBubble(f"❌ Unknown provider: {new_provider}", role="agent"))
                return
        
        # Agent Placeholder
        self.current_agent_bubble = ChatBubble("", role="agent")
        chat.add_message(self.current_agent_bubble)
        
        # Send
        if self.ws:
            payload = {
                "type": "chat", 
                "content": user_text,
                "provider": getattr(self, "active_provider", "openai")
            }
            await self.ws.send(json.dumps(payload))
        else:
            # Simulation for development/offline
            await asyncio.sleep(0.5)
            self.current_agent_bubble.update_content("Backend is offline. This is a simulated response.\n\n*Check your server connection.*")

    def action_palette(self):
        self.push_screen(CommandPalette())

    def action_settings(self):
        self.push_screen(SettingsScreen())

if __name__ == "__main__":
    app = GokuApp()
    app.run()
