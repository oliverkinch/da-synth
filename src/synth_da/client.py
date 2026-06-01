"""Async OpenAI client wrapper."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from synth_da.config import Settings

Message = dict[str, str]


class GenerationClient:
    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
        self.model = settings.openai_model_name

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.8,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            **kwargs,
        )
        content: str | None = response.choices[0].message.content
        if content is None:
            raise ValueError("Model returned empty response")
        return content
