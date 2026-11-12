"""Catalog layout overrides, applied after the shared workbench theme."""
from .ui_theme import WORKSPACE_CSS


DASHBOARD_CSS = WORKSPACE_CSS + """
<style>
/* A shared browse surface, with a compact index and a generous reading area. */
.stApp .block-container:has(.st-key-catalog_workspace) { padding-top:3rem; padding-bottom:2rem; }
.stApp:has(.st-key-catalog_topbar) [data-testid="stHeader"] { background:transparent; pointer-events:none; }
.stApp:has(.st-key-catalog_topbar) [data-testid="stHeader"] button { pointer-events:auto; }
.stApp:has(.st-key-catalog_topbar) [data-testid="stToolbar"] { visibility:hidden; pointer-events:none; }
.stApp:has(.st-key-catalog_topbar) [data-testid="stExpandSidebarButton"] { visibility:visible; pointer-events:auto; }
.stApp:has(.st-key-catalog_topbar) [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] { color:var(--workspace-nav-text)!important; }
.stApp:has(.st-key-catalog_topbar) [data-testid="stSidebar"][aria-expanded="false"] { width:0!important; min-width:0!important; max-width:0!important; flex-basis:0!important; }
.stApp:has(.st-key-catalog_topbar) [data-testid="stAppDeployButton"],
.stApp:has(.st-key-catalog_topbar) #MainMenu { display:none; }
.catalog-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; margin:0 0 .55rem; }
.catalog-heading .heading-kicker { font-size:.63rem; margin-bottom:.25rem; }
.stApp .catalog-heading h1.heading-title { font-size:1.75rem!important; margin-bottom:.2rem; }
.stApp .catalog-heading .heading-subtitle { font-size:.83rem; line-height:1.5; }
.st-key-catalog_topbar, .st-key-catalog_search { gap:.4rem; }
.catalog-mode-badge { flex-shrink:0; display:inline-flex; align-items:center; gap:.4rem; color:var(--catalog-muted); background:white; border:1px solid var(--catalog-line); border-radius:7px; padding:.3rem .6rem; font-size:.71rem; font-weight:550; }
.catalog-mode-badge::before { content:""; width:5px; height:5px; border-radius:50%; background:var(--catalog-accent); }
.catalog-sidebar-note { color:#a8b3c9; font-size:.72rem; line-height:1.65; padding-top:.9rem; border-top:1px solid #30394e; margin-top:.4rem; }
[data-testid="stSidebar"] .catalog-section-title { color:#a8b3c9; font-size:.74rem; }

.st-key-catalog_search { background:transparent; border:0; padding:0; margin:0 0 .6rem; }
.st-key-catalog_search [data-testid="stCaptionContainer"] p { font-size:.73rem!important; line-height:1.5!important; margin:0; }
.st-key-catalog_search [data-testid="stTextInput"] input { min-height:42px; font-size:.875rem; padding-left:.85rem; }
.st-key-catalog_search [data-baseweb="select"] > div { min-height:42px; }
.st-key-catalog_search [data-testid="stHorizontalBlock"] { align-items:center; }
.st-key-catalog_intents { margin-top:0; }
.st-key-catalog_intents [data-testid="stButton"] button { border:1px solid var(--catalog-line); background:white; color:#526078; border-radius:6px; min-height:30px; padding:.2rem .55rem; }
.st-key-catalog_intents [data-testid="stButton"] button p { font-size:.73rem; font-weight:450; }
.st-key-catalog_intents [data-testid="stButton"] button:hover { color:var(--catalog-accent); border-color:#c5c2ed; background:#f4f3ff; }

.st-key-catalog_workspace { border:1px solid var(--catalog-line); border-radius:12px; background:white; padding:0; min-width:0; }
.st-key-catalog_workspace [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-catalog_results) { gap:0; align-items:stretch; }
.st-key-catalog_workspace [data-testid="stColumn"]:has(.st-key-catalog_results) { flex:0 0 310px; width:310px; min-width:280px; max-width:330px; }
.st-key-catalog_workspace [data-testid="stColumn"]:has(.st-key-catalog_detail) { flex:1 1 0; width:0; min-width:0; }
.st-key-catalog_results, .st-key-catalog_detail { min-width:0; border:0; box-shadow:none; }
.st-key-catalog_results { background:#fafbfe; border-right:1px solid var(--catalog-line); border-radius:11px 0 0 11px; padding:.85rem .65rem .8rem; height:100%; gap:.45rem; }
.st-key-catalog_detail { background:white; border-radius:0 11px 11px 0; padding:1.05rem 1.4rem 1.4rem; gap:.55rem; }
.st-key-catalog_results > [data-testid="stVerticalBlock"] { gap:.5rem; }
.st-key-catalog_detail > [data-testid="stVerticalBlock"] { gap:.75rem; }
.catalog-result-meta { display:flex; align-items:center; justify-content:space-between; gap:.5rem; color:var(--catalog-muted); font-size:.75rem; line-height:1.5; padding:0 .45rem; margin:0 0 .35rem; }
.catalog-result-meta strong { color:var(--catalog-ink); font-weight:650; }
.catalog-list-heading { display:flex; align-items:center; justify-content:space-between; gap:.5rem; color:var(--catalog-ink); font-size:.82rem; font-weight:650; line-height:1.5; padding:0 .45rem; margin:0; }
.catalog-list-heading span { color:var(--catalog-muted); font-size:.73rem; font-weight:400; white-space:nowrap; }

/* Native radio semantics and keyboard selection, styled as readable component rows. */
.st-key-catalog_component_list { border:0; padding:0; scrollbar-width:thin; scrollbar-color:#d4d9e4 transparent; }
.st-key-catalog_component_list [data-testid="stRadio"] [role="radiogroup"] { gap:.3rem; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"] { position:relative; align-items:flex-start; width:100%; margin:0; min-height:48px; padding:.6rem .75rem; border:1px solid transparent; border-radius:7px; background:transparent; transition:background-color 120ms ease; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child { position:absolute; opacity:0; width:1px; height:1px; overflow:hidden; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"] [data-testid="stMarkdownContainer"] { min-width:0; width:100%; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"] [data-testid="stMarkdownContainer"] p { color:#344155; font-size:13px; font-weight:550; line-height:1.5; white-space:normal; overflow-wrap:anywhere; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"] [data-testid="stCaptionContainer"] { margin-top:.2rem; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"] [data-testid="stCaptionContainer"] p { display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:2; overflow:hidden; color:var(--catalog-muted)!important; font-size:12px!important; font-weight:400; line-height:1.5!important; margin:0; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"]:hover { background:#f0f2f8; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) { background:#eeefff; border-color:#e4e3fc; box-shadow:inset 3px 0 0 var(--catalog-accent); }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) [data-testid="stMarkdownContainer"] p { color:#37308a; }
.st-key-catalog_component_list [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:focus-visible) { outline:2px solid var(--catalog-accent); outline-offset:2px; }
.catalog-list-summary { color:var(--catalog-muted); font-size:.735rem; line-height:1.5; margin:.2rem .75rem .4rem; overflow-wrap:anywhere; }

/* Purpose, code and secondary declarations have distinct but restrained levels. */
.catalog-entry-header { padding:0; margin:0; }
.st-key-catalog_detail h2.catalog-entry-title { color:var(--catalog-ink); font-size:22px!important; font-weight:700; line-height:1.35; letter-spacing:-.025em; margin:0!important; padding:0!important; overflow-wrap:anywhere; }
.catalog-entry-key { font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace; color:var(--catalog-muted); font-size:.73rem; line-height:1.5; margin-top:.3rem; overflow-wrap:anywhere; }
.catalog-entry-summary { color:#475569; font-size:.84rem; line-height:1.6; margin:.45rem 0 0; overflow-wrap:anywhere; }
.catalog-entry-meta { display:flex; flex-wrap:wrap; align-items:center; gap:.4rem .65rem; color:var(--catalog-muted); font-size:.71rem; line-height:1.5; margin:0 0 .3rem; }
.catalog-chip { display:inline-block; margin:.08rem .25rem .08rem 0; border-radius:4px; padding:.1rem .38rem; color:#5146a8; background:var(--catalog-accent-soft); font-size:.68rem; font-weight:500; line-height:1.5; overflow-wrap:anywhere; }
.catalog-section-title { color:#475569; font-size:.81rem; font-weight:650; line-height:1.5; margin-top:.85rem; margin-bottom:.3rem; }
.catalog-detail, .catalog-detail-panel { color:var(--catalog-ink); }
.st-key-catalog_detail [data-testid="stMarkdownContainer"] p, .st-key-catalog_detail [data-testid="stMarkdownContainer"] li { font-size:.875rem; line-height:1.65; }
.st-key-catalog_detail [data-testid="stMarkdownContainer"] h1 { font-size:1.35rem; line-height:1.4; padding:.2rem 0 .45rem; }
.st-key-catalog_detail [data-testid="stMarkdownContainer"] h2 { font-size:1.125rem; line-height:1.45; padding:.2rem 0 .4rem; }
.st-key-catalog_detail [data-testid="stMarkdownContainer"] h3 { font-size:1rem; line-height:1.5; padding:.15rem 0 .35rem; }
.st-key-catalog_detail [data-testid="stMarkdownContainer"] h4 { font-size:.875rem; line-height:1.5; padding:.1rem 0 .25rem; }
.st-key-catalog_detail [data-testid="stCaptionContainer"] p { font-size:.75rem!important; line-height:1.6!important; }
.st-key-catalog_detail [data-testid="stCode"] { border:1px solid #e8ebf2; border-radius:8px; background:var(--catalog-code); }
.st-key-catalog_detail [data-testid="stCode"] pre { padding:1rem; }
.st-key-catalog_detail [data-testid="stCode"] code { font-size:13px; line-height:1.6; }
.st-key-catalog_detail [data-testid="stExpander"] details { border:0; border-bottom:1px solid #edf0f5; border-radius:0; background:transparent; }
.st-key-catalog_detail [data-testid="stExpander"] summary { padding:.7rem .15rem; }
.st-key-catalog_detail [data-testid="stExpander"] summary p { font-size:.8rem; font-weight:550; color:#526078; }
.st-key-catalog_detail [data-testid="stExpander"] details > div { padding-left:.15rem; padding-right:.15rem; }
.catalog-sequence { padding-left:1.1rem; color:#475569; font-size:.83rem; line-height:1.65; }
.catalog-sequence li { margin-bottom:.3rem; }

/* Radio-backed detail tabs preserve the existing URL and keyboard state. */
.st-key-catalog_detail [data-testid="stRadio"] [role="radiogroup"] { display:flex; gap:1.25rem; border-bottom:1px solid var(--catalog-line); padding:0; margin-bottom:.35rem; }
.st-key-catalog_detail [data-testid="stRadio"] label[data-baseweb="radio"] { position:relative; border-radius:0; border-bottom:2px solid transparent; padding:.35rem .1rem .5rem; margin-bottom:-1px; min-height:34px; background:transparent; }
.st-key-catalog_detail [data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child { position:absolute; opacity:0; width:1px; height:1px; overflow:hidden; }
.st-key-catalog_detail [data-testid="stRadio"] label[data-baseweb="radio"] p { color:var(--catalog-muted); font-size:.8rem; font-weight:500; }
.st-key-catalog_detail [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) { border-bottom-color:var(--catalog-accent); }
.st-key-catalog_detail [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p { color:#4338ca; font-weight:650; }
.st-key-catalog_detail [data-testid="stRadio"] label[data-baseweb="radio"]:hover p { color:var(--catalog-ink); }
.st-key-catalog_detail [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:focus-visible) { outline:2px solid var(--catalog-accent); outline-offset:3px; border-radius:3px; }

.catalog-shell-block { margin:.1rem 0 .45rem; }
.catalog-shell-header { display:flex; align-items:center; justify-content:space-between; gap:.75rem; margin-bottom:.35rem; }
.catalog-shell-copy { min-width:0; }
.catalog-shell-label { font-size:.62rem; color:var(--catalog-muted); letter-spacing:.08em; font-weight:550; margin-bottom:.15rem; }
.catalog-shell-title { font-size:.88rem; line-height:1.4; color:var(--catalog-ink); font-weight:650; margin-bottom:.16rem; }
.catalog-shell-subtitle { font-size:.74rem; color:var(--catalog-muted); line-height:1.5; }
.catalog-shell-note { color:var(--catalog-muted); background:#f0f2f8; padding:.16rem .45rem; border-radius:5px; font-size:.7rem; white-space:nowrap; }
.catalog-empty, .catalog-empty-state { color:var(--catalog-muted); background:#fafbfe; border:1px dashed var(--catalog-line); border-radius:8px; padding:1.5rem 1.1rem; font-size:.83rem; line-height:1.65; }
.catalog-warning { background:#fbf8ee; border:1px solid #eae1c9; color:#735d2b; font-size:.8rem; line-height:1.6; border-radius:7px; padding:.7rem .8rem; margin-bottom:.65rem; }
.catalog-floating { border:1px solid var(--catalog-line); border-radius:7px; padding:.65rem .8rem; background:var(--catalog-soft); margin-top:.45rem; }
.catalog-floating-label { font-size:.65rem; font-weight:600; color:var(--catalog-muted); }
.catalog-floating-title { font-size:.84rem; font-weight:650; color:var(--catalog-ink); margin-top:.2rem; }
.catalog-floating-meta { font-size:.73rem; line-height:1.65; color:var(--catalog-muted); margin-top:.2rem; }

.catalog-relation-grid, .catalog-relation-chain-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.65rem; margin:.5rem 0 .9rem; }
.catalog-relation-card, .catalog-relation-chain-card { background:white; border:1px solid var(--catalog-line); padding:.8rem; border-radius:7px; }
.catalog-relation-family { font-size:.66rem; font-weight:600; color:var(--catalog-accent); }
.catalog-relation-title { font-size:.86rem; font-weight:650; color:var(--catalog-ink); margin-top:.25rem; }
.catalog-relation-meta, .catalog-relation-chain-meta { font-size:.74rem; color:var(--catalog-muted); line-height:1.55; margin-top:.25rem; }
.catalog-relation-preview { display:flex; flex-direction:column; gap:.3rem; margin-top:.6rem; }
.catalog-relation-preview-item, .catalog-relation-lane-item { color:#475569; background:var(--catalog-soft); font-size:.75rem; line-height:1.55; padding:.3rem .45rem; border-radius:4px; overflow-wrap:anywhere; }
.catalog-relation-preview-key, .catalog-relation-lane-key { display:block; font-size:.67rem; color:var(--catalog-muted); }
.catalog-relation-chain-key { background:var(--catalog-soft); padding:.4rem .5rem; border-radius:4px; color:var(--catalog-ink); font-size:.83rem; font-weight:650; margin-top:.25rem; overflow-wrap:anywhere; }
.catalog-relation-chain-lanes { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.5rem; margin-top:.65rem; }
.catalog-relation-lane { border:1px solid var(--catalog-line); border-radius:5px; padding:.45rem; }
.catalog-relation-lane-title { font-size:.7rem; font-weight:600; color:var(--catalog-muted); margin-bottom:.4rem; }
.catalog-relation-lane-empty { color:var(--catalog-muted); font-size:.72rem; }
.catalog-relation-lane-item { margin-bottom:.25rem; }

.catalog-fab-stack { display:flex; flex-direction:column; gap:.45rem; position:fixed; right:1rem; bottom:1rem; z-index:9998; }
.catalog-fab { width:34px; height:34px; display:flex; align-items:center; justify-content:center; border:1px solid var(--catalog-line); border-radius:7px; color:#64748b!important; background:white; font-size:1rem; text-decoration:none!important; position:relative; cursor:pointer; }
.catalog-fab:hover { background:var(--catalog-accent-soft); color:var(--catalog-accent)!important; }
.catalog-fab-disabled { opacity:.4; cursor:default; pointer-events:none; }
.catalog-fab[data-tooltip]::after { content:attr(data-tooltip); position:absolute; right:calc(100% + 9px); top:50%; transform:translateY(-50%); background:var(--catalog-ink); color:white; font-size:.7rem; white-space:nowrap; padding:.35rem .55rem; border-radius:5px; opacity:0; pointer-events:none; }
.catalog-fab[data-tooltip]:hover::after, .catalog-fab[data-tooltip]:focus-visible::after { opacity:1; }

@media (max-width:1100px) {
    .st-key-catalog_workspace [data-testid="stColumn"]:has(.st-key-catalog_results) { flex-basis:280px; width:280px; }
    .st-key-catalog_detail { padding:1.25rem; }
    .st-key-catalog_intents [data-testid="stButton"] button { padding:.15rem .25rem; }
    .st-key-catalog_intents [data-testid="stButton"] button p { font-size:.7rem; }
}
@media (max-width:950px) {
    .st-key-catalog_workspace [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-catalog_results) { flex-direction:column; }
    .st-key-catalog_workspace [data-testid="stColumn"]:has(.st-key-catalog_results),
    .st-key-catalog_workspace [data-testid="stColumn"]:has(.st-key-catalog_detail) { width:100%; flex:1 1 100%; min-width:0; max-width:none; }
    .st-key-catalog_results { border-right:0; border-bottom:1px solid var(--catalog-line); border-radius:11px 11px 0 0; }
    .st-key-catalog_component_list { max-height:260px!important; overflow-y:auto; }
    .st-key-catalog_results [data-testid="stLayoutWrapper"]:has(> .st-key-catalog_component_list) { height:260px!important; max-height:260px!important; flex:0 0 260px!important; }
    .st-key-catalog_detail { border-radius:0 0 11px 11px; }
    .st-key-catalog_search [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stTextInput"]) { flex-wrap:wrap; gap:.5rem; }
    .st-key-catalog_search [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stTextInput"]) > [data-testid="stColumn"] { flex:1 1 calc(50% - .25rem); width:auto; min-width:0; }
    .st-key-catalog_search [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stTextInput"]) > [data-testid="stColumn"]:first-child { flex:1 1 100%; width:100%; }
    .st-key-catalog_search [data-testid="stButton"] button p { white-space:nowrap; }
    .st-key-catalog_intents [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.45rem; }
    .st-key-catalog_intents [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex:1 1 calc(50% - .225rem); width:auto; min-width:0; }
}
@media (max-width:760px) {
    .catalog-heading { gap:.6rem; margin-bottom:1rem; }
    .catalog-mode-badge { font-size:.62rem; padding:.25rem .45rem; margin-top:.3rem; }
    .st-key-catalog_search [data-testid="stHorizontalBlock"], .st-key-catalog_intents [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.45rem; }
    .st-key-catalog_search [data-testid="stColumn"], .st-key-catalog_intents [data-testid="stColumn"] { min-width:0; }
    .st-key-catalog_intents [data-testid="stButton"] button { min-height:34px; }
    .st-key-catalog_detail { padding:1rem; }
    .st-key-catalog_detail h2.catalog-entry-title { font-size:20px!important; }
    .st-key-catalog_detail [data-testid="stRadio"] [role="radiogroup"] { gap:1rem; }
    .catalog-relation-chain-lanes { grid-template-columns:1fr; }
    .catalog-fab-stack { right:.6rem; bottom:.6rem; }
}
</style>
"""
