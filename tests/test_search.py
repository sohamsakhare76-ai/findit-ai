from search import extract_object


def test_extract_supported_object():
    result = extract_object("Where is my laptop?")
    assert result == {"status": "ok", "object": "laptop"}


def test_extract_alias():
    result = extract_object("Find my phone")
    assert result == {"status": "ok", "object": "cell phone"}


def test_empty_query():
    assert extract_object("   ")["status"] == "empty"


def test_unsupported_object_is_not_faked():
    result = extract_object("Where is my calculator?")
    assert result["status"] == "unsupported"
    assert result["term"] == "calculator"
