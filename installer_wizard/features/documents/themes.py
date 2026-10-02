import re

THEMES = {
    "moderno": {"label": "Moderno", "primary": "1F4E79", "accent": "2E86DE", "accent2": "17A589", "dark": "1B2631",
                "light": "EAF2FB", "muted": "5D6D7E", "heading": "Calibri Light", "body": "Calibri",
                "chart": ["2E86DE", "17A589", "F39C12", "8E44AD", "E74C3C", "34495E"]},
    "aziendale": {"label": "Aziendale", "primary": "0B2545", "accent": "13315C", "accent2": "8DA9C4", "dark": "0B2545",
                  "light": "EEF4ED", "muted": "5C677D", "heading": "Cambria", "body": "Calibri",
                  "chart": ["13315C", "8DA9C4", "134074", "EEB902", "5C677D", "B23A48"]},
    "elegante": {"label": "Elegante", "primary": "2C2C54", "accent": "B08D57", "accent2": "706FD3", "dark": "1E1E2F",
                 "light": "F7F1E3", "muted": "6D6875", "heading": "Georgia", "body": "Cambria",
                 "chart": ["2C2C54", "B08D57", "706FD3", "40407A", "CC8E35", "84817A"]},
    "vivace": {"label": "Vivace", "primary": "6C3483", "accent": "E74C3C", "accent2": "F1C40F", "dark": "2C3E50",
               "light": "FDF2E9", "muted": "7F8C8D", "heading": "Trebuchet MS", "body": "Calibri",
               "chart": ["E74C3C", "F1C40F", "2ECC71", "3498DB", "9B59B6", "E67E22"]},
    "minimal": {"label": "Minimal", "primary": "222222", "accent": "555555", "accent2": "999999", "dark": "111111",
                "light": "F4F4F4", "muted": "777777", "heading": "Arial", "body": "Arial",
                "chart": ["222222", "666666", "999999", "BBBBBB", "444444", "DDDDDD"]},
    "natura": {"label": "Natura", "primary": "1E5631", "accent": "4C9A2A", "accent2": "A4DE02", "dark": "1B3A2B",
               "light": "EEF7E9", "muted": "5F7161", "heading": "Calibri Light", "body": "Calibri",
               "chart": ["1E5631", "4C9A2A", "A4DE02", "68BB59", "ACDF87", "76BA1B"]},
    "tech": {"label": "Tech", "primary": "0F172A", "accent": "06B6D4", "accent2": "8B5CF6", "dark": "020617",
             "light": "ECFEFF", "muted": "64748B", "heading": "Segoe UI", "body": "Segoe UI",
             "chart": ["06B6D4", "8B5CF6", "22C55E", "F59E0B", "EF4444", "64748B"]},
}
DEFAULT = "moderno"
HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def pick(name: str | None, palette: list | None = None, font: str | None = None) -> dict:
    theme = dict(THEMES.get(str(name or "").lower().strip(), THEMES[DEFAULT]))
    colors = [c.lstrip("#").upper() for c in (palette or []) if isinstance(c, str) and HEX.match(c)]
    if colors:
        theme["primary"] = colors[0]
        theme["accent"] = colors[1] if len(colors) > 1 else colors[0]
        theme["chart"] = colors + [c for c in theme["chart"] if c not in colors]
    if font and isinstance(font, str) and 2 < len(font) < 40:
        theme["body"] = font.strip()
        theme["heading"] = font.strip()
    return theme


def rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def readable_on(hex_color: str) -> str:
    r, g, b = rgb(hex_color)
    return "1B1B1B" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "FFFFFF"
