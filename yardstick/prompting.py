"""Assemble chat messages for a variant + question (spec §13.2).

Schema presentation is held CONSTANT across variants (configs/schema_format.yaml);
the ONLY thing that differs between V1/V3 (zero-shot) and V2/V4 (few-shot) is the
presence of the worked examples. Few-shot examples come from configs/fewshot_examples.yaml
and are held-out (no db_id overlap with the 150-question sample — leakage constraint
§4.5/§11.3), identical across all questions so the example prefix can be prompt-cached.
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
FEWSHOT_PATH = REPO / "configs" / "fewshot_examples.yaml"


def format_user(schema_ddl: str, question_text: str) -> str:
    return f"Database schema:\n{schema_ddl}\n\nQuestion: {question_text}"


def format_assistant(sql: str, confidence: float) -> str:
    return f"```sql\n{sql}\n```\nCONFIDENCE: {confidence}"


@functools.lru_cache(maxsize=1)
def _fewshot_examples() -> list[dict]:
    if not FEWSHOT_PATH.exists():
        return []
    return yaml.safe_load(FEWSHOT_PATH.read_text()).get("examples", [])


def build_messages(variant_cfg: dict, question: dict) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": variant_cfg["system_prompt"]}]

    if variant_cfg["prompt_strategy"] == "few-shot":
        for ex in _fewshot_examples():
            messages.append({"role": "user",
                             "content": format_user(ex["schema_ddl"], ex["question"])})
            messages.append({"role": "assistant",
                             "content": format_assistant(ex["sql"], ex.get("confidence", 0.9))})

    messages.append({"role": "user",
                     "content": format_user(question["schema_ddl"], question["question_text"])})
    return messages
