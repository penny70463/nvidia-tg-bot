from __future__ import annotations

from openai import AsyncOpenAI

from bot.config import settings


class NIMClient:
    def __init__(self) -> None:
        self.model = settings.nvidia_model

    async def chat(self, messages: list[dict[str, str]]) -> str:
        settings.require_nvidia()
        client = AsyncOpenAI(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
        )
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            return "\n".join(
                part.text for part in content if getattr(part, "type", None) == "text"
            ).strip()
        return (content or "").strip()
