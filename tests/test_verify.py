from kshiti.models import Answer, Citation
from kshiti.rules import get_rule
from kshiti.verify import mentioned_rules, quote_in_rule, verify


def _cit(rule, quote, is_table=False):
    r = get_rule(rule)
    return Citation(rule=rule, title=r.title, part=r.part, page=r.page_start, quote=quote, is_table=is_table)


def test_real_quote_passes_and_whitespace_does_not_matter():
    assert quote_in_rule("the sanction once\naccorded shall remain valid up to three years", "23")
    assert quote_in_rule("the  sanction once accorded   shall remain valid up to three years", "23")


def test_changed_words_fail():
    assert not quote_in_rule("the sanction once accorded shall remain valid up to five years", "23")
    assert not quote_in_rule("the sanction once accorded shall remain valid up to three years", "56")


def test_verify_drops_fake_quotes_and_marks_unverified():
    a = Answer(question="How long is permission valid?", text="It is valid for ten years under Rule 23.",
               citations=[_cit("23", "valid for ten years")])
    verify(a)
    assert a.citations == [] and a.status == "unverified"
    assert any(w.kind == "unverified" for w in a.warnings)


def test_verify_keeps_real_quotes():
    a = Answer(question="How long is permission valid?", text="Three years, Rule 23(1).",
               citations=[_cit("23", "the sanction once\naccorded shall remain valid up to three years")])
    verify(a)
    assert a.status == "answered" and a.citations[0].verified


def test_invented_rule_number_is_flagged():
    a = Answer(question="x", text="See Rule 140 and Rule 56.", citations=[_cit("56", "Front open spaces")])
    verify(a)
    assert any(w.kind == "invented_rule" and "140" in w.text_en for w in a.warnings)


def test_mentions_in_hindi_and_english():
    assert mentioned_rules("नियम 56(1) और Rule 21 तथा Rule 17-a") == ["56", "21", "17-a"]


def test_amendment_warning_for_question_11_only():
    q11 = Answer(question="Do I need separate development permission for a 300 sq m plot that matches the Development Plan?",
                 text="Rule 2.", citations=[_cit("2", "Authority having jurisdiction")])
    verify(q11)
    assert any(w.kind == "amendment" for w in q11.warnings)
    q3 = Answer(question="My development permission was granted in 2023. How long does it stay valid?",
                text="Three years, Rule 23(1).",
                citations=[_cit("23", "the sanction once\naccorded shall remain valid up to three years")])
    verify(q3)
    assert not any(w.kind == "amendment" for w in q3.warnings)


def test_table_quote_gets_pdf_check_warning():
    table = [c for c in get_rule("56").chunks if c.is_table][0]
    a = Answer(question="front gap?", text="3.6 m, Rule 56(1)(a).", citations=[_cit("56", table.text, is_table=True)])
    verify(a)
    assert any(w.kind == "table" for w in a.warnings)
