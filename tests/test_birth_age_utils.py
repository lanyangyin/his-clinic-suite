from datetime import date

from his_client.ui.birth_age import age_parts, age_text, birth_from_age, parse_id_birth


def test_parse_18_digit_id_extracts_birth():
    born, error = parse_id_birth("11010519491231002X")
    assert born == date(1949, 12, 31)
    assert error == ""


def test_parse_15_digit_id_extracts_birth():
    born, error = parse_id_birth("110105491231002")
    assert born == date(1949, 12, 31)
    assert "15" in error


def test_bad_checksum_still_extracts_but_warns():
    born, error = parse_id_birth("11010520240101123X")
    assert born == date(2024, 1, 1)
    assert "校验位" in error


def test_age_in_years_months_days():
    assert age_parts(date(2000, 1, 2), date(2026, 11, 14)) == (26, 10, 12)
    assert age_text(date(2000, 1, 2), date(2026, 11, 14)) == "26岁10个月12天"


def test_age_unknown_text():
    assert age_text(None) == "年龄不详"


def test_age_reverse_is_approximate_but_round_trips():
    today = date(2026, 11, 14)
    born = birth_from_age(30, 2, 3, today)
    assert born == date(1996, 9, 11)
    assert age_parts(born, today) == (30, 2, 3)
