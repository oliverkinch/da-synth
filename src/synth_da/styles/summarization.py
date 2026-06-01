"""Summarization generator."""

from __future__ import annotations

import random
from typing import Any

from synth_da.client import GenerationClient, Message
from synth_da.config import DatasetConfig
from synth_da.styles.base import BaseGenerator

_SYSTEM_PROMPTS = [
    "Du er en hjælpsom assistent. Svar altid på dansk.",
    "Du er præcis og kortfattet. Opsummer tekster klart og på dansk.",
]

_REQUEST_STYLES = [
    "Kan du opsummere denne tekst?",
    "Giv mig et kortfattet resumé af teksten herunder.",
    "Hvad er de vigtigste pointer i teksten nedenfor?",
    "Opsummer venligst teksten i et par sætninger.",
    "Kan du give mig de vigtigste punkter fra teksten som bulletpunkter?",
    "Opsummer teksten i præcis tre sætninger.",
    "Forklar kort hvad teksten handler om.",
]

_QUALITY_CRITERIA = """\
Et højkvalitets opsummeringseksempel:
- Resuméet er trofast over for kildeteksten — ingen opfundne detaljer
- De vigtigste pointer dækkes, ikke kun de første sætninger
- Resuméet er markant kortere end kildeteksten
- Resuméet kan stå alene uden reference til "teksten ovenfor"
- Sproget er naturligt dansk med korrekt register
- Formatkravet (prosa, bulletpunkter, antal sætninger) følges præcist
"""


class SummarizationGenerator(BaseGenerator):
    def __init__(self, config: DatasetConfig, client: GenerationClient) -> None:
        super().__init__(config=config, client=client)

    async def build_prompt(self, row: dict[str, Any], persona_text: str | None) -> list[Message]:
        text = self.config.render_text(row=row)
        request_style = random.choice(_REQUEST_STYLES)

        persona_note = ""
        if persona_text:
            persona_note = (
                f"\n\nFormulér opsummeringen til en person med denne profil:\n{persona_text}"
            )

        generation_prompt = f"""\
Generér ét højkvalitets opsummeringseksempel på dansk.

Brugerens forespørgsel: "{request_style}"
{persona_note}

{_QUALITY_CRITERIA}

Kildetekst:
---
{text[:6000]}
---

Svar i præcis dette format:
BRUGER: <brugerbesked inkl. den fulde kildetekst og forespørgslen>
ASSISTENT: <opsummering>"""

        generation_messages: list[Message] = [
            {"role": "user", "content": generation_prompt},
        ]

        raw = await self.client.generate(messages=generation_messages, temperature=0.8)
        user_msg, assistant_msg = _parse_summarization(raw=raw)

        system_msgs = self._maybe_system_prompt(content=random.choice(_SYSTEM_PROMPTS))
        return system_msgs + [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ]


def _parse_summarization(raw: str) -> tuple[str, str]:
    user_msg = ""
    assistant_msg = ""
    lines = raw.splitlines()
    in_assistant = False
    assistant_lines: list[str] = []
    in_user = False
    user_lines: list[str] = []

    for line in lines:
        if line.startswith("BRUGER:"):
            in_user = True
            in_assistant = False
            user_lines.append(line.removeprefix("BRUGER:").strip())
        elif line.startswith("ASSISTENT:"):
            in_assistant = True
            in_user = False
            assistant_lines.append(line.removeprefix("ASSISTENT:").strip())
        elif in_assistant:
            assistant_lines.append(line)
        elif in_user:
            user_lines.append(line)

    user_msg = "\n".join(user_lines).strip()
    assistant_msg = "\n".join(assistant_lines).strip()

    if not user_msg or not assistant_msg:
        raise ValueError(f"Could not parse summarization from model output: {raw!r}")
    return user_msg, assistant_msg
