import sys
import os
from .engine import GokuEngine
from . import ui
from . import config

def main():
    engine = GokuEngine()
    
    # Check if we are in setup mode
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        # This will be handled by the bash script calling goku setup? 
        # Actually it's better to just tell the user to run the setup script.
        # But we can trigger it here if needed.
        os.system("bash ~/.goku/scripts/setup_offline.sh")
        return

    # Initialize MCP
    ui.console.print("[dim]Initializing tools...[/dim]")
    import asyncio
    asyncio.run(engine.initialize_mcp())

    ui.print_welcome()

    # Onboarding: Check for token
    if not config.HF_TOKEN:
        ui.console.print("[yellow]HuggingFace Token not found![/yellow]")
        ui.console.print("Goku needs a [bold]Read[/bold] token to use the online mode.")
        ui.console.print("Get one at: [link=https://huggingface.co/settings/tokens]https://huggingface.co/settings/tokens[/link]\n")
        new_token = ui.console.input("[bold cyan]Enter your HF Token (or press Enter to skip and use offline mode): [/bold cyan]").strip()
        if new_token:
            config.save_token(new_token)
            config.HF_TOKEN = new_token
            ui.console.print("[green]Token saved! Online mode activated.[/green]")
        else:
            ui.console.print("[bold yellow]Skipping token. Online mode will fail until a token is added via /token.[/bold yellow]")

    ui.print_status(engine.mode)

    last_user_input = None
    while True:
        try:
            user_input = ui.get_user_input().strip()
            
            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit"]:
                break
            
            if user_input.lower() == "/help":
                ui.print_help()
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
                        asyncio.run(engine.initialize_mcp())
                        ui.console.print("[green]MCP servers reloaded.[/green]")
                    else:
                        ui.console.print("Usage: /mcp [list|reload]")
                else:
                    ui.console.print("Usage: /mcp [list|reload]")
                continue
                
            if user_input.lower() == "/clear":
                engine.clear_history()
                ui.console.clear()  # Clear the terminal screen
                ui.print_welcome()  # Redisplay the welcome header
                ui.print_status(engine.mode)
                continue

            if user_input.lower() in ["/setup", "setup"]:
                ui.console.print("[yellow]Starting offline setup...[/yellow]")
                os.system(f"bash {config.GOKU_DIR}/scripts/setup_offline.sh")
                continue

            if user_input.startswith("/token "):
                token = user_input.split(" ", 1)[1].strip()
                config.save_token(token)
                config.HF_TOKEN = token
                ui.console.print("[green]Token saved successfully![/green]")
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

            if user_input.startswith("/mode "):
                mode = user_input.split(" ")[1].lower()
                if engine.set_mode(mode):
                    ui.console.print(f"[green]Switched to {mode} mode.[/green]")
                else:
                    ui.show_error("Invalid mode. Use online or offline.")
                continue
            
            if user_input == "/retry":
                if not last_user_input:
                    ui.show_error("No previous query to retry.")
                    continue
                
                # Clean history of the last (possibly incomplete) turn
                while engine.history and engine.history[-1]["role"] != "user":
                    engine.history.pop()
                if engine.history and engine.history[-1]["role"] == "user":
                    engine.history.pop()
                
                user_input = last_user_input
                ui.console.print(f"[dim]Retrying: {user_input}[/dim]")

            # Save for potential retry before processing command-like inputs
            if not user_input.startswith("/"):
                last_user_input = user_input

            try:
                with ui.show_loading() as status:
                    response, error = engine.generate(
                        user_input, 
                        status_obj=status
                    )
                
                if error:
                    ui.show_error(error)
                    if engine.mode == "online":
                        choice = ui.console.input("[bold yellow]Online failed. Switch to offline? (y/n): [/bold yellow]").lower()
                        if choice == 'y':
                            engine.set_mode("offline")
                            # Retry automatically
                            with ui.show_loading():
                                response, error = engine.generate(user_input)
                            if error:
                                if "binary not found" in str(error):
                                    ui.show_error(f"Offline support not installed. Run [bold green]goku setup[/bold green] to install.")
                                else:
                                    ui.show_error(f"Offline failed: {error}")
                            else:
                                ui.show_assistant_response(response)
                    continue
                
                ui.show_assistant_response(response)
            except KeyboardInterrupt:
                ui.console.print("\n[bold red]── Action Aborted by User ──[/bold red]")
                continue

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            ui.show_error(str(e))

if __name__ == "__main__":
    main()
