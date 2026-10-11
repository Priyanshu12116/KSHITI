"""The rulebook: load the official rules, remove running headers, split each rule
into small quotable blocks, and remember the PDF page of every block.

Claude reads each rule as one citable document whose content blocks are the
chunks built here, so every citation maps straight back to a rule and a page.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = ROOT / "data" / "source" / "bhumi_vikas_rules.jsonl"
RULES_VERSION = "MP Bhumi Vikas Rules 2012, consolidated to 06-03-2025"

# "Rule 56        M.P. Bhumi Vikas Rules, 2012        78" -> PDF page 78 starts here.
HEADER_RE = re.compile(r"^\s*Rule\s+[\w\-\(\)\.,& ]+?\s{2,}M\.P\. Bhumi Vikas Rules, 2012\s+(\d+)\s*$")
# A line that starts a new clause: (1) (a) (iv) 1[ 2. Explanation Provided Note Table S.No.
CLAUSE_RE = re.compile(
    r"^\s*(\(\d{1,3}\)|\([a-z]{1,2}\)|\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\)|\d{1,2}\s*\[|"
    r"\d{1,3}\.\s|Explanation|Provided|Note|Table|S\.\s?No)",
    re.IGNORECASE,
)
MAX_CHUNK = 900   # characters; keeps quotes short enough to read at the counter
MAX_TABLE = 3400  # a table stays in one block so its header and rows are quoted together
TABLE_START_RE = re.compile(
    r"^\s*(S\.\s?No|S\.\s+[A-Z][a-z]|Item\s{3,}|\(1\)\s{3,}\(2\)|(?-i:TABLE)\b)", re.IGNORECASE | re.MULTILINE
)
# A lettered clause such as "(b) In case of ..." written as prose ends a table.
TABLE_END_RE = re.compile(r"^\s{0,12}\((?:[a-z]|[ivx]{1,4})\)\s+\S+(?:\s\S+){3,}\s*$")
MIN_CHUNK = 120   # merge tiny fragments into their neighbour


@dataclass(frozen=True)
class Chunk:
    rule: str
    index: int        # position inside the rule's document (= citation block index)
    page: int         # PDF page (1-based, the PDF's own count)
    text: str

    @property
    def is_table(self) -> bool:
        return bool(TABLE_START_RE.search(self.text))


@dataclass(frozen=True)
class Rule:
    rule: str
    title: str
    part: str
    page_start: int
    page_end: int
    text: str                       # original text from the data pack
    chunks: tuple[Chunk, ...] = field(default=())

    @property
    def label(self) -> str:
        return f"Rule {self.rule}"

    @property
    def clean_text(self) -> str:
        return "\n".join(c.text for c in self.chunks)


def _split_rule(rule_no: str, text: str, page_start: int) -> list[Chunk]:
    """Split a rule into chunks at blank lines and clause starts, tracking pages."""
    paragraphs: list[tuple[int, list[str]]] = []
    page = page_start
    current: list[str] = []
    current_page = page
    in_table = False

    def flush() -> None:
        nonlocal current
        if any(line.strip() for line in current):
            paragraphs.append((current_page, current))
        current = []

    for line in text.split("\n"):
        m = HEADER_RE.match(line)
        if m:
            page = int(m.group(1))
            continue                          # running header: not rule content
        if not line.strip():
            if in_table and current and not _table_done(current):
                continue                      # blank line inside a table body
            flush()
            in_table = False
            current_page = page
            continue
        if TABLE_START_RE.match(line) and not in_table:
            if current and sum(len(x) for x in current) > MIN_CHUNK:
                flush()
                current_page = page
            in_table = True
        elif in_table and TABLE_END_RE.match(line) and "   " not in line.strip():
            flush()                           # prose clause after the table
            in_table = False
            current_page = page
        elif in_table:
            pass                              # table rows never start a new block
        elif CLAUSE_RE.match(line) and current and sum(len(x) for x in current) > MIN_CHUNK:
            flush()
            current_page = page
        if not current:
            current_page = page
        current.append(line.rstrip())
    flush()

    # Merge small fragments forward, split oversized paragraphs at line boundaries.
    merged: list[tuple[int, str]] = []
    for pg, lines in paragraphs:
        block = "\n".join(lines).strip("\n")
        if merged and len(merged[-1][1]) < MIN_CHUNK and len(merged[-1][1]) + len(block) <= MAX_CHUNK:
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n" + block)
            continue
        limit = MAX_TABLE if TABLE_START_RE.search(block) else MAX_CHUNK
        if len(block) <= limit:
            merged.append((pg, block))
            continue
        buf: list[str] = []
        for line in block.split("\n"):
            if buf and sum(len(x) + 1 for x in buf) + len(line) > MAX_CHUNK:
                merged.append((pg, "\n".join(buf)))
                buf = []
            buf.append(line)
        if buf:
            merged.append((pg, "\n".join(buf)))

    return [Chunk(rule=rule_no, index=i, page=pg, text=t) for i, (pg, t) in enumerate(merged)]


def _table_done(lines: list[str]) -> bool:
    """A table body has started once a numbered data row has been seen."""
    return any(re.match(r"^\s*\d{1,2}\.\s+\S", x) for x in lines)


@lru_cache(maxsize=1)
def load_rules() -> dict[str, Rule]:
    rules: dict[str, Rule] = {}
    with RULES_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            no = str(row["rule"])
            chunks = tuple(_split_rule(no, row["text"], int(row["page_start"])))
            rules[no] = Rule(
                rule=no,
                title=row["title"].strip(),
                part=row["part"].strip(),
                page_start=int(row["page_start"]),
                page_end=int(row["page_end"]),
                text=row["text"],
                chunks=chunks,
            )
    return rules


def rule_order() -> list[str]:
    """Rule numbers in book order; position = citation document_index."""
    return list(load_rules().keys())


def get_rule(rule_no: str) -> Rule | None:
    return load_rules().get(normalise_rule_no(rule_no))


def normalise_rule_no(rule_no: str) -> str:
    """'Rule 26 B', '26b', '26-B' -> '26-B'; '056' -> '56'."""
    s = str(rule_no).strip().upper().replace("RULE", "").strip()
    m = re.match(r"^0*(\d+)\s*[-\s]?\s*([A-Z])?$", s)
    if not m:
        return s
    return f"{m.group(1)}-{m.group(2)}" if m.group(2) else m.group(1)


def rule_exists(rule_ref: str) -> bool:
    """True if a cited rule reference points to a real rule.

    Inserted rules such as 17-a, 12-A or 42-A live inside their parent rule's text
    (see the data dictionary), so they count as real when the parent exists and the
    inserted number appears in the parent's text.
    """
    rules = load_rules()
    norm = normalise_rule_no(rule_ref)
    if norm in rules:
        return True
    m = re.match(r"^(\d+)", norm)
    if not m or m.group(1) not in rules:
        return False
    parent = rules[m.group(1)]
    suffix = rule_ref.strip()[len(m.group(1)):].strip(" -").lower()
    return bool(suffix) and re.search(rf"{m.group(1)}\s*[-\(]?\s*{re.escape(suffix)}\b", parent.text, re.I) is not None


def rulebook_fingerprint() -> str:
    """SHA-256 of the rules file: printed on every answer slip."""
    return hashlib.sha256(RULES_FILE.read_bytes()).hexdigest()


def rule_titles() -> list[tuple[str, str]]:
    return [(r.rule, r.title) for r in load_rules().values()]
