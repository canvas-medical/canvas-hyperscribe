from evaluations.local_lab_tests import local_lab_tests


def test_local_lab_tests() -> None:
    result = local_lab_tests(["glucose"])

    assert result
    assert all(item.uuid == "" and item.code and item.label for item in result)
    assert local_lab_tests(["glucose", "no-such-keyword-zzz"]) == []
