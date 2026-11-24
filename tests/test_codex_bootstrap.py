import pytest

from nsgablack.catalog import codex_bootstrap as bootstrap
from nsgablack.catalog.lab_knowledge import read_framework_basics


def test_native_guidance_uses_shared_body_and_preserves_unrelated_settings(tmp_path):
    agents = tmp_path / "AGENTS.md"
    config = tmp_path / "config.toml"
    agents.write_bytes(b"Personal instruction.\r\n")
    before = b'model="unchanged-model"\r\n# preserve this\r\n[mcp_servers.private]\r\ncommand="private-command"\r\n'
    config.write_bytes(before)
    dry = bootstrap.bootstrap(tmp_path)
    assert dry["status"] == "stale" and dry["project_doc_max_bytes"] == 32768
    assert config.read_bytes() == before and agents.read_bytes() == b"Personal instruction.\r\n"
    result = bootstrap.bootstrap(tmp_path, install=True)
    assert result["status"] == "installed"
    assert agents.read_bytes().startswith(b"Personal instruction.\r\n")
    assert read_framework_basics()["content"] in agents.read_text(encoding="utf-8")
    assert config.read_bytes().endswith(before)
    assert result["project_doc_max_bytes"] == 98304
    assert bootstrap.bootstrap(tmp_path)["status"] == "current"
    again = bootstrap.bootstrap(tmp_path, install=True)
    assert again["status"] == "current" and again["backup_path"] is None


def test_stale_managed_text_is_detected_and_only_managed_section_is_replaced(tmp_path):
    original = bootstrap.managed_section().replace("框架基础认识", "old foundation")
    agents = tmp_path / "AGENTS.md"
    agents.write_text("before\n" + original + "after\n", encoding="utf-8")
    assert bootstrap.bootstrap(tmp_path)["status"] == "stale"
    bootstrap.bootstrap(tmp_path, install=True)
    assert agents.read_text(encoding="utf-8") == "before\n" + bootstrap.managed_section() + "after\n"


def test_global_override_and_invalid_markers_fail_without_mutating(tmp_path):
    override = tmp_path / "AGENTS.override.md"
    override.write_text("User override", encoding="utf-8")
    with pytest.raises(ValueError, match="shadows_bootstrap"):
        bootstrap.bootstrap(tmp_path, install=True)
    override.unlink()
    (tmp_path / "AGENTS.md").write_text(bootstrap.START, encoding="utf-8")
    with pytest.raises(ValueError, match="markers_invalid"):
        bootstrap.bootstrap(tmp_path, install=True)
    assert not (tmp_path / "config.toml").exists()


def test_budget_edit_is_root_only_and_does_not_lower_existing_larger_limit():
    raw = b'project_doc_max_bytes=32768 # keep comment\n[profiles.special]\nproject_doc_max_bytes=1000\n'
    changed = bootstrap._budget_config(raw)
    assert changed == raw.replace(b"=32768", b"=98304", 1)
    larger = b'project_doc_max_bytes=200000\n'
    assert bootstrap._budget_config(larger) == larger


@pytest.mark.parametrize("value", ("32_768", "+32768", "0x8000"))
@pytest.mark.parametrize("key", ("project_doc_max_bytes", '"project_doc_max_bytes"'))
def test_budget_rewrites_complete_integer_without_inflating_it(value, key):
    raw = (key + " = " + value + " # retain comment\n[profiles.other]\nproject_doc_max_bytes=123\n").encode()
    changed = bootstrap._budget_config(raw)
    assert bootstrap._config(changed)["project_doc_max_bytes"] == 98304
    assert changed.endswith(b"# retain comment\n[profiles.other]\nproject_doc_max_bytes=123\n")


@pytest.mark.parametrize("trailing_comma", (False, True))
def test_multiline_arguments_preserve_comments_and_brackets_inside_strings(trailing_comma):
    raw = (b'[mcp_servers."black-framework"]\ncommand="python"\nargs=[\n'
           b' "-I", # do not remove this\n "-m",\n "nsgablack.catalog.mcp_server",\n'
           b' "--project-root", "private=C:/a]#b"' + (b"," if trailing_comma else b"") + b'\n # closing ] in comment\n]\n')
    changed = bootstrap._current_project_config(raw)
    before = bootstrap._config(raw)["mcp_servers"]["black-framework"]["args"]
    assert bootstrap._config(changed)["mcp_servers"]["black-framework"]["args"] == before + ["--include-current-project"]
    assert b"# do not remove this" in changed and b"# closing ] in comment" in changed


def test_different_server_using_same_registration_name_is_not_reconfigured():
    raw=b'[mcp_servers.black-framework]\ncommand="python"\nargs=["another_server.py"]\n'
    with pytest.raises(ValueError, match="command_not_recognized"):
        bootstrap._current_project_config(raw)


def test_budget_example_inside_instructions_is_not_treated_as_the_setting():
    raw=b'developer_instructions="""\nproject_doc_max_bytes=1"""\nproject_doc_max_bytes=32_768\n'
    changed=bootstrap._budget_config(raw)
    assert bootstrap._config(changed)["project_doc_max_bytes"] == 98304
    assert bootstrap._config(changed)["developer_instructions"] == bootstrap._config(raw)["developer_instructions"]


def test_current_project_opt_in_preserves_explicit_roots_and_unrelated_services(tmp_path):
    raw = (b'project_doc_max_bytes=98304\n[mcp_servers.black-framework]\n'
           b'command="python"\nargs=["-I","-m","nsgablack.catalog.mcp_server","--project-root","private=project"] # keep\n'
           b'[mcp_servers.other]\ncommand="do-not-touch"\n')
    (tmp_path/"config.toml").write_bytes(raw)
    bootstrap.bootstrap(tmp_path, install=True)
    actual = bootstrap._config((tmp_path/"config.toml").read_bytes())
    before = bootstrap._config(raw)
    expected_args = before["mcp_servers"]["black-framework"]["args"] + ["--include-current-project"]
    assert actual["mcp_servers"]["black-framework"]["args"] == expected_args
    assert actual["mcp_servers"]["other"] == before["mcp_servers"]["other"]
    assert b"# keep" in (tmp_path/"config.toml").read_bytes()
    assert bootstrap.bootstrap(tmp_path)["status"] == "current"
