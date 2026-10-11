import re

import pytest

from kshiti.calculator import CalcInputs, calculate, fee, front_setback, height_norms, rear_setback, table_text, tables


def _sq(s):
    return re.sub(r"\s+", " ", s).strip()


def test_every_table_row_appears_word_for_word_in_the_official_text():
    t = tables()
    for name in ["front_open_space", "rear_open_space", "far", "height_above_12_5", "permission_fee_residential"]:
        block = _sq(table_text(t[name]["rule"], t[name]["table_marker"]))
        assert block, name
        for row in t[name]["rows"]:
            assert _sq(row["row_text"]) in block, (name, row["row_text"])


@pytest.mark.parametrize("road,expected", [(6, 3.0), (9, 3.0), (9.01, 3.6), (10, 3.6), (12, 3.6), (12.5, 4.5),
                                           (18, 4.5), (18.5, 6.0), (30, 6.0)])
def test_front_open_space_rows_and_boundaries(road, expected):
    r = front_setback(CalcInputs(road_width_m=road))
    assert r.value == expected and r.verified and r.page == 77 and r.sub_rule == "56(1)(a)"


@pytest.mark.parametrize("area,expected", [(30, 0.0), (40, 0.0), (41, 1.5), (150, 1.5), (151, 2.5), (200, 2.5),
                                           (225, 2.5), (226, 3.0)])
def test_rear_open_space_rows_and_boundaries(area, expected):
    r = rear_setback(CalcInputs(plot_area_sqm=area))
    assert r.value == expected and r.verified and r.page == 78


@pytest.mark.parametrize("bua,permission", [(50, 750), (75, 750), (100, 1250), (200, 2000), (250, 3000), (300, 3000),
                                            (301, 4000), (1000, 10000), (2500, 25000), (2600, 50000)])
def test_residential_permission_fee_slabs(bua, permission):
    r = fee(CalcInputs(built_up_area_sqm=bua, building_use="residential"))
    assert r.value == permission + bua and r.verified and r.page == 36


def test_commercial_fee_has_50_percent_surcharge():
    r = fee(CalcInputs(built_up_area_sqm=200, building_use="commercial"))
    assert r.value == 2000 * 1.5 + 200


def test_sample_question_1_ten_metre_street_nine_metre_tall():
    out = calculate(CalcInputs(road_width_m=10, building_height_m=9), ["front_setback"])
    assert out.results[0].display == "3.6 m"


def test_sample_question_10_rear_space_150_sqm():
    out = calculate(CalcInputs(plot_area_sqm=150, building_use="residential"), ["rear_setback"])
    assert out.results[0].display == "1.5 m"


def test_sample_question_14_hindi_200_sqm_9m_road_front():
    out = calculate(CalcInputs(plot_area_sqm=200, road_width_m=9), ["front_setback"])
    assert out.results[0].display == "3.0 m"


def test_headline_counter_question_200_sqm_9m_road():
    out = calculate(CalcInputs(plot_area_sqm=200, road_width_m=9, building_use="residential"),
                    ["front_setback", "rear_setback", "far", "height", "fee"])
    got = {r.key: r for r in out.results}
    assert got["front_setback"].value == 3.0
    assert got["rear_setback"].value == 2.5
    assert got["far"].value == 1.25 and "250 sq m" in got["far"].display
    assert got["height"].value == 12.5
    assert got["fee"].value == 3000 + 250 and got["fee"].assumptions_en
    assert all(r.verified for r in out.results)


def test_tall_building_uses_table_4():
    r = height_norms(CalcInputs(road_width_m=18, plot_area_sqm=1600, frontage_m=22))
    assert r.value == 24 and r.verified


def test_missing_inputs_are_reported_not_assumed():
    out = calculate(CalcInputs(), ["front_setback", "rear_setback", "side_setback"])
    assert not out.results
    assert {m.key for m in out.missing} == {"front_setback", "rear_setback", "side_setback"}


def test_non_residential_open_space_not_calculated():
    out = calculate(CalcInputs(road_width_m=12, building_use="commercial"), ["front_setback"])
    assert not out.results and out.notes_en
