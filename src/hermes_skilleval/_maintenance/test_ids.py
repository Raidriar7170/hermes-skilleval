"""Use the same pytest address convention for collection and JUnit comparison."""


def case_id(nodeid):
    from _pytest.junitxml import mangle_test_address

    names = mangle_test_address(nodeid)
    return ".".join(names[:-1]) + "::" + names[-1]
