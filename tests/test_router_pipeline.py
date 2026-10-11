import pytest

from kshiti import pipeline
from kshiti.calculator import calculate
from kshiti.models import Answer
from kshiti.pipeline import calc_context, cross_check
from kshiti.router import rule_based_route

Q = {
    1: "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?",
    2: "I want a farm house on agricultural land. What is the minimum plot size and the maximum FAR?",
    3: "My development permission was granted in 2023. How long does it stay valid, and how many times can I renew it?",
    8: "What is the fee for building permission for a residential house?",
    10: "What is the minimum rear open space for a 150 sq m residential plot?",
    11: "Do I need separate development permission for a 300 sq m plot that matches the Development Plan? (Tip: this changed in August 2026.)",
    13: "What are the rules for lifts in a building taller than 15 m?",
    14: "मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?",
    15: "बिल्डिंग परमिशन की फीस कितनी है और किस नियम में लिखी है?",
    16: "How do I pay my property tax online?",
    17: "What is the current market rate for land in Kolar Road, Bhopal?",
    "headline": "My plot is 200 sq m on a 9 m road. How much gap do I leave at the front, how many floors can I build, and what fee do I pay?",
    "hinglish": "mera plot 200 sq m hai, 9 m sadak hai, aage kitni jagah chhodni hai?",
}


def test_q1_extracts_road_and_height():
    r = rule_based_route(Q[1])
    assert r.inputs.road_width_m == 10 and r.inputs.building_height_m == 9
    assert r.topics == ["front_setback"] and r.intent == "calculation"


def test_q10_rear_only():
    r = rule_based_route(Q[10])
    assert r.inputs.plot_area_sqm == 150 and r.topics == ["rear_setback"] and r.inputs.building_use == "residential"


def test_q14_hindi_plot_and_road():
    r = rule_based_route(Q[14])
    assert r.lang == "hi" and r.inputs.plot_area_sqm == 200 and r.inputs.road_width_m == 9
    assert r.topics == ["front_setback"]


def test_hinglish_question():
    r = rule_based_route(Q["hinglish"])
    assert r.lang == "hi" and r.inputs.plot_area_sqm == 200 and r.inputs.road_width_m == 9
    assert "front_setback" in r.topics


def test_headline_question_topics():
    r = rule_based_route(Q["headline"])
    assert r.inputs.plot_area_sqm == 200 and r.inputs.road_width_m == 9
    assert set(r.topics) == {"front_setback", "far", "height", "fee"}


@pytest.mark.parametrize("k", [2, 3, 11, 13])
def test_rule_questions_do_not_trigger_calculations(k):
    r = rule_based_route(Q[k])
    assert r.intent == "rule_question"
    assert "height" not in r.topics and "front_setback" not in r.topics


@pytest.mark.parametrize("k", [16, 17])
def test_out_of_scope(k):
    assert rule_based_route(Q[k]).intent == "out_of_scope"


@pytest.mark.parametrize("k", [8, 15])
def test_fee_questions(k):
    assert "fee" in rule_based_route(Q[k]).topics


def test_farm_house_never_gets_residential_figures():
    r = rule_based_route(Q[2])
    assert r.inputs.building_use == "other"
    out = calculate(r.inputs, r.topics)
    assert not out.results and out.notes_en


def test_how_far_is_not_floor_area_ratio():
    r = rule_based_route("How far must my balcony stay from a low-voltage overhead electric line, vertically and horizontally?")
    assert "far" not in r.topics
    assert "far" in rule_based_route("What is the FAR for a residential plot?").topics


def test_square_feet_converted():
    r = rule_based_route("My plot is 1500 sq ft on a 9 m road, front open space?")
    assert r.inputs.plot_area_sqm == pytest.approx(139.35, abs=0.01) and r.notes


def test_calc_context_and_cross_check_warns_on_missing_figure():
    calc = calculate(rule_based_route(Q[1]).inputs, ["front_setback"])
    assert "3.6 m" in calc_context(calc)
    ok = Answer(question=Q[1], text="Leave at least 3.6 m in front, Rule 56(1)(a).")
    cross_check(ok, calc)
    assert not ok.warnings
    bad = Answer(question=Q[1], text="Leave at least 3.0 m in front, Rule 56(1)(a).")
    cross_check(bad, calc)
    assert bad.warnings and "3.6 m" in bad.warnings[0].text_en


def test_pipeline_emits_figure_before_answer(monkeypatch):
    events = []

    def fake_ask(question, on_text=None, context=""):
        assert "3.6 m" in context
        on_text("3.6 m")
        return Answer(question=question, text="3.6 m, Rule 56(1)(a).")

    monkeypatch.setattr(pipeline, "ask", fake_ask)
    res = pipeline.run(Q[1], on_event=lambda kind, data: events.append(kind))
    assert events == ["route", "calc", "text", "done"]
    assert res.calc.results[0].display == "3.6 m" and res.seconds_to_first_figure is not None
