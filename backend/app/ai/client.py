"""Claude 호출 (SDK 는 여기서만 쓴다).  [재관]

기능마다 system 프롬프트(캐시) + 출력 JSON 스키마 한 쌍:
- 정제(A)     call_refine        prompts/refine_system.txt       · refine_schema.json
- 답장 초안(B) call_draft_reply   prompts/draft_reply_system.txt  · draft_reply_schema.json
- 공지 초안(B) call_draft_notice  prompts/draft_notice_system.txt · draft_notice_schema.json
- 할 일 · 일정(C) call_extract     prompts/extract_system.txt      · extract_schema.json

가린 글(masked)만 받는다. 원문 · 매핑표는 이 파일에 들어오지 않는다.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import anthropic

PROMPTS = Path(__file__).parent / "prompts"


def _load(name: str) -> tuple[str, dict]:
    return ((PROMPTS / f"{name}_system.txt").read_text(encoding="utf-8"),
            json.loads((PROMPTS / f"{name}_schema.json").read_text(encoding="utf-8")))


SYSTEM_PROMPT, REFINE_SCHEMA = _load("refine")
DRAFT_REPLY_PROMPT, DRAFT_REPLY_SCHEMA = _load("draft_reply")
DRAFT_NOTICE_PROMPT, DRAFT_NOTICE_SCHEMA = _load("draft_notice")
EXTRACT_PROMPT, EXTRACT_SCHEMA = _load("extract")

DEFAULT_EFFORT = "medium"  # 12건 시험(2026-11-08)에서 medium 으로 쟀음. 모델 · effort 는 더 시험해서 정한다
MAX_TOKENS = 4000
TIMEOUT_SECONDS = 90

# 안전 분류기가 거절하면 서버가 대신 다른 모델로 다시 돌려 주는 기능을 쓸 수 있는 모델.
# 폭언 · 협박이 든 글을 다루므로 켠다. (Haiku 는 이 기능이 없다)
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class ClaudeReply:
    text: str                      # 응답 본문 (JSON 문자열)
    stop_reason: str | None        # end_turn · refusal · max_tokens …
    stop_category: str | None = None  # refusal 일 때 분류 (cyber · bio …)
    model: str = ""
    seconds: float = 0.0
    usage: dict = field(default_factory=dict)  # input · output · cache_read · cache_write 토큰 수


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    """키는 backend/.env 의 ANTHROPIC_API_KEY. 처음 부를 때 한 번만 만든다."""
    from app.core.config import settings  # 늦게 불러서, 설정 없이도 이 파일을 import 할 수 있게

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 가 비어 있습니다 (backend/.env)")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=TIMEOUT_SECONDS, max_retries=2)


def default_model() -> str:
    from app.core.config import settings

    return settings.claude_model


def call_refine(masked: str, **kw) -> ClaudeReply:
    """가린 원문 하나를 정제 · 분석한다."""
    return call_json(SYSTEM_PROMPT, REFINE_SCHEMA, masked, **kw)


def call_draft_reply(masked: str, **kw) -> ClaudeReply:
    """가린 대화 + 교사 메모로 답장 초안을 쓴다."""
    return call_json(DRAFT_REPLY_PROMPT, DRAFT_REPLY_SCHEMA, masked, **kw)


def call_draft_notice(masked: str, **kw) -> ClaudeReply:
    """가린 공지 요점으로 공지 초안을 쓴다."""
    return call_json(DRAFT_NOTICE_PROMPT, DRAFT_NOTICE_SCHEMA, masked, **kw)


def call_extract(masked: str, **kw) -> ClaudeReply:
    """가린 대화에서 담임의 할 일 · 일정을 뽑는다."""
    return call_json(EXTRACT_PROMPT, EXTRACT_SCHEMA, masked, **kw)


def call_json(system: str, schema: dict, masked: str, *, model: str | None = None, effort: str = DEFAULT_EFFORT,
              client: anthropic.Anthropic | None = None) -> ClaudeReply:
    """가린 글 하나를 보내고 schema 형식의 JSON 을 받는다. 실패하면 anthropic 예외가 그대로 올라간다 (부르는 쪽이 잡음)."""
    client = client or get_client()
    model = model or default_model()
    params = dict(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": masked}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    start = time.time()
    if model in FALLBACK_MODELS:
        resp = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
    else:
        resp = client.messages.create(**params)
    seconds = time.time() - start

    text = next((b.text for b in resp.content if b.type == "text"), "")
    details = getattr(resp, "stop_details", None)
    u = resp.usage
    return ClaudeReply(
        text=text,
        stop_reason=resp.stop_reason,
        stop_category=getattr(details, "category", None) if details else None,
        model=resp.model,
        seconds=seconds,
        usage={
            "input": u.input_tokens,
            "output": u.output_tokens,
            "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
        },
    )
