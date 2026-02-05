"""
Goku TUI Theme Documentation
"""

class Theme:
    # Core Backgrounds
    BG_APP = "#0f172a"        # Slate 900
    BG_HEADER = "#1e293b"     # Slate 800
    BG_PANEL = "#111827"      # Gray 900
    BG_INPUT = "#1e293b"      # Slate 800
    
    # Borders & Separators
    BORDER_DEFAULT = "#334155" # Slate 700
    BORDER_FOCUS = "#3b82f6"   # Blue 500
    BORDER_ACCENT = "#8b5cf6"  # Violet 500

    # Text Colors
    TEXT_PRIMARY = "#f8fafc"   # Slate 50
    TEXT_SECONDARY = "#94a3b8" # Slate 400
    TEXT_MUTED = "#64748b"     # Slate 500
    TEXT_ACCENT = "#60a5fa"    # Blue 400
    
    # Message Colors
    MSG_USER_BG = "#1e40af"       # Blue 800
    MSG_USER_TEXT = "#f1f5f9"     # Slate 100
    MSG_AGENT_BG = "#1e293b"      # Slate 800
    MSG_AGENT_TEXT = "#e2e8f0"    # Slate 200
    
    # Status Colors
    STATUS_ONLINE = "#10b981"  # Emerald 500
    STATUS_OFFLINE = "#ef4444" # Red 500
    STATUS_BUSY = "#f59e0b"    # Amber 500

    # Common Styles
    CSS = f"""
    Screen {{
        background: {BG_APP};
        color: {TEXT_PRIMARY};
    }}

    /* Global Scrollbar styling */
    ScrollBar {{
        background: {BG_APP};
        color: {BORDER_DEFAULT};
    }}
    
    /* Input Fields */
    Input {{
        background: {BG_INPUT};
        border: wide {BORDER_DEFAULT};
        color: {TEXT_PRIMARY};
        padding: 0 1;
    }}
    
    Input:focus {{
        border: wide {BORDER_FOCUS};
    }}
    
    /* Buttons */
    Button {{
        background: {BG_HEADER};
        border: none;
        color: {TEXT_SECONDARY};
    }}
    
    Button:hover {{
        background: {BORDER_DEFAULT};
        color: {TEXT_PRIMARY};
    }}
    
    /* Panels */
    .panel {{
        background: {BG_PANEL};
        border: wide {BORDER_DEFAULT};
    }}
    
    .panel:focus {{
        border: wide {BORDER_FOCUS};
    }}
    """
