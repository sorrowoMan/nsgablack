"""Shared presentation for Catalog discovery and the experiment workbench.

Only page layouts belong in dashboard_style/lab_ui. Navigation, design tokens
and native control styling live here so workspace switches keep one identity.
"""

COLORS = {"ink": "#172033", "muted": "#64748b", "line": "#e2e6ef",
          "soft": "#f7f8fc", "accent": "#4f46e5", "accent_soft": "#eef0ff",
          "code": "#f5f7fb", "background": "#f5f6fa", "card": "#ffffff"}
# Canvas-based tables read Streamlit's native theme, not CSS. Keep startup
# options and CSS variables derived from the same palette.
STREAMLIT_THEME = {"base": "light", "primaryColor": COLORS["accent"],
                   "textColor": COLORS["ink"], "backgroundColor": COLORS["background"],
                   "secondaryBackgroundColor": COLORS["card"]}

WORKSPACE_BRAND = "<div class='workspace-brand'>N / NSGABLACK</div>"
WORKSPACE_FOOTER = ("<div class='workspace-footer'>FRAMEWORK WORKSPACE<br>"
                    "发现组件 · 设计实验 · 验证想法</div>")

WORKSPACE_CSS = """
<style>
:root {
  --catalog-ink:__ink__; --catalog-muted:__muted__; --catalog-line:__line__;
  --catalog-soft:__soft__; --catalog-accent:__accent__;
  --catalog-accent-soft:__accent_soft__; --catalog-code:__code__;
  --workspace-bg:__background__; --workspace-card:__card__;
  --workspace-nav:#171e30; --workspace-nav-text:#b9c2d5;
  --workspace-radius:16px; --workspace-shadow:0 3px 12px #17203303;
}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background:var(--workspace-bg); color:var(--catalog-ink);
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
}
.stApp [data-testid="stHeader"] {background:var(--workspace-bg);height:36px;}
.stApp .block-container {padding:2.8rem 2rem 3rem;max-width:1560px;}
[data-testid="stVerticalBlock"] {gap:.8rem;}
[data-testid="stMarkdownContainer"] p {line-height:1.75;}
.stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stCaptionContainer"] * {color:#52627b!important;font-size:.81rem!important;line-height:1.75;opacity:1;}
.stApp [data-testid="stWidgetLabel"] p {color:#3e4b63!important;font-size:.82rem;font-weight:550;}
.stApp h1.heading-title,.lab-heading h1 {color:var(--catalog-ink);font-size:2rem!important;font-weight:720;line-height:1.3;letter-spacing:-.045em;padding:0;margin:0 0 .35rem;}
.heading-kicker,.lab-kicker {color:#696d85;font-size:.69rem;font-weight:650;letter-spacing:.16em;margin-bottom:.5rem;}
.stApp .heading-subtitle,.lab-subtitle {color:var(--catalog-muted);font-size:.9rem;line-height:1.8;max-width:650px;margin:0;}
.workspace-brand {color:#f5f6ff;font-size:.74rem;letter-spacing:.06em;white-space:nowrap;font-weight:700;padding:.35rem .5rem 2.7rem;}
.workspace-footer {color:#9aa6bf;font-size:.72rem;line-height:1.9;border-top:1px solid #30394e;margin:2.2rem .5rem 0;padding-top:1rem;}
[data-testid="stSidebar"] {width:216px;min-width:216px;max-width:216px;border:0;background:var(--workspace-nav);}
[data-testid="stSidebarContent"] {background:var(--workspace-nav);}
[data-testid="stSidebarHeader"] {height:36px;min-height:36px;padding:.2rem .65rem;}
[data-testid="stSidebarUserContent"] {padding:1.4rem 1rem;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.55rem;}
.stApp [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color:#929db5!important;font-size:.7rem!important;letter-spacing:.06em;margin:0 0 .5rem;}
.stApp [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {color:#a8b3c9!important;font-size:.74rem!important;}
.stApp [data-testid="stSidebar"] [data-testid="stProgress"] p {color:#b9c2d5!important;font-size:.74rem!important;}
[data-testid="stSidebar"] [role="radiogroup"]:is([aria-label="工作区"],[aria-label="分类"]) label {border-radius:8px;margin:.15rem 0;padding:.6rem .75rem;min-height:42px;width:100%;align-items:center;}
[data-testid="stSidebar"] [role="radiogroup"] {width:100%;gap:2px;}
[data-testid="stSidebar"] [role="radiogroup"]:is([aria-label="工作区"],[aria-label="分类"]) label p {color:var(--workspace-nav-text)!important;font-size:.85rem;}
[data-testid="stSidebar"] [role="radiogroup"]:is([aria-label="工作区"],[aria-label="分类"]) label > div:first-child {position:absolute;opacity:0;width:1px;height:1px;overflow:hidden;}
[data-testid="stSidebar"] [role="radiogroup"]:is([aria-label="工作区"],[aria-label="分类"]) label:has(input:checked) {background:#343052;box-shadow:inset 3px 0 #a79bff;}
[data-testid="stSidebar"] [role="radiogroup"]:is([aria-label="工作区"],[aria-label="分类"]) label:has(input:checked) p {color:#efecff!important;font-weight:650;}
[data-testid="stSidebar"] [role="radiogroup"]:is([aria-label="工作区"],[aria-label="分类"]) label:hover {background:#262e44;}
[data-testid="stSidebar"] [role="radiogroup"]:is([aria-label="工作区"],[aria-label="分类"]) label:has(input:focus-visible) {outline:2px solid #a79bff;outline-offset:2px;}
[data-testid="stSidebar"] [role="radiogroup"][aria-label="分类"] label {min-height:34px;padding:.4rem .7rem;}
[data-testid="stSidebar"] [role="radiogroup"][aria-label="分类"] label p {font-size:.8rem;white-space:nowrap;}
[data-testid="stSidebarCollapseButton"] button {color:var(--workspace-nav-text);}
.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"],
.stApp [data-testid="stTextInput"] input,.stApp [data-testid="stTextArea"] textarea,
.stApp [data-baseweb="select"] div {background:#fff;color:var(--catalog-ink);caret-color:var(--catalog-ink);}
.stApp input::placeholder,.stApp textarea::placeholder {color:#7b8497!important;opacity:1;}
.stApp [data-testid="stTextInput"] input,.stApp [data-baseweb="select"] > div {border-color:#dde2ec;border-radius:8px;min-height:40px;font-size:.84rem;}
.stApp [data-testid="stTextInput"] [data-baseweb="input"] {border:1px solid #dde2ec;border-radius:8px;}
.stApp [data-testid="stTextInput"] [data-baseweb="input"]:focus-within {border-color:#8277e8;box-shadow:0 0 0 2px #4f46e510;}
.stApp [data-testid="stTextArea"] [data-baseweb="textarea"] {border:1px solid #dde2ec;border-radius:10px;}
.stApp [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {border-color:#8277e8;box-shadow:0 0 0 2px #4f46e510;}
.stApp [data-testid="stButton"] button,.stApp [data-testid="stDownloadButton"] button,
.stApp [data-testid="stLinkButton"] a,.stApp [data-testid="stPopover"] button {border-radius:8px;border:1px solid #dde2ec;min-height:38px;background:#fff;color:#34445e;transition:background 120ms,border-color 120ms;}
.stApp [data-testid="stButton"] button p,.stApp [data-testid="stDownloadButton"] button p {color:inherit!important;}
.stApp [data-testid="stButton"] button:hover {border-color:#b7b1ed;background:#f3f2ff;color:#4338ca;}
.stApp [data-testid="stButton"] button[kind="primary"] {background:var(--catalog-accent)!important;border-color:var(--catalog-accent)!important;color:#fff!important;}
.stApp [data-testid="stButton"] button[kind="primary"]:hover {background:#4338ca!important;}
.stApp [data-testid="stButton"] button[kind="primary"]:disabled {background:#e8e9f7!important;border-color:#e8e9f7!important;color:#7a7e9f!important;opacity:1;}
.stApp button:focus-visible,.stApp a:focus-visible {outline:2px solid var(--catalog-accent);outline-offset:3px;}
.stApp [data-testid="stNumberInput"] button {background:#f5f6fb!important;color:#475569!important;min-height:0;}
.stApp [data-testid="stNumberInput"] button svg,.stApp [data-baseweb="select"] svg {color:#64748b!important;fill:currentColor!important;}
.stApp [data-testid="stExpander"] {border:1px solid var(--catalog-line);border-radius:9px;background:#fff;}
.stApp [data-testid="stExpander"] summary {background:#fff;border-radius:9px;min-height:44px;}
.stApp [data-testid="stExpander"] summary p {font-size:.82rem;color:#475569;}
.stApp [data-testid="stMetricLabel"] *,.stApp [data-testid="stMetricValue"] * {color:var(--catalog-ink)!important;}
.stApp [data-testid="stCheckbox"] label p {color:#475569!important;}
.stApp [data-testid="stFileUploader"] section {background:var(--catalog-soft);color:#475569;}
.stApp [data-testid="stCode"] pre {background:var(--catalog-code);color:#334155;border-radius:8px;}
.stApp code {color:#5146a8;background:var(--catalog-code);border-radius:4px;}
.stApp [data-testid="stCode"] code {background:transparent;color:inherit;}
.stApp [data-testid="stDataFrame"] {border:1px solid var(--catalog-line);border-radius:9px;overflow:hidden;}
/* Sidebar controls deliberately use the same dark surface in both workspaces. */
.stApp [data-testid="stSidebar"] [data-baseweb="select"] div,
.stApp [data-testid="stSidebar"] [data-baseweb="input"],
.stApp [data-testid="stSidebar"] [data-baseweb="base-input"],
.stApp [data-testid="stSidebar"] input {background:#252e44!important;color:#e0e5f0!important;border-color:#3c465e;}
.stApp [data-testid="stSidebar"] [data-baseweb="select"] svg {color:#a8b3c9!important;}
.stApp [data-testid="stSidebar"] [data-baseweb="select"] > div {font-size:.76rem;}
.stApp [data-testid="stSidebar"] [data-testid="stExpander"],
.stApp [data-testid="stSidebar"] [data-testid="stExpander"] summary {background:transparent;border-color:#3c465e;}
.stApp [data-testid="stSidebar"] [data-testid="stExpander"] summary p,
.stApp [data-testid="stSidebar"] [data-testid="stCheckbox"] label p {color:#b9c2d5!important;}
[data-testid="stPopoverBody"],[data-baseweb="popover"] {background:#fff!important;color:var(--catalog-ink)!important;}
[data-testid="stPopoverBody"] {max-height:80vh;overflow:auto;}
[data-testid="stPopoverBody"] div {background-color:transparent!important;}
[data-testid="stPopoverBody"] p,[data-testid="stPopoverBody"] span,
[data-testid="stPopoverBody"] label {color:#475569!important;}
[data-testid="stPopoverBody"] strong {color:var(--catalog-ink)!important;}
[data-testid="stPopoverBody"] textarea {background:#fff!important;color:var(--catalog-ink)!important;caret-color:var(--catalog-ink);border:1px solid #dde2ec!important;border-radius:8px;}
[data-testid="stPopoverBody"] textarea::placeholder {color:#7b8497!important;}
[data-testid="stPopoverBody"] [data-baseweb="textarea"] {border:1px solid #dde2ec!important;border-radius:8px;}
[data-testid="stPopoverBody"] [data-baseweb="textarea"]:focus-within {border-color:#8277e8!important;box-shadow:0 0 0 2px #4f46e510;}
[data-testid="stPopoverBody"] button {background:#f7f8fc!important;color:#334155!important;border:1px solid #dde2ec!important;}
[data-testid="stPopoverBody"] pre {background:var(--catalog-code)!important;color:#334155!important;}
[data-baseweb="popover"] [role="option"] {color:#334155;background:#fff;}
[data-baseweb="popover"] [role="option"][aria-selected="true"] {color:#4338ca;background:var(--catalog-accent-soft);}
@media(max-width:1050px){.stApp .block-container{padding-left:1.25rem;padding-right:1.25rem}.stApp h1.heading-title,.lab-heading h1{font-size:1.75rem!important}}
@media(max-width:760px){.stApp .block-container{padding:2.5rem 1rem}.stApp h1.heading-title,.lab-heading h1{font-size:1.6rem!important}}
@media(prefers-reduced-motion:reduce){.stApp *{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
</style>
"""
for _name, _value in COLORS.items():
    WORKSPACE_CSS = WORKSPACE_CSS.replace("__" + _name + "__", _value)
