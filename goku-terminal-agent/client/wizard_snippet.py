
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
             inp.value = "http://localhost:11434" # Auto-fill default

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "wiz_skip":
            self.app.pop_screen()
            return
        
        if event.button.id == "wiz_save":
            provider_radio = self.query_one("#provider_select", RadioSet).pressed.id
            token_val = self.query_one("#wiz_token_input", Input).value
            
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
                    
                except Exception as e:
                    self.app.notify(f"Error saving: {e}", severity="error")
            
            self.app.pop_screen()
