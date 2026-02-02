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
                
            if user_input.lower() == "/clear":
                engine.clear_history()
                ui.console.print("[yellow]History cleared.[/yellow]")
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
                    # We need to find the install.sh relative to the repo root
                    # Your project has it in goku-termux-agent/install.sh
                    os.system(f"cd {repo_dir} && git pull && find . -name install.sh -exec bash {{}} \;")
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
                if not engine.history:
                    ui.show_error("No previous query to retry.")
                    continue
                # Pop the last assistant message and user message to retry
                last_user_query = engine.history.pop()["content"] if engine.history[-1]["role"] == "assistant" else None
                # Actually if last was user, we just use it. If last was assistant, we need to pop and use the one before.
                # Simplified: just pop assistant if exists, then pop user and use it.
                if engine.history and engine.history[-1]["role"] == "assistant":
                    engine.history.pop()
                if engine.history and engine.history[-1]["role"] == "user":
                    user_input = engine.history.pop()["content"]
                else:
                    ui.show_error("Could not find previous query.")
                    continue

            with ui.show_loading() as status:
                response, error = engine.generate(user_input, status_callback=lambda m: status.update(f"[bold green]{m}"))
            
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
                            ui.show_error(f"Offline also failed: {error}")
                        else:
                            ui.show_assistant_response(response)
                continue
            
            ui.show_assistant_response(response)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            ui.show_error(str(e))

if __name__ == "__main__":
    main()
