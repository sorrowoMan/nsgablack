"""Complete offline workbench themes, including native overlays.

The editor iframe receives the same theme separately. Switching presentation
never mutates a draft, a saved revision, or a run.
"""
from __future__ import annotations

THEMES = ("dark", "light", "system")
PALETTES = {
    "dark": {
        "background": "#11151d", "surface": "#191f2a", "raised": "#222b39",
        "sidebar": "#141a24", "editor": "#151b25", "ink": "#dce3ef",
        "muted": "#a5b1c5", "line": "#303b4c", "accent": "#a5baff",
        "accent_fill": "#3e5db6", "on_accent": "#ffffff", "accent_soft": "#28344e",
        "hover": "#253044", "focus": "#b0c1ff", "code": "#151b25",
        "error": "#ffb3bd", "error_soft": "#38252f", "warning": "#e9c58f",
        "warning_soft": "#332d23", "success": "#9bd6c1", "success_soft": "#20342e",
        "keyword": "#cbb0f3", "string": "#a5d1b9", "number": "#edc898",
    },
    "light": {
        "background": "#f5f6f8", "surface": "#ffffff", "raised": "#edf0f5",
        "sidebar": "#f0f2f6", "editor": "#ffffff", "ink": "#273347",
        "muted": "#606e83", "line": "#dce2eb", "accent": "#3457b4",
        "accent_fill": "#3457b4", "on_accent": "#ffffff", "accent_soft": "#e9eefb",
        "hover": "#edf1fa", "focus": "#3457b4", "code": "#f7f8fb",
        "error": "#a63143", "error_soft": "#fff0f2", "warning": "#7e5a16",
        "warning_soft": "#fff5df", "success": "#236852", "success_soft": "#eaf6f0",
        "keyword": "#7950a2", "string": "#2e7457", "number": "#80541d",
    },
}


def _variables(theme: str) -> str:
    values = ";".join(f"--wb-{name.replace('_', '-')}:{color}"
                      for name, color in PALETTES[theme].items())
    return f":root{{color-scheme:{theme};{values};}}"


def workspace_styles(theme: str = "dark") -> str:
    """Closed theme input: never interpolate arbitrary CSS from the browser."""
    if theme not in THEMES:
        raise ValueError("workspace_theme_invalid")
    variables = _variables("light" if theme == "system" else theme)
    if theme == "system":
        variables += "@media(prefers-color-scheme:dark){" + _variables("dark") + "}"
    return "<style>" + variables + _SHELL + "</style>"


