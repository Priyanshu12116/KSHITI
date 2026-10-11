import re

from kshiti.rules import HEADER_RE, get_rule, load_rules, normalise_rule_no, rule_exists, rule_order


def _squash(s):
    return re.sub(r"\s+", " ", s).strip()


def test_all_rules_loaded_in_book_order():
    rules = load_rules()
    assert len(rules) == 106
    assert rule_order()[:3] == ["1", "2", "3"] and "26-B" in rules and rule_order()[-1] == "105"


def test_chunks_are_exact_source_text_without_headers():
    for r in load_rules().values():
        assert r.chunks, r.rule
        src = _squash("\n".join(line for line in r.text.split("\n") if not HEADER_RE.match(line)))
        for c in r.chunks:
            assert c.text.strip(), (r.rule, c.index)
            assert not any(HEADER_RE.match(line) for line in c.text.split("\n"))
            assert _squash(c.text) in src, (r.rule, c.index)
            assert r.page_start <= c.page <= r.page_end + 1, (r.rule, c.index, c.page)


def test_front_open_space_table_is_one_block_on_page_77():
    table = [c for c in get_rule("56").chunks if "Width of street facing the plot" in c.text][0]
    assert table.is_table and table.page == 77
    for row in ["3.0 meters", "3.6 meters", "4.5 meters", "6.0 meters"]:
        assert row in table.text


def test_rear_open_space_table_on_page_78():
    table = [c for c in get_rule("56").chunks if "Minimum Rear Open space" in c.text][0]
    assert table.is_table and table.page == 78 and "1.50" in table.text


def test_rule_number_normalising_and_existence():
    assert normalise_rule_no("Rule 26 B") == "26-B"
    assert normalise_rule_no("056") == "56"
    assert rule_exists("26-B") and rule_exists("17-a") and rule_exists("56")
    assert not rule_exists("140") and not rule_exists("0")
