from routers.cases import _structured_case_value


def test_structured_case_value_with_dict():
    result = _structured_case_value({"complaint": "High BP", "duration": None})
    assert result == "High BP"


def test_structured_case_value_with_none():
    result = _structured_case_value(None)
    assert result == ""


def test_structured_case_value_with_empty_dict():
    result = _structured_case_value({})
    assert result == ""


def test_structured_case_value_with_dict_no_complaint():
    result = _structured_case_value({"other": "value"})
    assert result == "value"


def test_structured_case_value_with_list():
    result = _structured_case_value(["item1", "item2"])
    assert result == "item1, item2"


def test_structured_case_value_with_empty_list():
    result = _structured_case_value([])
    assert result == ""


def test_structured_case_value_with_stringified_dict():
    result = _structured_case_value("{'complaint': 'High BP (Hypertension)', 'duration': None, 'severity': None}")
    assert result == "High BP (Hypertension)"
