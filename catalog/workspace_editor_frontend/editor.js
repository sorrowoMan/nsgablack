/* MIT. Offline workspace editor; see THIRD_PARTY_LICENSES.txt for CodeMirror. */
import {basicSetup} from "codemirror";
import {EditorState, Compartment, Prec} from "@codemirror/state";
import {EditorView, keymap} from "@codemirror/view";
import {indentWithTab, undo, redo} from "@codemirror/commands";
import {openSearchPanel} from "@codemirror/search";
import {indentUnit, HighlightStyle, syntaxHighlighting} from "@codemirror/language";
import {tags} from "@lezer/highlight";
import {python} from "@codemirror/lang-python";
import {json} from "@codemirror/lang-json";
import {lintGutter, setDiagnostics} from "@codemirror/lint";

const shell = document.getElementById("editor-shell");
const status = document.getElementById("buffer-status");
const languageLabel = document.getElementById("language");
const positionLabel = document.getElementById("position");
const languageCompartment = new Compartment();
const editableCompartment = new Compartment();
const themeCompartment = new Compartment();
const systemAppearance = window.matchMedia("(prefers-color-scheme: dark)");
const encoder = new TextEncoder();
const MAX_SEQUENCE = Number.MAX_SAFE_INTEGER;
let view = null, identity = null, sequence = 0, acknowledged = 0;
let parentOrigin = null, pending = null, lastGoto = null;
let lastSentText = null, readOnly = false, maxBytes = 524288;
let language = null, lastHeight = null, lintSignature = null;
let appearance = "dark", effectiveAppearance = "dark";

function themeExtensions(dark) {
  const colors = dark ? {
    keyword: "#c5a4ec", name: "#dde3ed", function: "#a7c5ff", string: "#93cfb4",
    number: "#edbc8a", comment: "#8e99aa", operator: "#b8c3d5", type: "#81cbd5",
    invalid: "#f1a4ad"
  } : {
    keyword: "#7752a7", name: "#263449", function: "#315dac", string: "#347566",
    number: "#9a5b25", comment: "#718096", operator: "#526176", type: "#247d88",
    invalid: "#b73d49"
  };
  return [
    EditorView.theme({
      "&": {color: "var(--ed-text)", backgroundColor: "var(--ed-bg)"},
      ".cm-content": {caretColor: "var(--ed-accent)"},
      ".cm-cursor, .cm-dropCursor": {borderLeftColor: "var(--ed-accent)"},
      "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
        backgroundColor: "var(--ed-selection)"},
      ".cm-gutters": {backgroundColor: "var(--ed-gutter)", color: "var(--ed-muted)",
        borderRight: "1px solid var(--ed-line)"},
      ".cm-activeLine": {backgroundColor: "var(--ed-active)"},
      ".cm-activeLineGutter": {backgroundColor: "var(--ed-active)", color: "var(--ed-text)"},
      ".cm-panels": {backgroundColor: "var(--ed-toolbar)", color: "var(--ed-text)"},
      ".cm-panels.cm-panels-top": {borderBottom: "1px solid var(--ed-line)"},
      ".cm-panels.cm-panels-bottom": {borderTop: "1px solid var(--ed-line)"},
      ".cm-tooltip": {backgroundColor: "var(--ed-toolbar)", color: "var(--ed-text)",
        border: "1px solid var(--ed-line)"},
      ".cm-tooltip-autocomplete > ul > li[aria-selected]": {
        backgroundColor: "var(--ed-selected)", color: "var(--ed-text)"},
      ".cm-matchingBracket": {backgroundColor: "var(--ed-selected)", color: "var(--ed-text)"},
      ".cm-searchMatch": {backgroundColor: "var(--ed-search)"},
      ".cm-searchMatch-selected": {backgroundColor: "var(--ed-selection)"}
    }, {dark}),
    syntaxHighlighting(HighlightStyle.define([
      {tag: tags.keyword, color: colors.keyword},
      {tag: [tags.name, tags.deleted, tags.character, tags.macroName], color: colors.name},
      {tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: colors.function},
      {tag: [tags.string, tags.regexp], color: colors.string},
      {tag: [tags.number, tags.bool, tags.null, tags.atom], color: colors.number},
      {tag: [tags.comment, tags.meta], color: colors.comment},
      {tag: [tags.operator, tags.punctuation], color: colors.operator},
      {tag: [tags.typeName, tags.className, tags.namespace], color: colors.type},
      {tag: tags.invalid, color: colors.invalid}
    ]))
  ];
}

