from types import SimpleNamespace as NS

from kshiti.engine import build_request, parse_message
from kshiti.lang import detect_lang
from kshiti.rules import get_rule, rule_order
from kshiti.verify import verify


def test_request_has_every_rule_as_citable_document_and_one_cache_breakpoint():
    req = build_request("What is the front open space?")
    content = req["messages"][0]["content"]
    docs = [b for b in content if b["type"] == "document"]
    assert len(docs) == 106 and all(d["citations"] == {"enabled": True} for d in docs)
    assert [("cache_control" in d) for d in docs].count(True) == 1 and "cache_control" in docs[-1]
    assert content[-1]["type"] == "text" and "front open space" in content[-1]["text"]
    assert {t["name"] for t in req["tools"]} == {"report_not_found", "ask_missing_inputs"}


def _msg(*blocks, stop="end_turn"):
    usage = NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=90000, cache_creation_input_tokens=0)
    return NS(content=list(blocks), stop_reason=stop, model="claude-opus-5-5", usage=usage)


def test_citation_maps_to_rule_page_and_exact_table_text():
    doc_i = rule_order().index("56")
    idx = next(c.index for c in get_rule("56").chunks if "Width of street facing the plot" in c.text)
    raw = NS(type="content_block_location", document_index=doc_i, start_block_index=idx, end_block_index=idx + 1,
             cited_text=get_rule("56").chunks[idx].text)
    msg = _msg(NS(type="text", text="3.6 m front open space, Rule 56(1)(a).", citations=[raw]))
    ans = verify(parse_message("10 m street, 9 m tall: front open space?", msg))
    c = ans.citations[0]
    assert ans.status == "answered" and c.rule == "56" and c.page == 77 and c.verified and c.is_table
    assert ans.usage.cache_read_tokens == 90000


def test_not_found_tool():
    msg = _msg(NS(type="tool_use", name="report_not_found",
                  input={"reason": "Property tax is not in these rules.", "suggestion": "Ask the revenue section."}),
               stop="tool_use")
    ans = verify(parse_message("How do I pay my property tax online?", msg))
    assert ans.status == "not_found" and "Property tax" in ans.not_found_reason


def test_missing_inputs_tool():
    msg = _msg(NS(type="tool_use", name="ask_missing_inputs",
                  input={"prompt": "Need the road width.",
                         "missing": [{"field": "road_width_m", "label": "Road width", "unit": "m"}]}),
               stop="tool_use")
    ans = verify(parse_message("How much front space?", msg))
    assert ans.status == "need_inputs" and ans.missing_inputs[0].field == "road_width_m"


def test_language_detection():
    assert detect_lang("मेरा प्लॉट 200 वर्ग मीटर का है") == "hi"
    assert detect_lang("mera plot 200 sq m hai, aage kitni jagah chhodni hai?") == "hi"
    assert detect_lang("What is the fee for building permission for a residential house?") == "en"
