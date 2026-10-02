import html
import re
import unicodedata

class TextSanitizer:
    DANGEROUS_SHELL_PATTERNS = re.compile(r"(\||;|`|\$|\&\&|\|\||>|<|\n|\r)")

    @staticmethod
    def sanitize_plain_text(input_text: str) -> str:
        if not input_text:
            return ""
        normalized = unicodedata.normalize("NFKC", input_text)
        escaped = html.escape(normalized)
        return escaped.strip()

    @staticmethod
    def sanitize_command_param(param_text: str) -> str:
        if not param_text:
            return ""
        normalized = unicodedata.normalize("NFKC", param_text)
        stripped = TextSanitizer.DANGEROUS_SHELL_PATTERNS.sub("", normalized)
        return stripped.strip()

    @staticmethod
    def validate_entity_identifier(identifier: str) -> bool:
        pattern = re.compile(r"^[a-zA-Z0-9_\-\.]+$")
        return bool(pattern.match(identifier))
