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

            with ui.show_loading():
                response, error = engine.generate(user_input)
            
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
