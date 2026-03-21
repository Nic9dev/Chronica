"""
CSS Styles for Chronica UI Themes
"""
from typing import Dict

THEMES: Dict[str, str] = {
    "basic": """
    <style>
        :root {
            --bg-primary: #FFFFFF;
            --bg-secondary: #F5F5F5;
            --text-primary: #333333;
            --text-secondary: #666666;
            --accent: #2196F3;
            --border: #E0E0E0;
            --shadow: rgba(0, 0, 0, 0.1);
        }
        .stApp {
            background-color: var(--bg-primary);
            color: var(--text-primary);
        }
        .chat-message {
            background-color: var(--bg-secondary);
            border-left: 3px solid var(--accent);
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
        }
        .memory-card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px;
            margin: 5px 0;
            box-shadow: 0 2px 4px var(--shadow);
        }
    </style>
    """,
    
    "pop": """
    <style>
        :root {
            --bg-primary: #FFF0F5;
            --bg-secondary: #FFE4E1;
            --text-primary: #8B008B;
            --text-secondary: #DA70D6;
            --accent: #FF69B4;
            --border: #FFB6C1;
            --shadow: rgba(255, 105, 180, 0.2);
        }
        .stApp {
            background: linear-gradient(135deg, #FFF0F5 0%, #FFE4E1 100%);
            color: var(--text-primary);
            font-family: 'Comic Sans MS', 'Yu Gothic', sans-serif;
        }
        .chat-message {
            background-color: var(--bg-secondary);
            border-left: 4px solid var(--accent);
            padding: 12px;
            margin: 8px 0;
            border-radius: 15px;
            box-shadow: 0 3px 6px var(--shadow);
        }
        .memory-card {
            background: linear-gradient(135deg, #FFE4E1 0%, #FFB6C1 100%);
            border: 2px solid var(--accent);
            border-radius: 12px;
            padding: 12px;
            margin: 8px 0;
            box-shadow: 0 4px 8px var(--shadow);
        }
    </style>
    """,
    
    "tech": """
    <style>
        :root {
            --bg-primary: #0A0A0A;
            --bg-secondary: #1A1A1A;
            --text-primary: #00FF00;
            --text-secondary: #00CC00;
            --accent: #FF6600;
            --border: #00FF00;
            --shadow: rgba(0, 255, 0, 0.3);
        }
        .stApp {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'Courier New', 'Monaco', monospace;
        }
        .chat-message {
            background-color: var(--bg-secondary);
            border-left: 3px solid var(--accent);
            padding: 10px;
            margin: 5px 0;
            border-radius: 3px;
            box-shadow: 0 0 10px var(--shadow);
        }
        .memory-card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 5px;
            padding: 10px;
            margin: 5px 0;
            box-shadow: 0 0 15px var(--shadow);
        }
        .memory-card::before {
            content: "> ";
            color: var(--accent);
        }
    </style>
    """
}

def get_theme_css(theme: str) -> str:
    """テーマ名からCSSを取得"""
    return THEMES.get(theme, THEMES["basic"])
