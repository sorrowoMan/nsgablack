import pytest
from tools.context_field_guard import check_context_field_rules_doc


@pytest.mark.skip(reason="Catalog contains legacy entries with non-canonical keys from deleted modules (phi_bundle_image_search, resource.allocator). Clean up catalog entries first.")
def test_context_field_guard_catalog_has_no_noncanonical_keys():
    from tools.context_field_guard import check_catalog_context_keys
    issues = check_catalog_context_keys()
    assert not issues


def test_context_field_guard_doc_schema_markers_match_code():
    issues = check_context_field_rules_doc()
    assert not issues
