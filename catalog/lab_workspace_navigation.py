"""Lazy file navigation over a frozen Project manifest; no file reads."""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath


def _folder_toggle(st, key, trigger):
    if st.session_state.get(trigger) is not True:
        return
    st.session_state[key] = not st.session_state.get(key, False)


def render_file_tree(st, paths, *, workspace_id, current_path, changed_paths, on_open, case_names):
    """Only render children of open folders, keeping large Projects light."""
    tree = {}
    for path in sorted(set(paths)):
        cursor = tree
        for part in PurePosixPath(path).parts[:-1]:
            cursor = cursor.setdefault(part + "/", {})
        cursor[PurePosixPath(path).name] = path

    def render(nodes, prefix="", depth=0):
        for name, value in sorted(nodes.items(), key=lambda item: (not isinstance(item[1], dict), item[0])):
            digest = hashlib.sha256((prefix + name).encode()).hexdigest()[:16]
            with st.container(key=f"filetree_depth_{depth}_{digest}"):
                if isinstance(value, dict):
                    folder = prefix + name
                    key = f"project_workspace::folder::{workspace_id}::{folder}"
                    if key not in st.session_state:
                        st.session_state[key] = str(current_path or "").startswith(folder)
                    opened = st.session_state[key]
                    st.button(name.rstrip("/"), key=key + "::toggle", icon=":material/folder_open:" if opened else ":material/folder:",
                              help=folder, use_container_width=True, on_click=_folder_toggle, args=(st, key, key + "::toggle"), type="tertiary")
                else:
                    mark = "  ●" if value in changed_paths else ""
                    trigger = f"project_workspace::tree::{workspace_id}::{value}"
                    st.button(name + mark, key=trigger,
                              icon=":material/description:", help=value, use_container_width=True,
                              type="primary" if value == current_path else "tertiary",
                              on_click=on_open, args=(st, workspace_id, value, case_names, trigger))
            if isinstance(value, dict) and opened:
                render(value, prefix + name, min(depth + 1, 5))
    render(tree)


def file_tab_label(path, changed=False):
    parts = PurePosixPath(path).parts
    name = "/".join(parts[-2:]) if len(parts) > 1 else path
    return name + ("  ●" if changed else "")
