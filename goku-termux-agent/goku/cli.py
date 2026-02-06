import sys
import os
from .engine import GokuEngine
from . import ui
from . import config
import asyncio
from rich.columns import Columns
from rich.table import Table

async def main():
    engine = GokuEngine()
    
    # Check if we are in setup mode
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        os.system("bash ~/.goku/scripts/setup_offline.sh")
        return

    # Initialize MCP
    ui.console.print("[dim]Initializing tools...[/dim]")
    await engine.initialize_mcp()

    ui.print_welcome()

    # Onboarding: Check if any provider is configured
    active_provider = config.get_active_provider()
    # Check if we have a token for the active provider OR if it's ollama (no token needed)
    has_active_token = config.get_token(active_provider) or active_provider == "ollama"
    
    if not has_active_token:
        # Check if ANY provider has a token to avoid unnecessary wizard if they just switched manually
        any_token = any(config.get_token(p) for p in config.PROVIDERS)
        
        if not any_token:
            ui.console.print("\n[bold cyan]👋 Welcome to Goku AI![/bold cyan]")
            ui.console.print("Let's set up your preferred AI Provider.\n")
            
            ui.console.print("Available Providers:")
            providers = list(config.PROVIDERS.keys())
            for i, p in enumerate(providers, 1):
                ui.console.print(f"  {i}. [bold]{p}[/bold]")
            
            # Blocking input
            choice = await ui.ask_async("Select a provider (1-5): ")
            choice = choice.strip()
            
            selected_provider = "huggingface" # Default
            if choice.isdigit() and 1 <= int(choice) <= len(providers):
                selected_provider = providers[int(choice)-1]
            elif choice in config.PROVIDERS:
                selected_provider = choice
            
            # Set active
            config.set_active_provider(selected_provider)
            active_provider = selected_provider
            
            ui.console.print(f"[green]Selected: {selected_provider}[/green]\n")

    # Verify token
    if not config.get_token(active_provider) and active_provider != "ollama":
        ui.console.print(f"[yellow]Authentication required for {active_provider}.[/yellow]")
        if active_provider == "huggingface":
             ui.console.print("Get a free token at: [link=https://huggingface.co/settings/tokens]https://huggingface.co/settings/tokens[/link]\n")
        elif active_provider == "openai":
             ui.console.print("Get your key at: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]\n")
        elif active_provider == "anthropic":
             ui.console.print("Get your key at: [link=https://console.anthropic.com/]https://console.anthropic.com/[/link]\n")
        elif active_provider == "github":
             ui.console.print("Get your token at: [link=https://github.com/settings/tokens]https://github.com/settings/tokens[/link]\n")
        elif active_provider == "brave":
             ui.console.print("Get your key at: [link=https://brave.com/search/api/]https://brave.com/search/api/[/link]\n")
        
        new_token = await ui.ask_async(f"Enter your {active_provider} API Key: ")
        new_token = new_token.strip()

        if new_token:
            config.save_token(new_token, active_provider)
            ui.console.print(f"[green]Token saved! Goku is ready.[/green]")
        else:
            ui.console.print("[bold yellow]Skipping token. You can set it later with /token.[/bold yellow]")

    ui.print_status(engine.mode)

    last_user_input = None
    available_models = []
    while True:
        try:
            # Async prompt
            user_input = await ui.get_user_input_async()
            user_input = user_input.strip()
            
            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit"]:
                break
            
            if user_input.lower() == "/help":
                ui.print_help()
                continue
            
            # Command parsing
            cmd_parts = user_input.split()
            cmd = cmd_parts[0].lower() if cmd_parts else ""

            # Provider Command
            if cmd == "/provider":
                if len(cmd_parts) == 1:
                    ui.console.print("[bold]Available Providers:[/bold]")
                    active = config.get_active_provider()
                    for p in config.PROVIDERS:
                        status = "[green](active)[/green]" if p == active else ""
                        ui.console.print(f" - {p} {status}")
                else:
                    target = cmd_parts[1].lower()
                    if config.set_active_provider(target):
                        ui.console.print(f"[green]Switched to {target} provider.[/green]")
                    else:
                        ui.show_error(f"Provider '{target}' not found.")
                continue

            # List Models Command
            if cmd in ["/models", "/list"]:
                provider = config.get_active_provider()
                ui.console.print(f"[dim]Fetching models for {provider}...[/dim]")
                models = await asyncio.to_thread(engine.list_models)
                
                if not models:
                    ui.console.print(f"[yellow]No models found or error fetching for {provider}.[/yellow]")
                elif isinstance(models[0], str) and models[0].startswith("Error"):
                     ui.show_error(models[0])
                else:
                    available_models = models
                    ui.console.print(f"[bold]Available Models for {provider}:[/bold]")
                    
                    # Create a multi-column table for alignment
                    table = Table(show_header=False, padding=(0, 2), box=None, show_edge=False)
                    num_cols = 3
                    for _ in range(num_cols):
                        table.add_column()
                    
                    # Partition models into rows
                    rows = []
                    for i in range(0, len(models), num_cols):
                        row_items = []
                        for j in range(num_cols):
                            idx = i + j
                            if idx < len(models):
                                row_items.append(f"[cyan]{idx+1:2}.[/cyan] {models[idx]}")
                            else:
                                row_items.append("")
                        table.add_row(*row_items)
                    
                    ui.console.print(table)
                    
                    ui.console.print(f"\n[dim]Set with: /model <number> or <name>[/dim]")
                continue

            # Model Command
            if cmd == "/model":
                if len(cmd_parts) > 1:
                    arg = cmd_parts[1]
                    provider = config.get_active_provider()
                    
                    selected_model = arg
                    # Check if it's a number and we have available_models
                    if arg.isdigit() and available_models:
                        idx = int(arg) - 1
                        if 0 <= idx < len(available_models):
                            selected_model = available_models[idx]
                        else:
                            ui.show_error(f"Invalid model number. Choose 1-{len(available_models)}.")
                            continue
                            
                    if provider in config.PROVIDERS:
                        config.save_model(selected_model, provider)
                        ui.console.print(f"[green]Model for {provider} set to: {selected_model}[/green]")
                else:
                    provider = config.get_active_provider()
                    current_model = config.PROVIDERS[provider]["model"]
                    ui.console.print(f"Current model for [bold]{provider}[/bold]: [cyan]{current_model}[/cyan]")
                continue

            # URL Command
            if cmd == "/url":
                if len(cmd_parts) > 1:
                    new_url = cmd_parts[1]
                    provider = config.get_active_provider()
                    if len(cmd_parts) > 2:
                        provider = cmd_parts[1].lower()
                        new_url = cmd_parts[2]
                    
                    if provider in config.PROVIDERS:
                        config.save_url(new_url, provider)
                        ui.console.print(f"[green]URL for {provider} updated to: {new_url}[/green]")
                    else:
                        ui.show_error(f"Provider '{provider}' not found.")
                else:
                    provider = config.get_active_provider()
                    current_url = config.PROVIDERS[provider].get("url")
                    ui.console.print(f"Current URL for [bold]{provider}[/bold]: [dim]{current_url}[/dim]")
                continue

            # Search Provider Command
            if user_input.startswith("/search"):
                parts = user_input.split(" ")
                if len(parts) == 1:
                    ui.console.print("[bold]Available Search Providers:[/bold]")
                    active = config.get_active_search_provider()
                    for p in config.SEARCH_PROVIDERS:
                        status = "[green](active)[/green]" if p == active else ""
                        desc = config.SEARCH_PROVIDERS[p]["description"]
                        ui.console.print(f" - {p}: {desc} {status}")
                else:
                    target = parts[1].lower()
                    if config.set_active_search_provider(target):
                        ui.console.print(f"[green]Switched search provider to {target}.[/green]")
                    else:
                        ui.show_error(f"Search provider '{target}' not found.")
                continue

            # Token Command
            if user_input.startswith("/token"):
                parts = user_input.split(" ")
                if len(parts) == 1:
                    ui.console.print("\n[bold]Current API Tokens:[/bold]")
                    found = False
                    # AI Providers
                    all_providers = sorted(list(config.PROVIDERS.keys()))
                    for p in all_providers:
                        t = config.get_token(p)
                        if t:
                            masked = f"{t[:3]}...{t[-3:]}" if len(t) > 6 else "***"
                            ui.console.print(f"  • {p.capitalize():<12}: [cyan]{masked}[/cyan]")
                            found = True
                    # Search Providers
                    all_search = sorted(list(config.SEARCH_PROVIDERS.keys()))
                    for sp in all_search:
                        if sp == "duckduckgo": continue
                        t = config.get_search_token(sp)
                        if t:
                            masked = f"{t[:3]}...{t[-3:]}" if len(t) > 6 else "***"
                            ui.console.print(f"  • {sp.capitalize():<12}: [cyan]{masked}[/cyan]")
                            found = True
                    
                    if not found:
                        ui.console.print("[dim]  No tokens saved yet. Run '/token help' for setup guide.[/dim]")
                    continue

                # Check for help specifically
                if parts[1].lower() == "help":
                    ui.console.print("\n[bold yellow]🎫 Token Management Guide[/bold yellow]")
                    ui.console.print("Use the following commands to update your API keys:\n")
                    
                    # AI Providers
                    ui.console.print("[bold]AI Models:[/bold]")
                    ui.console.print("  • OpenAI:      [cyan]/token openai <sk-...>[/cyan]")
                    ui.console.print("  • Anthropic:   [cyan]/token anthropic <sk-ant-...>[/cyan]")
                    ui.console.print("  • HuggingFace: [cyan]/token huggingface <hf_...>[/cyan]")
                    ui.console.print("  • GitHub:      [cyan]/token github <token>[/cyan]")
                    ui.console.print("  • Gemini:      [cyan]/token gemini <AIza...>[/cyan]")
                    ui.console.print("  • Ollama:      [cyan]/token ollama <token>[/cyan]")
                    
                    # Tools
                    ui.console.print("\n[bold]Search Tools:[/bold]")
                    ui.console.print("  • Brave Search: [cyan]/token brave <BSA...>[/cyan]")
                    ui.console.print("  • Bing:         [cyan]/token bing <key>[/cyan]")
                    ui.console.print("  • Google:       [cyan]/token google <API_KEY:CX_ID>[/cyan]")
                    ui.console.print("  • DuckDuckGo:   [dim](No token required)[/dim]")
                    
                    ui.console.print("\n[dim]Note: Tokens are saved locally in ~/.goku/config.json[/dim]\n")
                    continue

                if len(parts) == 2:
                    token = parts[1]
                    provider = config.get_active_provider()
                    config.save_token(token, provider)
                    masked = f"{token[:3]}...{token[-3:]}" if len(token) > 6 else "***"
                    ui.console.print(f"[green]Token saved for {provider}: {masked}[/green]")
                elif len(parts) == 3:
                    provider = parts[1].lower()
                    token = parts[2]
                    # Support brave as a special case since it's not in PROVIDERS dict but in config.tokens
                    if provider in config.PROVIDERS or provider in config.SEARCH_PROVIDERS:
                        config.save_token(token, provider)
                        masked = f"{token[:3]}...{token[-3:]}" if len(token) > 6 else "***"
                        ui.console.print(f"[green]Token saved for {provider}: {masked}[/green]")
                    else:
                        ui.show_error(f"Provider '{provider}' not found.")
                else:
                    ui.console.print("Usage: /token [provider] <key> (or type '/token help')")
                continue

            # MCP Commands
            if user_input.startswith("/mcp"):
                parts = user_input.split(" ")
                if len(parts) > 1:
                    cmd = parts[1]
                    if cmd == "list":
                        if not engine.mcp_clients:
                            ui.console.print("No MCP servers connected.")
                        else:
                            ui.console.print("[bold]Connected MCP Servers:[/bold]")
                            for name in engine.mcp_clients:
                                ui.console.print(f" - {name}")
                            ui.console.print(f"\n[dim]{len(engine.mcp_tools)} tools available loaded.[/dim]")
                    elif cmd == "reload":
                        await engine.initialize_mcp()
                        ui.console.print("[green]MCP servers reloaded.[/green]")
                    else:
                        ui.console.print("Usage: /mcp [list|reload]")
                else:
                    ui.console.print("Usage: /mcp [list|reload]")
                continue
                
            if user_input.lower() in ["/clear", "clear"]:
                engine.clear_history()
                ui.console.clear() 
                ui.print_welcome() 
                ui.print_status(engine.mode)
                continue

            if user_input.lower() in ["/setup", "setup"]:
                ui.console.print("[yellow]Starting offline setup...[/yellow]")
                os.system(f"bash {config.GOKU_DIR}/scripts/setup_offline.sh")
                continue

            if user_input.lower() in ["/update", "update"]:
                ui.console.print("[yellow]Checking for updates...[/yellow]")
                repo_path_file = config.GOKU_DIR / "repo_path"
                if repo_path_file.exists():
                    repo_dir = repo_path_file.read_text().strip()
                else:
                    script_dir = os.path.dirname(os.path.realpath(__file__))
                    repo_dir = os.path.abspath(os.path.join(script_dir, "../../"))
                
                if os.path.exists(os.path.join(repo_dir, ".git")):
                    os.system(fr"cd {repo_dir} && git pull && find . -name install.sh -exec bash {{}} \;")
                    ui.console.print("[green]Update complete! Please restart goku.[/green]")
                else:
                    ui.show_error(f"Git repository not found at {repo_dir}. Please update manually using git pull.")
                break

            if user_input.startswith("/mode"):
                parts = user_input.split(" ")
                if len(parts) > 1:
                    mode = parts[1].lower()
                    if engine.set_mode(mode):
                        ui.console.print(f"[green]Switched to {mode} mode.[/green]")
                    else:
                        ui.show_error("Invalid mode. Use online or offline.")
                else:
                    ui.console.print(f"Current mode: [bold]{engine.mode}[/bold]")
                    ui.console.print("Usage: /mode [online|offline]")
                continue

            if user_input.lower() == "/online":
                engine.set_mode("online")
                ui.console.print("[green]Switched to online mode.[/green]")
                continue

            if user_input.lower() == "/offline":
                engine.set_mode("offline")
                ui.console.print("[yellow]Switched to offline mode.[/yellow]")
                continue
            
            if user_input == "/retry":
                if not last_user_input:
                    ui.show_error("No previous query to retry.")
                    continue
                
                while engine.history and engine.history[-1]["role"] != "user":
                    engine.history.pop()
                if engine.history and engine.history[-1]["role"] == "user":
                    engine.history.pop()
                
                user_input = last_user_input
                ui.console.print(f"[dim]Retrying: {user_input}[/dim]")

            if not user_input.startswith("/"):
                last_user_input = user_input

            try:
                # Use generate_async directly
                with ui.show_loading() as status:
                    response, error = await engine.generate_async(
                        user_input, 
                        status_obj=status
                    )
                
                if error:
                    ui.show_error(error)
                    if engine.mode == "online":
                        choice = await ui.ask_async("Online failed. Switch to offline? (y/n): ")
                        choice = choice.strip().lower()
                        if choice == 'y':
                            engine.set_mode("offline")
                            ui.console.print(f"[bold blue]You:[/bold blue] {user_input}")
                            with ui.show_loading():
                                response, error = await engine.generate_async(user_input)
                            if error:
                                if "binary not found" in str(error):
                                    ui.show_error(f"Offline support not installed. Run [bold green]goku setup[/bold green] to install.")
                                else:
                                    ui.show_error(f"Offline failed: {error}")
                            else:
                                ui.show_assistant_response(response)
                                ui.show_thought_panel()
                    continue
                
                ui.show_assistant_response(response)
            except KeyboardInterrupt:
                ui.console.print("\n[bold red]── Action Aborted by User ──[/bold red]")
                continue

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate limit" in err_str.lower():
                    ui.show_error(f"Rate limit exceeded: {err_str}")
                    ui.console.print("\n[bold yellow]💡 Pro Tip:[/bold yellow] You can switch providers with [cyan]/provider[/cyan] or change your search engine with [cyan]/search[/cyan].")
                    ui.console.print("Type [cyan]/provider[/cyan] to see other available options.\n")
                else:
                    ui.show_error(f"An unexpected error occurred: {err_str}")
                
                # We don't break here unless it's a fatal error
                continue

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            # Fatal error at the outer loop
            ui.show_error(f"Fatal CLI Error: {e}")
            break

    # Clean shutdown
    ui.console.print("[dim]Shutting down...[/dim]")
    await engine.close()

if __name__ == "__main__":
    asyncio.run(main())
