from tools.context_field_guard import check_catalog_context_keys, check_context_field_rules_doc


def test_context_field_guard_catalog_has_no_noncanonical_keys():
    issues = check_catalog_context_keys()
    assert not issues


def test_context_field_guard_doc_schema_markers_match_code():
    issues = check_context_field_rules_doc()
    assert not issues