_SHELL = r"""
:root{--text-color:var(--wb-ink);--background-color:var(--wb-background);--secondary-background-color:var(--wb-raised);--primary-color:var(--wb-accent);--border-color:var(--wb-line);}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--wb-background);color:var(--wb-ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;}
.stApp [data-testid="stHeader"]{height:12px;background:transparent;}
/* Streamlit keeps a fixed header above the compact toolbar. Its transparent
   area must not intercept code/workspace actions; real header controls keep
   their own hit targets (including the collapsed-sidebar button). */
header[data-testid="stHeader"]{pointer-events:none!important;}
header[data-testid="stHeader"] button,header[data-testid="stHeader"] [role="button"]{pointer-events:auto;}
.stApp [data-testid="stToolbar"]{display:flex;pointer-events:none;}
.stApp [data-testid="stAppDeployButton"],.stApp [data-testid="stMainMenu"]{display:none;}
.stApp [data-testid="stMainBlockContainer"]{max-width:none;padding:.8rem 1.15rem .8rem;}
.stApp [data-testid="stVerticalBlock"]{gap:.36rem;}
.stApp [data-testid="stMarkdownContainer"]{color:var(--wb-ink);}
.stApp [data-testid="stMarkdownContainer"] p{line-height:1.6;}
.stApp h1,.stApp h2,.stApp h3,.stApp h4{color:var(--wb-ink);}
.stApp h3{font-size:1rem!important;letter-spacing:-.015em;}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] *{font-size:.75rem;color:var(--wb-muted);line-height:1.5;}
.stApp [data-testid="stWidgetLabel"] p{font-size:.76rem;color:var(--wb-muted);font-weight:500;}
.stApp a,[role="dialog"] a{color:var(--wb-accent);}
.stApp hr,[role="dialog"] hr{border-color:var(--wb-line);}
.stApp :focus-visible,[role="dialog"] :focus-visible{outline-color:var(--wb-focus);}
section[data-testid="stSidebar"]{width:250px!important;min-width:250px!important;max-width:250px!important;background:var(--wb-sidebar);border-right:1px solid var(--wb-line);}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{background:var(--wb-sidebar);padding-left:0!important;padding-right:0!important;}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding:.85rem .75rem!important;}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{height:21px;min-height:21px;}
.workbench-brand{display:flex;align-items:center;gap:9px;color:var(--wb-ink);letter-spacing:.08em;font-size:11px;font-weight:600;margin:2px 0 9px;}
.workbench-brand span{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:6px;background:var(--wb-accent-fill);color:var(--wb-on-accent);letter-spacing:0;font-size:14px;}
.workspace-title{font-size:17px;line-height:1.35;font-weight:650;letter-spacing:-.02em;color:var(--wb-ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.workspace-subtitle{font-size:11px;color:var(--wb-muted);margin-top:4px;}
.st-key-workbench_toolbar{padding:2px 0 9px;}
.st-key-workbench_toolbar [data-testid="stHorizontalBlock"]{align-items:center;}
.st-key-workbench_categories{border-bottom:1px solid var(--wb-line);padding:2px 0 2px;margin-bottom:2px;}
.st-key-workbench_categories [role="radiogroup"]{gap:15px;}
.st-key-workbench_categories label{border:0;border-bottom:2px solid transparent;border-radius:0;padding:7px 0;margin:0!important;}
.st-key-workbench_categories label p{color:var(--wb-muted);font-size:13px;}
.st-key-workbench_categories label:has(input:checked){background:transparent;border-bottom-color:var(--wb-accent);}
.st-key-workbench_categories label:has(input:checked) p{color:var(--wb-ink);font-weight:600;}
.st-key-workbench_categories label>div:first-of-type{display:none;}
.explorer-heading{font-size:11px;letter-spacing:.06em;color:var(--wb-muted);font-weight:500;margin:11px 0 3px;}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="tertiary"]{border:0;background:transparent;padding:3px 6px;min-height:29px;justify-content:flex-start;color:var(--wb-muted);}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{justify-content:flex-start;background:var(--wb-accent-soft);color:var(--wb-accent);border-color:transparent;box-shadow:none;}
section[data-testid="stSidebar"] [data-testid="stButton"] button p{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
[class*="st-key-filetree_depth_"] button>div,[class*="st-key-filetree_depth_"] button>div>span{justify-content:flex-start!important;}
[class*="st-key-filetree_depth_"] button p{text-align:left;}
[class*="st-key-filetree_depth_1_"]{margin-left:9px;width:calc(100% - 9px)!important;}
[class*="st-key-filetree_depth_2_"]{margin-left:18px;width:calc(100% - 18px)!important;}
[class*="st-key-filetree_depth_3_"]{margin-left:27px;width:calc(100% - 27px)!important;}
[class*="st-key-filetree_depth_4_"],[class*="st-key-filetree_depth_5_"]{margin-left:34px;width:calc(100% - 34px)!important;}
.st-key-workbench_file_tabs{padding:0;margin:0;}
.st-key-workbench_file_tabs [data-testid="stButton"] button{border:0!important;border-radius:0!important;min-height:34px;background:var(--wb-background)!important;color:var(--wb-muted);box-shadow:none;padding:5px 9px;}
.st-key-workbench_file_tabs [data-testid="stButton"] button[kind="primary"]{color:var(--wb-ink)!important;background:var(--wb-editor)!important;border-bottom:2px solid var(--wb-accent)!important;}
.st-key-workbench_file_tabs [data-testid="stButton"] button p{font:12px/1.3 "Cascadia Code",Consolas,"Microsoft YaHei",monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.st-key-project_workspace_editor{background:var(--wb-editor);border:1px solid var(--wb-line);border-radius:0 0 6px 6px;padding:.4rem .55rem .3rem;box-shadow:none;}
.workbench-path{font:11px/1.6 "Cascadia Code",Consolas,"Microsoft YaHei",monospace;color:var(--wb-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:1px;}
.st-key-project_workspace_editor iframe{height:calc(100dvh - 242px)!important;min-height:410px;max-height:1200px;border:0;}
.st-key-project_workspace_editor [data-testid="stPopover"] button{min-height:28px;font-size:11px;padding:2px 7px;background:transparent;border-color:transparent;}
.st-key-project_workspace_editor [data-testid="stPopover"] button p{white-space:nowrap;}
.st-key-project_workspace_editor [data-testid="stTextArea"] textarea{font:14px/1.65 "Cascadia Code",Consolas,"Microsoft YaHei",monospace;background:var(--wb-editor);color:var(--wb-ink);tab-size:4;}
.st-key-workbench_inspector{background:var(--wb-surface);border:1px solid var(--wb-line);border-radius:6px;padding:.7rem .8rem;max-height:calc(100dvh - 160px);overflow-y:auto;overflow-x:hidden;}
.st-key-workbench_inspector [data-testid="stCode"] pre{font-size:12px;}
.st-key-workbench_inspector h3{font-size:1rem!important;}
.st-key-workbench_inspector_close button{width:30px;min-width:30px;padding:4px!important;}
.st-key-workbench_inspector_close button p{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;}
.st-key-workbench_results{background:var(--wb-surface);border:1px solid var(--wb-line);border-radius:6px;padding:.8rem .9rem;}
.st-key-workbench_run_actions{position:sticky;top:0;z-index:5;background:var(--wb-surface);padding:3px 0 7px;border-bottom:1px solid var(--wb-line);}
.st-key-workbench_run_status{background:var(--wb-surface);border:1px solid var(--wb-line);border-radius:5px;padding:.55rem .7rem;color:var(--wb-muted);}
.st-key-workbench_scope_notice{background:var(--wb-accent-soft);border-left:2px solid var(--wb-accent);padding:.3rem .65rem;border-radius:3px;}
.st-key-workbench_scope_notice p{font-size:12px;}
.stApp [data-testid="stButton"] button,.stApp [data-testid="stPopover"] button,.stApp [data-testid="stDownloadButton"] button,[role="dialog"] button[kind]{min-height:32px;border-radius:5px;border:1px solid var(--wb-line);background:var(--wb-surface);color:var(--wb-ink);font-size:.8rem;box-shadow:none;}
.stApp [data-testid="stButton"] button:hover,.stApp [data-testid="stPopover"] button:hover,[role="dialog"] button[kind]:hover{background:var(--wb-hover);border-color:var(--wb-muted);}
.stApp [data-testid="stButton"] button[kind="primary"],[role="dialog"] button[kind="primary"]{background:var(--wb-accent-fill);color:var(--wb-on-accent);border-color:var(--wb-accent-fill);}
.stApp [data-testid="stButton"] button:disabled,[role="dialog"] button:disabled{opacity:.5;}
.st-key-workbench_toolbar [data-testid="stButton"] button[kind="secondary"]{border-color:transparent;background:transparent;}
.st-key-workbench_toolbar [data-testid="stButton"] button[kind="secondary"]:hover{background:var(--wb-hover);}
.stApp [data-testid="stButton"] button p,.stApp [data-testid="stPopover"] button p,.stApp [data-testid="stDownloadButton"] button p{font-size:12px;font-weight:500;}
section[data-testid="stSidebar"] [data-testid="stPopover"] button p{white-space:nowrap;}
.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"],.stApp [data-baseweb="select"]>div,.stApp [data-baseweb="textarea"],[role="dialog"] [data-baseweb="input"],[role="dialog"] [data-baseweb="base-input"],[role="dialog"] [data-baseweb="select"]>div,[role="dialog"] [data-baseweb="textarea"]{background:var(--wb-raised);color:var(--wb-ink);border-color:var(--wb-line);border-radius:5px;font-size:12px;}
.stApp input,.stApp textarea,.stApp select,[role="dialog"] input,[role="dialog"] textarea,[role="dialog"] select{background:transparent;color:var(--wb-ink);caret-color:var(--wb-accent);}
.stApp input::placeholder,.stApp textarea::placeholder,[role="dialog"] input::placeholder{color:var(--wb-muted);opacity:.85;}
.stApp [data-baseweb="select"] svg,[role="dialog"] [data-baseweb="select"] svg{fill:var(--wb-muted);}
.stApp [data-testid="stNumberInput"] button{background:var(--wb-raised);color:var(--wb-ink);}
.stApp [data-testid="stCheckbox"] label,.stApp [data-testid="stRadio"] label,[role="dialog"] label{color:var(--wb-ink);}
.stApp [data-testid="stExpander"] details,[role="dialog"] [data-testid="stExpander"] details{border-color:var(--wb-line);background:transparent;color:var(--wb-ink);}
.stApp [data-testid="stExpander"] summary,[role="dialog"] [data-testid="stExpander"] summary{color:var(--wb-ink);}
.stApp [data-baseweb="tab-list"],[role="dialog"] [data-baseweb="tab-list"]{background:transparent;border-bottom:1px solid var(--wb-line);}
.stApp [data-baseweb="tab"],[role="dialog"] [data-baseweb="tab"]{background:transparent;color:var(--wb-muted);font-size:12px;}
.stApp [data-baseweb="tab"][aria-selected="true"],[role="dialog"] [data-baseweb="tab"][aria-selected="true"]{color:var(--wb-accent);}
.stApp [data-baseweb="tab-highlight"],[role="dialog"] [data-baseweb="tab-highlight"]{background:var(--wb-accent);}
.stApp [data-testid="stCode"],[role="dialog"] [data-testid="stCode"]{border:1px solid var(--wb-line);border-radius:5px;background:var(--wb-code);}
.stApp [data-testid="stCode"] pre,[role="dialog"] [data-testid="stCode"] pre{background:var(--wb-code)!important;color:var(--wb-ink)!important;}
.stApp [data-testid="stMarkdownContainer"] code,[role="dialog"] [data-testid="stMarkdownContainer"] code{background:var(--wb-raised);color:var(--wb-accent);}
.stApp [data-testid="stTable"] table,[role="dialog"] [data-testid="stTable"] table{color:var(--wb-ink);background:var(--wb-surface);}
.stApp [data-testid="stTable"] th,.stApp [data-testid="stTable"] td,[role="dialog"] [data-testid="stTable"] th,[role="dialog"] [data-testid="stTable"] td{border-color:var(--wb-line);}
.stApp [data-testid="stJson"],[role="dialog"] [data-testid="stJson"]{background:var(--wb-code);color:var(--wb-ink);}
.stApp [data-testid="stMetricLabel"],.stApp [data-testid="stMetricValue"]{color:var(--wb-ink);}
.stApp [data-testid="stMetricValue"]{font-size:1.45rem;}
.stApp [data-testid="stAlert"]{border-radius:5px;border:1px solid var(--wb-line);color:var(--wb-ink);background:var(--wb-raised);}
.stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"]{color:var(--wb-ink);}
[data-baseweb="popover"],[data-baseweb="popover"]>div,[data-testid="stPopoverBody"],[role="dialog"],[data-testid="stDialog"] [role="dialog"],[role="listbox"],[data-baseweb="menu"],[data-baseweb="tooltip"]{background:var(--wb-surface)!important;color:var(--wb-ink)!important;border-color:var(--wb-line)!important;}
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"],[role="dialog"] [data-testid="stCaptionContainer"],[data-baseweb="tooltip"]{color:var(--wb-muted)!important;}
[data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"],[role="dialog"] [data-testid="stMarkdownContainer"]{color:var(--wb-ink);}
[role="option"],[data-baseweb="menu"] li{color:var(--wb-ink)!important;background:var(--wb-surface)!important;}
[role="option"]:hover,[role="option"][aria-selected="true"],[data-baseweb="menu"] li:hover{background:var(--wb-hover)!important;}
[data-testid="stToast"]{background:var(--wb-raised)!important;color:var(--wb-ink)!important;border-color:var(--wb-line)!important;}
.workbench-empty{max-width:580px;margin:15vh auto 2rem;text-align:center;color:var(--wb-muted);}
.workbench-empty h2{font-size:1.6rem!important;color:var(--wb-ink);}
@media(max-width:1360px){.workbench-brand{font-size:0;letter-spacing:0;}}
@media(max-width:1280px){
 section[data-testid="stSidebar"]{width:218px!important;min-width:218px!important;max-width:218px!important;}
 .stApp [data-testid="stMainBlockContainer"]{padding:.8rem .75rem;}
 .workspace-title{font-size:16px;}
 .st-key-workbench_categories [role="radiogroup"]{gap:11px;}
}
@media(max-width:800px){
 .st-key-project_workspace_editor iframe{min-height:380px;}
 .st-key-workbench_inspector{max-height:none;}
}
"""

# Older imports use this constant; the runtime selects workspace_styles(theme).
STYLES = workspace_styles()
