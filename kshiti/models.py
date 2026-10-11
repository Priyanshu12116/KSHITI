"""Data shapes shared by the engine, the interface and the PDF."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "hi"]
Status = Literal["answered", "not_found", "need_inputs", "unverified", "error"]


class Citation(BaseModel):
    rule: str
    title: str
    part: str
    page: int
    quote: str                       # exact source text (from the official data pack)
    supports: str = ""               # the sentence of the answer this quote backs
    verified: bool = False           # passed the word-for-word check
    is_table: bool = False           # numbers from a flattened table: check the PDF page


class Warning_(BaseModel):
    kind: Literal["amendment", "table", "unverified", "invented_rule", "info"]
    text_en: str
    text_hi: str
    source_url: str | None = None


class MissingInput(BaseModel):
    field: str
    label: str                       # in the question's language
    unit: str | None = None


class Timing(BaseModel):
    router_s: float | None = None
    first_token_s: float | None = None
    total_s: float | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class Answer(BaseModel):
    question: str
    lang: Lang = "en"
    status: Status = "answered"
    text: str = ""                                   # short answer, question's language
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[Warning_] = Field(default_factory=list)
    missing_inputs: list[MissingInput] = Field(default_factory=list)
    not_found_reason: str = ""
    suggestion: str = ""                             # where else to go (not-found)
    mentioned_rules: list[str] = Field(default_factory=list)
    model: str = ""
    timing: Timing = Field(default_factory=Timing)
    usage: Usage = Field(default_factory=Usage)
    error: str = ""

    @property
    def cited_rules(self) -> list[str]:
        seen: list[str] = []
        for c in self.citations:
            if c.rule not in seen:
                seen.append(c.rule)
        return seen
