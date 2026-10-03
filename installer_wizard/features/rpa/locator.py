from features.brain import sight as seeing
from features.vision.ui_anchor import Screen, UiElement, parse_elements, prompt_for


class VisionLocator:
    async def locate(self, png: bytes, query: str, screen: Screen) -> list[UiElement]:
        data, _ = await seeing.look(png, prompt_for(query, screen), as_json=True, max_tokens=500)
        return parse_elements(data, screen)