function applyAppearance(requested) {
  appearance = ["dark", "light", "system"].includes(requested) ? requested : "dark";
  const resolved = appearance === "system" ? (systemAppearance.matches ? "dark" : "light") : appearance;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  shell.dataset.appearance = appearance;
  if (resolved !== effectiveAppearance) {
    effectiveAppearance = resolved;
    // Reconfiguration changes presentation only; live text, selection, undo
    // history and event sequences remain in the existing EditorState.
    if (view) view.dispatch({effects: themeCompartment.reconfigure(themeExtensions(resolved === "dark"))});
  }
}

function post(type, data = {}) {
  // Ready contains no source text. All text messages require a parent render.
  if (!parentOrigin && type !== "streamlit:componentReady") return;
  window.parent.postMessage({isStreamlitMessage: true, type, ...data}, parentOrigin || "*");
}
function setStatus(text, error = false) {
  status.textContent = text;
  status.classList.toggle("error", error);
}
function updatePosition() {
  const head = view.state.selection.main.head, line = view.state.doc.lineAt(head);
  positionLabel.textContent = `行 ${line.number}，列 ${head - line.from + 1}`;
}
function cancelPending() {
  if (pending !== null) window.clearTimeout(pending);
  pending = null;
}
function flush(command = null) {
  cancelPending();
  if (!view || !identity || readOnly || !parentOrigin) return;
  const text = view.state.doc.toString();
  if (command === null && text === lastSentText) return;
  if (encoder.encode(text).length > maxBytes || text.includes("\0")) {
    setStatus("文件过大或含无效字符，尚未同步", true);
    return;
  }
  if (sequence >= MAX_SEQUENCE) {
    setStatus("请重新打开文件以继续编辑", true);
    return;
  }
  sequence += 1;
  lastSentText = text;
  post("streamlit:setComponentValue", {
    value: {identity, text, sequence, command}, dataType: "json"
  });
  setStatus(command === "save" ? "已请求保存" : "正在同步草稿…");
}
function scheduleChange() {
  if (readOnly) return;
  cancelPending();
  setStatus("正在编辑…");
  pending = window.setTimeout(() => {
    pending = null;
    if (view.composing) { scheduleChange(); return; }
    flush();
  }, 280);
}
function languageExtension(name) {
  if (name === "python") return python();
  if (name === "json") return json();
  return []; // Markdown/TOML are plain text; no extra language/runtime loader.
}
function makeView(text, languageName) {
  return new EditorView({parent: document.getElementById("editor"), state: EditorState.create({
    doc: text,
    extensions: [basicSetup, lintGutter(), languageCompartment.of(languageExtension(languageName)),
      themeCompartment.of(themeExtensions(effectiveAppearance === "dark")),
      editableCompartment.of([EditorState.readOnly.of(readOnly), EditorView.editable.of(!readOnly)]),
      EditorState.tabSize.of(4), indentUnit.of("    "),
      EditorView.contentAttributes.of({"aria-label": "代码编辑器", spellcheck: "false"}),
      Prec.highest(keymap.of([
        {key: "Mod-s", run: () => {flush("save"); return true;}},
        {key: "Mod-Shift-z", run: redo},
        indentWithTab
      ])),
      EditorView.updateListener.of(update => {
        if (update.docChanged) { lintSignature = null; scheduleChange(); }
        if (update.selectionSet || update.docChanged) updatePosition();
      }),
      EditorView.domEventHandlers({
        blur() { flush(); },
        compositionend() { scheduleChange(); }
      })]
  })});
}
function applyDiagnostics(args) {
  // A backend marker belongs to the exact source that was inspected, never a
  // newer unsent edit. Diagnostics are only text/ranges, never HTML/actions.
  const current = view.state.doc.toString();
  const items = current === args.value && Array.isArray(args.diagnostics) ? args.diagnostics : [];
  const signature = JSON.stringify(items);
  if (lintSignature === signature) return;
  lintSignature = signature;
  const markers = [];
  for (const item of items.slice(0, 200)) {
    if (!Number.isSafeInteger(item.line) || item.line < 1 || item.line > view.state.doc.lines ||
        !["error", "warning"].includes(item.severity) || typeof item.message !== "string") continue;
    const line = view.state.doc.line(item.line);
    const column = Number.isSafeInteger(item.column) && item.column > 0 ? item.column : 1;
    const from = Math.min(line.to, line.from + column - 1);
    markers.push({from, to: Math.min(line.to, from + 1), severity: item.severity,
      message: item.message.slice(0, 4000)});
  }
  view.dispatch(setDiagnostics(view.state, markers));
}
function render(args, disabled) {
  if (!args || typeof args.identity !== "string" || !args.identity ||
      typeof args.value !== "string" || !Number.isSafeInteger(args.sequence_base) ||
      args.sequence_base < 0 || args.sequence_base >= MAX_SEQUENCE) return;
  const requestedReadOnly = Boolean(args.read_only || disabled);
  const requestedLanguage = ["python", "json", "markdown", "toml", "text"].includes(args.language)
    ? args.language : "text";
  applyAppearance(args.theme);
  maxBytes = Number.isSafeInteger(args.max_text_bytes) && args.max_text_bytes > 0
    ? Math.min(args.max_text_bytes, 524288) : 524288;
  if (identity !== args.identity) {
    cancelPending();
    if (view) view.destroy();
    identity = args.identity;
    sequence = args.sequence_base;
    acknowledged = args.sequence_base;
    lastSentText = args.value;
    readOnly = requestedReadOnly;
    language = requestedLanguage;
    lastGoto = null;
    lintSignature = null;
    view = makeView(args.value, language);
    setStatus(readOnly ? "只读" : "草稿已同步到会话");
    updatePosition();
  } else {
    sequence = Math.max(sequence, args.sequence_base);
    acknowledged = Math.max(acknowledged, args.sequence_base);
    if (acknowledged >= sequence && args.value === view.state.doc.toString())
      setStatus(requestedReadOnly ? "只读" : "草稿已同步到会话");
    if (requestedReadOnly !== readOnly) {
      readOnly = requestedReadOnly;
      view.dispatch({effects: editableCompartment.reconfigure([
        EditorState.readOnly.of(readOnly), EditorView.editable.of(!readOnly)])});
    }
    if (requestedLanguage !== language) {
      language = requestedLanguage;
      view.dispatch({effects: languageCompartment.reconfigure(languageExtension(language))});
    }
    // Same identity deliberately never replaces a live buffer on rerender.
    // Source replacement/discard uses a new caller-controlled editor epoch.
  }
  languageLabel.textContent = requestedLanguage.toUpperCase();
  document.getElementById("save").disabled = readOnly;
  document.getElementById("undo").disabled = readOnly;
  document.getElementById("redo").disabled = readOnly;
  const height = Number.isSafeInteger(args.height) ? Math.max(200, Math.min(1200, args.height)) : 520;
  if (lastHeight !== height) {
    lastHeight = height;
    post("streamlit:setFrameHeight", {height});
  }
  applyDiagnostics(args);
  if (args.goto_line === null || args.goto_line === undefined) lastGoto = null;
  else if (Number.isSafeInteger(args.goto_line) && args.goto_line > 0 && args.goto_line !== lastGoto) {
    lastGoto = args.goto_line;
    const target = view.state.doc.line(Math.min(args.goto_line, view.state.doc.lines)).from;
    view.dispatch({selection: {anchor: target}, effects: EditorView.scrollIntoView(target, {y: "center"})});
    view.focus();
  }
}

document.getElementById("save").addEventListener("click", () => flush("save"));
document.getElementById("search").addEventListener("click", () => {if (view) {openSearchPanel(view); view.focus();}});
document.getElementById("undo").addEventListener("click", () => {if (view && !readOnly) {undo(view); view.focus();}});
document.getElementById("redo").addEventListener("click", () => {if (view && !readOnly) {redo(view); view.focus();}});
window.addEventListener("blur", () => flush());
window.addEventListener("pagehide", () => flush());
document.addEventListener("visibilitychange", () => {if (document.hidden) flush();});
systemAppearance.addEventListener("change", () => {if (appearance === "system") applyAppearance("system");});
window.addEventListener("message", event => {
  if (event.source !== window.parent || !event.data || event.data.type !== "streamlit:render") return;
  if (parentOrigin !== null && event.origin !== parentOrigin) return;
  parentOrigin = event.origin;
  render(event.data.args, event.data.disabled);
});
post("streamlit:componentReady", {apiVersion: 1});
