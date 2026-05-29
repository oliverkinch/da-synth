"""Async OpenAI client wrapper."""

from __future__ import annotations

import asyncio
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
            **kwargs,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Model returned empty response")
        return content

    async def generate_batch(
        self,
        messages_list: list[list[Message]],
        concurrency: int = 20,
        **kwargs: Any,
    ) -> list[str | Exception]:
        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded(msgs: list[Message]) -> str | Exception:
            async with semaphore:
                try:
                    return await self.generate(msgs, **kwargs)
                except Exception as e:
                    return e

        return await asyncio.gather(*[_bounded(m) for m in messages_list])
