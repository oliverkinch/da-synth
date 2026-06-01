"""Async OpenAI client wrapper."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from synth_da.cache import GenerationCache
from synth_da.config import Settings

Message = dict[str, str]

_DEFAULT_CACHE_PATH = Path(".cache") / "generations.db"


class GenerationClient:
    def __init__(self, settings: Settings, cache_path: Path = _DEFAULT_CACHE_PATH) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )
        self.model = settings.openai_model_name
        self.cache = GenerationCache(path=cache_path)

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.8,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        key = GenerationCache.make_key(
            model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        cached = self.cache.get(key=key)
        if cached is not None:
            return cached

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            **kwargs,
        )
        content: str | None = response.choices[0].message.content
        if content is None:
            raise ValueError("Model returned empty response")
        self.cache.set(key=key, value=content)
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
                    return await self.generate(messages=msgs, **kwargs)
                except Exception as e:
                    return e

        return await asyncio.gather(*[_bounded(m) for m in messages_list])
