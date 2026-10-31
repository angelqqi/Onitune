/* Interfaz de Onitune.
 *
 * Python manda los datos con onitune.receive([[evento, datos], ...]) (ver ui/app.py)
 * y la página llama a Python con api.función(...) (ver ui/api.py).
 * Cada pestaña se arma una sola vez; después solo se actualiza lo que cambió.
 */
"use strict";

// ================================================================== utilidades

const $ = (sel, root = document) => root.querySelector(sel);
let api = null; // window.pywebview.api cuando esté listo

/** Crea un elemento: h("div.card.flush", {onclick: ...}, hijo1, "texto", ...) */
function h(spec, props, ...children) {
  const [tag, ...classes] = spec.split(".");
  const el = document.createElement(tag || "div");
  if (classes.length) el.className = classes.join(" ");
  if (props && (typeof props !== "object" || props instanceof Node || Array.isArray(props))) {
    children.unshift(props);
    props = null;
  }
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "className") { if (v) el.classList.add(...v.split(" ")); } // se suma a las clases de `spec`
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "text") el.textContent = v;
    else if (k === "style") Object.assign(el.style, v);
    else if (k === "tip") el.dataset.tip = v;
    else if (k in el && k !== "list") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

/** Icono de Material: relleno (por defecto) o de contorno (outlined=true). */
function icon(name, outlined = false) {
  return h(outlined ? "span.io" : "span.i", { text: name, "aria-hidden": "true" });
}

// ------------------------------------------------------------------ idiomas

let TEXTS = {}; // textos del idioma elegido (llegan de Python en init; ver core/i18n.py)

/** Texto traducido: t("audio.results", {text: "abc"}). Con {n} elige el plural ({"one": ..., "other": ...}). */
function t(key, vars = {}) {
  let text = TEXTS[key] ?? key;
  if (typeof text === "object") text = (vars.n === 1 ? text.one : text.other) ?? text.other ?? key;
  return text.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
}

function normalize(text) {
  // Minúsculas y sin tildes, para que "cancion" encuentre "Canción"
  return (text || "").normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase();
}

const isUrl = (text) => /^https?:\/\//i.test((text || "").trim());

function niceDate(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const day = new Date(d); day.setHours(0, 0, 0, 0);
  const hour = d.toTimeString().slice(0, 5);
  const diff = Math.round((today - day) / 86400000);
  if (diff === 0) return t("common.today_at", { time: hour });
  if (diff === 1) return t("common.yesterday_at", { time: hour });
  // "31 oct" / "Oct 31": el navegador pone el mes abreviado en el idioma elegido
  const opts = { day: "numeric", month: "short" };
  if (d.getFullYear() !== today.getFullYear()) opts.year = "numeric";
  try { return d.toLocaleDateString(S.lang, opts); } catch { return d.toLocaleDateString(); }
}

function thumbUrl(videoId) { return videoId ? `https://i.ytimg.com/vi/${videoId}/mqdefault.jpg` : ""; }

// ================================================================== piezas de la interfaz

function button(kind, label, iconName, onclick, opts = {}) {
  const b = h(`button.btn.btn-${kind}${opts.big ? ".big" : ""}`, { onclick, tip: opts.tip, type: "button" });
  if (iconName) b.append(icon(iconName, opts.outlined));
  b.append(h("span", { text: label }));
  return b;
}
function setButton(b, label, iconName, outlined = false) {
  b.replaceChildren(...(iconName ? [icon(iconName, outlined)] : []), h("span", { text: label }));
}

function iconButton(name, tip, onclick, outlined = false) {
  return h("button.icon-btn", { tip, onclick, type: "button", "aria-label": tip }, icon(name, outlined));
}

/** Campo de texto con icono, botón para borrar y Enter. */
function textField({ iconName, placeholder, onEnter, onInput }) {
  const input = h("input", { type: "text", placeholder, spellcheck: false });
  const wrap = h("label.field", icon(iconName), input);
  const clear = iconButton("close", t("common.clear"), () => { input.value = ""; sync(); input.focus(); });
  clear.classList.add("clear");
  wrap.append(clear);
  function sync() { wrap.classList.toggle("has-text", !!input.value); onInput && onInput(input.value); }
  input.addEventListener("input", sync);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && onEnter) onEnter(); });
  wrap.input = input;
  wrap.set = (v) => { input.value = v; sync(); };
  return wrap;
}

/** Lista desplegable con etiqueta sobre el borde. options = [[valor, texto], ...] */
function selectBox({ label, options, value, width, onchange }) {
  const sel = h("select", { onchange: () => onchange && onchange(sel.value) },
    options.map(([v, label]) => h("option", { value: v, text: label })));
  sel.value = value;
  const wrap = h("div.select", { style: { width: width ? width + "px" : "" } }, sel);
  if (label) wrap.append(h("span.float", { text: label }));
  wrap.select = sel;
  return wrap;
}

/** Botón segmentado (MP3 | M4A | ...). */
function segmented(options, value, onchange) {
  const wrap = h("div.segmented");
  const buttons = options.map(([v, label]) => h("button", {
    type: "button", text: label, className: v === value ? "on" : "",
    onclick: () => { wrap.set(v); onchange && onchange(v); },
  }));
  wrap.append(...buttons);
  wrap.set = (v) => { wrap.value = v; options.forEach(([ov], i) => buttons[i].classList.toggle("on", ov === v)); };
  wrap.value = value;
  return wrap;
}

function switchBox(label, checked, onchange) {
  const input = h("input", { type: "checkbox", checked, onchange: () => onchange && onchange(input.checked) });
  const wrap = h("label.switch", input, h("span.track"), h("span", { text: label }));
  wrap.input = input;
  wrap.setDisabled = (d) => { input.disabled = d; wrap.classList.toggle("disabled", d); };
  return wrap;
}

function checkBox(label, checked) {
  const input = h("input", { type: "checkbox", checked });
  const wrap = h("label.check", input, h("span", { text: label }));
  wrap.input = input;
  return wrap;
}

let radioCount = 0;
/** Grupo de opciones. options = [[valor, texto, elementoExtra?], ...] */
function radioGroup(options, value, onchange, rowGap = 4) {
  const name = "r" + ++radioCount;
  const wrap = h("div.col", { style: { gap: rowGap + "px" } });
  for (const [v, t, extra] of options) {
    const input = h("input", { type: "radio", name, value: v, checked: v === value, onchange: () => onchange(v) });
    wrap.append(h("div.row", h("label.radio", input, h("span", { text: t })), extra || null));
  }
  return wrap;
}

function header(title, sub) {
  const subEl = h("div.sub", { text: sub || "" });
  const el = h("div.header", h("div.grow", h("h1", { text: title }), subEl));
  el.sub = subEl;
  return el;
}

const sectionLabel = (text) => h("div.section-label", { text });
const card = (...children) => h("div.card", ...children);
const loadingRow = (text) => h("div.loading", h("div.spinner"), h("span", { text }));
const emptyState = (text) => h("div.empty", { text });

/** Miniatura de YouTube; si no carga (sin internet) queda el icono de reserva. */
function thumb(src, w, hgt, duration, fallback = "play_arrow", outlined = false) {
  const el = h("div.thumb", { style: { width: w + "px", height: hgt + "px" } }, icon(fallback, outlined));
  if (src) {
    const img = h("img", { src, alt: "", loading: "lazy", draggable: false });
    img.onload = () => img.classList.add("loaded");
    img.onerror = () => img.remove();
    el.append(img);
  }
  if (duration) el.append(h("span.dur", { text: duration }));
  return el;
}

/** Miniatura chica de una descarga, con el icono de audio o video en la esquina. */
function kindThumb(item, w, hgt) {
  const audio = item.kind === "audio";
  const el = thumb(thumbUrl(item.vid), w, hgt, "", audio ? "music_note" : "movie", !audio);
  el.classList.add("kind-icon");
  el.style.width = w + "px";
  if (item.vid) el.append(h("span.i.mini", { text: audio ? "music_note" : "movie" }));
  return el;
}

// ------------------------------------------------------------------ mensajes cortos

function toast(message) {
  const el = h("div.toast", { text: message });
  $("#toasts").append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 250); }, 2500);
}

// ------------------------------------------------------------------ diálogos

function openDialog({ title, subtitle, body = [], actions = [], wide = false }) {
  const head = h("div", h("h2", { text: title }), subtitle ? h("div.small.muted", { text: subtitle }) : null);
  const dlg = h(`div.dialog${wide ? ".wide" : ""}`, { role: "dialog" }, head, h("div.body", body), h("div.actions", actions));
  const scrim = h("div.scrim", dlg);
  scrim.addEventListener("mousedown", (e) => { if (e.target === scrim) close(); });
  function close() { scrim.remove(); document.removeEventListener("keydown", onKey); }
  function onKey(e) { if (e.key === "Escape") close(); }
  document.addEventListener("keydown", onKey);
  $("#dialogs").append(scrim);
  return close;
}

// ------------------------------------------------------------------ ayudas al pasar el mouse

(function tooltips() {
  const tip = $("#tip");
  let current = null;
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el === current) return;
    current = el;
    if (!el || !el.dataset.tip) { tip.classList.remove("on"); return; }
    tip.textContent = el.dataset.tip;
    const r = el.getBoundingClientRect();
    const tw = tip.offsetWidth;
    let left = r.left + r.width / 2 - tw / 2;
    left = Math.max(6, Math.min(left, innerWidth - tw - 6));
    let top = r.bottom + 6;
    if (top + 30 > innerHeight) top = r.top - 30;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
    tip.classList.add("on");
  });
  document.addEventListener("mousedown", () => tip.classList.remove("on"));
})();

// ================================================================== estado y temas

const S = {
  app: {}, settings: {}, themes: [], theme: "dracula", lang: "es", languages: [], systemLang: "es",
  items: new Map(), order: [], history: [], counts: { pending: 0, running: 0 },
  view: "audio",
};

async function setSetting(name, value) {
  S.settings[name] = value;
  await api.set_setting(name, value);
}

const THEME_VARS = ["bg", "rail", "card", "high", "border", "fg", "muted", "primary", "secondary", "ok", "warn", "info", "error"];
function applyTheme(id, animate = false) {
  const p = S.themes.find((x) => x.id === id) || S.themes[0];
  if (!p) return;
  S.theme = p.id;
  const root = document.documentElement.style;
  for (const k of THEME_VARS) root.setProperty("--" + k, p[k]);
  root.setProperty("--on-primary", p.on_primary);
  root.setProperty("color-scheme", p.dark ? "dark" : "light");
  if (animate) {
    document.body.classList.add("theme-anim");
    setTimeout(() => document.body.classList.remove("theme-anim"), 300);
  }
}

// ================================================================== menú lateral

// [vista, icono]; el nombre es "nav.<vista>"
const NAV = [
  ["audio", "music_note"],
  ["video", "movie"],
  ["queue", "download"],
  ["history", "history"],
  ["settings", "tune"],
];
const navButtons = {};

function buildNav() {
  const box = $("#destinations");
  for (const [id, ic] of NAV) {
    const ind = h("span.ind", icon(ic, true));
    const b = h("button.dest", { type: "button", onclick: () => go(id) }, ind, h("span", { text: t("nav." + id) }));
    b.ind = ind; b.iconName = ic;
    navButtons[id] = b;
    box.append(b);
  }
  $("#logo").src = S.app.icon;
}

function go(view) {
  S.view = view;
  for (const [id, b] of Object.entries(navButtons)) {
    const on = id === view;
    b.classList.toggle("on", on);
    b.ind.firstChild.replaceWith(icon(b.iconName, !on)); // relleno si está elegido, contorno si no
  }
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("on", v.id === "view-" + view));
  $("#scroll").scrollTop = 0;
  if (view === "settings") Settings.loadVersions();
  updateBadge();
}

function updateBadge() {
  const ind = navButtons.queue.ind;
  ind.querySelector(".badge")?.remove();
  if (S.counts.pending) ind.append(h("span.badge", { text: S.counts.pending }));
  const running = S.counts.running;
  const txt = $("#txt-queue");
  txt.textContent = running ? t("rail.running", { n: running }) : t("rail.idle");
  txt.className = running ? "" : "muted";
}

function showYtdlpStatus(status) {
  $("#dot-ytdlp").className = "dot " + (status.ok ? "ok" : "warn");
  $("#txt-ytdlp").textContent = status.ok ? t("rail.ytdlp_ok") : t("rail.ytdlp_old");
  if (status.message) Settings.showUpdateResult(status.ok, status.message);
}

// ================================================================== avisos de arriba

const Banners = {
  clipUrl: "",
  update: null,
  clip: null,

  showUpdate(info) {
    this.update?.remove();
    this.update = h("div.banner",
      icon("new_releases", true),
      h("div.text", h("div.t", { text: t("banner.update", { app: S.app.name, version: info.version }) }),
        h("div.small.muted", { text: t("banner.installed", { version: S.app.version }) })),
      button("text", t("banner.not_now"), null, () => { this.update.remove(); this.update = null; }),
      button("filled", t("common.download"), "open_in_new", () => api.open_url(info.url)));
    $("#banners").prepend(this.update);
  },

  showClip({ url, playlist }) {
    this.clip?.remove();
    this.clipUrl = url;
    this.clip = h("div.banner",
      icon("content_paste"),
      h("div.text", h("div.t", { text: t(playlist ? "banner.clip_playlist" : "banner.clip_video") }),
        h("div.small.muted.ellipsis", { text: url })),
      button("text", t("banner.ignore"), null, () => this.dismissClip()),
      button("outlined", t("nav.video"), "movie", () => this.useClip("video"), { outlined: true }),
      button("filled", t("nav.audio"), "music_note", () => this.useClip("audio")));
    $("#banners").append(this.clip);
  },

  dismissClip() {
    api.clip_ignore(this.clipUrl);
    this.clip?.remove();
    this.clip = null;
  },

  useClip(where) {
    const url = this.clipUrl;
    this.dismissClip();
    go(where);
    (where === "audio" ? Audio : Video).useUrl(url);
  },
};

// ================================================================== pestaña Audio

const AUDIO_FORMATS = ["mp3", "m4a", "opus", "flac", "wav"]; // su descripción es "format.<nombre>"

/** Ventana para elegir qué videos de una playlist agregar. */
function playlistDialog(data, kind, sourceUrl) {
  const info = data.info;
  // Si el enlace venía de un video concreto de la playlist, se marca solo ese
  const m = /[?&]v=([^&]+)/.exec(sourceUrl);
  const only = m && info.entries.some((e) => e.id === m[1]) ? m[1] : null;

  const checks = info.entries.map((e, n) => {
    const input = h("input", { type: "checkbox", checked: only ? e.id === only : true, onchange: refresh });
    return { e, input, row: h("label.pl-row.check", input, h("span.n", { text: n + 1 }),
      h("span.grow.ellipsis", { text: e.title }), h("span.d", { text: e.duration })) };
  });
  const addBtn = button("filled", "", null, add);
  const setAll = (v) => { checks.forEach((c) => (c.input.checked = v)); refresh(); };

  let res, container;
  const body = [
    h("div.row", { style: { gap: "4px" } }, button("text", t("playlist.select_all"), null, () => setAll(true)), button("text", t("playlist.select_none"), null, () => setAll(false))),
    h("div.pl-list", checks.map((c) => c.row)),
  ];
  if (kind === "video") {
    res = selectBox({ label: t("playlist.max_quality"), width: 220, value: "0", options: genericRes() });
    container = segmented([["mp4", "MP4"], ["mkv", "MKV"]], S.settings.video_container);
    body.push(h("div.row", { style: { gap: "16px" } }, res, container));
  }
  body.push(h("div.small.muted", { text: data.folder_note }));

  const close = openDialog({
    title: info.title, subtitle: t("playlist.subtitle", { n: info.entries.length }), wide: true, body,
    actions: [button("text", t("common.cancel"), null, () => close()), addBtn],
  });

  function selected() { return checks.filter((c) => c.input.checked).map((c) => ({ url: c.e.url, title: c.e.title })); }
  function refresh() {
    const n = selected().length;
    setButton(addBtn, t("playlist.download", { n }));
    addBtn.disabled = n === 0;
  }
  async function add() {
    const items = selected();
    const opts = kind === "video"
      ? { res: Number(res.select.value) || null, container: container.value, subs: false, music: data.music }
      : { music: data.music };
    close();
    const n = await api.add(kind, items, opts, info.title);
    toast(t("playlist.added", { n }));
  }
  refresh();
}

const Audio = {
  build() {
    const s = S.settings;
    this.query = textField({
      iconName: "search", placeholder: t("audio.placeholder"),
      onEnter: () => this.go(), onInput: () => this.updateButton(),
    });
    this.goBtn = button("filled", t("common.search"), "search", () => this.go(), { big: true });
    const paste = button("outlined", t("common.paste"), "content_paste", async () => {
      const text = await api.get_clipboard();
      if (text) { this.query.set(text); this.query.input.focus(); }
    }, { big: true });

    // Opciones
    this.formatDesc = h("div.small.muted", { text: t("format." + s.audio_format) });
    const format = segmented(AUDIO_FORMATS.map((k) => [k, k.toUpperCase()]), s.audio_format, (v) => {
      setSetting("audio_format", v);
      this.formatDesc.textContent = t("format." + v);
      this.applyRules();
    });
    this.quality = selectBox({
      label: t("common.quality"), width: 220, value: s.audio_quality,
      options: [["best", t("common.best_available")], ["320", "320 kbps"], ["256", "256 kbps"], ["192", "192 kbps"], ["128", "128 kbps"]],
      onchange: (v) => setSetting("audio_quality", v),
    });
    this.qualityNote = h("div.small.muted", { text: t("audio.lossless_note"), hidden: true });
    this.cover = switchBox(t("audio.cover"), s.audio_cover, (v) => setSetting("audio_cover", v));
    const meta = switchBox(t("audio.metadata"), s.audio_metadata, (v) => setSetting("audio_metadata", v));

    const options = card(h("div.col", { style: { gap: "14px" } },
      h("div.options-grid",
        h("div.col", sectionLabel(t("common.format")), format, this.formatDesc),
        h("div.col", sectionLabel(t("common.quality")), this.quality, this.qualityNote)),
      h("hr.divider"),
      h("div.row.wrap", { style: { gap: "8px 32px" } }, this.cover, meta)));

    this.status = h("div", { hidden: true });
    this.error = h("div.error-msg", { hidden: true });
    this.resultsTitle = h("div.results-title");
    this.resultsList = h("div.card.flush");
    this.results = h("div.col", { hidden: true, style: { gap: "12px" } }, this.resultsTitle, this.resultsList);

    $("#view-audio").append(
      header(t("audio.title"), t("audio.subtitle")),
      h("div.search-row", this.query, paste, this.goBtn),
      options, this.status, this.error, this.results);
    this.applyRules();
  },

  applyRules() {
    const f = S.settings.audio_format;
    const lossless = f === "flac" || f === "wav";
    this.quality.select.disabled = lossless;
    this.qualityNote.hidden = !lossless;
    this.cover.setDisabled(f === "wav"); // WAV no admite portada
  },

  updateButton() {
    if (isUrl(this.query.input.value)) setButton(this.goBtn, t("common.download"), "download");
    else setButton(this.goBtn, t("common.search"), "search");
  },

  busy(text) {
    this.status.hidden = !text;
    this.status.replaceChildren(text ? loadingRow(text) : "");
    this.goBtn.disabled = !!text;
  },

  showError(msg) { this.error.textContent = msg || ""; this.error.hidden = !msg; },

  useUrl(url) { this.query.set(url); this.updateButton(); this.go(); },

  async go() {
    const text = this.query.input.value.trim();
    if (!text || this.goBtn.disabled) return;
    this.showError("");
    if (isUrl(text)) {
      this.busy(t("audio.analyzing"));
      const r = await api.analyze(text, "audio");
      this.busy(null);
      if (r.error) return this.showError(r.error);
      if (r.type === "playlist") return playlistDialog(r, "audio", text);
      await api.add("audio", [{ url: text, title: r.info.title }], { music: r.info.music });
      this.query.set("");
      this.updateButton();
      toast(t("common.added"));
    } else {
      this.results.hidden = true;
      this.busy(t(S.settings.music_search ? "audio.searching_music" : "audio.searching", { text }));
      const r = await api.search(text);
      this.busy(null);
      if (r.error) return this.showError(r.error);
      this.resultsTitle.textContent = t("audio.results", { text });
      this.resultsList.replaceChildren(...(r.results.length ? r.results.map((x) => this.resultRow(x)) : [emptyState(t("audio.no_results"))]));
      this.results.hidden = false;
    }
  },

  resultRow(r) {
    let action;
    if (r.live) {
      action = h("span.live", { text: t("audio.live"), tip: t("audio.live_tip") });
    } else {
      action = button("outlined", t("common.download"), "download", async () => {
        action.replaceWith(h("span.added", icon("check"), t("audio.in_queue")));
        await api.add("audio", [{ url: r.url, title: r.title }], { music: r.music });
        toast(t("common.added"));
      });
    }
    return h("div.result",
      thumb(r.thumbnail, 104, 58, r.live ? t("audio.live_badge") : r.duration),
      h("div.grow", h("div.bold.clamp2", { text: r.title }), h("div.small.muted", { text: r.channel })),
      action);
  },
};

// ================================================================== pestaña Video

// Para playlists no se analiza cada video: se ofrecen calidades típicas
const genericRes = () => [["0", t("common.best_available")], ["2160", "2160p 4K"], ["1440", "1440p"], ["1080", "1080p"], ["720", "720p"], ["480", "480p"], ["360", "360p"]];

const Video = {
  info: null,
  res: 0,

  build() {
    this.url = textField({ iconName: "link", placeholder: "https://www.youtube.com/watch?v=…", onEnter: () => this.analyze() });
    this.analyzeBtn = button("filled", t("video.analyze"), "search", () => this.analyze(), { big: true });
    const paste = button("outlined", t("common.paste"), "content_paste", async () => {
      const text = await api.get_clipboard();
      if (text) this.url.set(text);
    }, { big: true });
    this.status = h("div", { hidden: true });
    this.error = h("div.error-msg", { hidden: true });
    this.empty = h("div.card", emptyState(t("video.empty")));
    this.details = h("div.col", { hidden: true, style: { gap: "12px" } });
    $("#view-video").append(
      header(t("video.title"), t("video.subtitle")),
      h("div.search-row", this.url, paste, this.analyzeBtn),
      this.status, this.error, this.empty, this.details);
  },

  busy(text) {
    this.status.hidden = !text;
    this.status.replaceChildren(text ? loadingRow(text) : "");
    this.analyzeBtn.disabled = !!text;
  },

  useUrl(url) { this.url.set(url); this.analyze(); },

  async analyze() {
    const url = this.url.input.value.trim();
    if (this.analyzeBtn.disabled) return;
    this.error.hidden = true;
    if (!isUrl(url)) { this.error.textContent = t("video.need_https"); this.error.hidden = false; return; }
    this.details.hidden = true;
    this.empty.hidden = true;
    const isList = url.includes("list=") && !url.includes("v=");
    this.busy(t(isList ? "video.reading_playlist" : "video.reading_formats"));
    const r = await api.analyze(url, "video");
    this.busy(null);
    if (r.error) {
      this.error.textContent = r.error; this.error.hidden = false; this.empty.hidden = false;
      return;
    }
    if (r.type === "playlist") { this.empty.hidden = false; return playlistDialog(r, "video", url); }
    this.show(r.info);
  },

  show(info) {
    this.info = info;
    this.res = 0;
    const s = S.settings;

    // Resolución: "Mejor" + las que tiene el video
    const best = info.resolutions[0]?.label || "";
    const highest = t("video.highest");
    const choices = [[0, t("video.best"), best ? `${best} · ${highest}` : highest], ...info.resolutions.map((r) => [r.res, r.label, r.detail])];
    this.chips = choices.map(([value, label, detail]) => {
      const c = h("button.chip", { type: "button", className: value === 0 ? "on" : "", onclick: () => {
        this.res = value;
        this.chips.forEach((x) => x.classList.toggle("on", x === c));
        this.updateSummary();
      } }, h("b", { text: label }), h("small", { text: detail || " " }));
      return c;
    });

    // Formato
    const containerDesc = h("div.small.muted", { text: t("format." + s.video_container) });
    const container = segmented([["mp4", "MP4"], ["mkv", "MKV"]], s.video_container, (v) => {
      setSetting("video_container", v);
      containerDesc.textContent = t("format." + v);
      this.updateSummary();
    });

    // Subtítulos
    const subs = info.subtitles;
    const hasSubs = subs.length > 0;
    // Por defecto, los subtítulos en el idioma de la app (si el video los tiene)
    const def = subs.find((x) => x.code.startsWith(S.lang) && !x.auto) || subs[0];
    this.subLang = selectBox({
      label: t("video.subs_language"), width: 320, value: def ? `${def.code}|${def.auto ? 1 : 0}` : "",
      options: subs.map((x) => [`${x.code}|${x.auto ? 1 : 0}`, x.label]), onchange: () => this.updateSummary(),
    });
    this.subMode = s.video_subs_embed ? "embed" : "file";
    const mode = radioGroup([["embed", t("video.subs_embed")], ["file", t("video.subs_file")]], this.subMode, (v) => {
      this.subMode = v;
      setSetting("video_subs_embed", v === "embed");
    });
    mode.style.flexDirection = "row";
    mode.style.gap = "16px";
    const subBox = h("div.col", { style: { gap: "8px" }, hidden: !(s.video_subs && hasSubs) }, this.subLang, mode);
    this.subs = switchBox(t("video.subs_download"), s.video_subs && hasSubs, (v) => {
      setSetting("video_subs", v);
      subBox.hidden = !v;
      this.updateSummary();
    });
    this.subs.setDisabled(!hasSubs);

    let found = t("video.found", { n: info.resolutions.length });
    if (hasSubs) found += " · " + t("video.found_subs", { n: subs.length });
    this.summary = h("div.bold");

    this.details.replaceChildren(
      card(h("div.video-head",
        thumb(info.thumbnail, 224, 126, info.duration),
        h("div.col", { style: { gap: "6px" } },
          h("div.video-title", { text: info.title }),
          h("div.muted", { text: [info.channel, info.duration].filter(Boolean).join(" · ") }),
          h("div.row.small.ok-text", { style: { gap: "6px" } }, icon("check"), found)))),
      card(h("div.col", { style: { gap: "16px" } },
        h("div.col", sectionLabel(t("video.resolution")), h("div.row.wrap", { style: { gap: "8px" } }, this.chips),
          h("div.small.muted", { text: t("video.resolution_note") })),
        h("hr.divider"),
        h("div.video-grid",
          h("div.col", sectionLabel(t("common.format")), container, containerDesc),
          h("div.col", sectionLabel(t("video.subtitles")), this.subs, subBox,
            hasSubs ? null : h("div.small.muted", { text: t("video.no_subs") }))))),
      card(h("div.row", { style: { gap: "12px" } },
        h("div.grow", this.summary, h("div.tiny.muted.ellipsis", { text: t("video.save_in", { path: s.video_dir }) })),
        button("filled", t("common.download"), "download", () => this.add(), { big: true }))));
    this.details.hidden = false;
    this.updateSummary();
  },

  options() {
    const o = { kind: "video", res: this.res || null, container: S.settings.video_container, subs: false, music: !!this.info?.music };
    const lang = this.subLang?.select.value;
    if (this.subs?.input.checked && lang) {
      const [code, auto] = lang.split("|");
      Object.assign(o, { subs: true, sub_lang: code, sub_auto: auto === "1", subs_embed: this.subMode === "embed" });
    }
    return o;
  },

  async updateSummary() { this.summary.textContent = await api.describe(this.options()); },

  async add() {
    if (!this.info) return;
    await api.add("video", [{ url: this.info.url, title: this.info.title }], this.options());
    toast(t("common.added"));
  },
};

// ================================================================== pestaña Descargas

const Queue = {
  cards: new Map(),

  build() {
    this.head = header(t("nav.queue"), "");
    this.parallel = h("span.num", { text: S.settings.max_parallel });
    const step = async (d) => { this.parallel.textContent = await api.set_parallel(d); };
    this.pauseAll = button("outlined", t("queue.pause_all"), "pause", () => {
      api.queue_all(this.count("waiting", "downloading", "processing") ? "pause" : "resume");
    });
    this.list = h("div.col", { style: { gap: "10px" } });
    $("#view-queue").append(
      this.head,
      h("div.toolbar",
        h("div.stepper", h("span", { text: t("queue.parallel") }),
          iconButton("remove", t("queue.less"), () => step(-1)), this.parallel, iconButton("add", t("queue.more"), () => step(1))),
        h("div.row", this.pauseAll, button("outlined", t("queue.clear_done"), "done_all", () => api.queue_all("clear_done")))),
      this.list,
      h("div.small.muted", { text: t("queue.resume_note") }));
    this.rebuild();
  },

  count(...statuses) {
    let n = 0;
    for (const it of S.items.values()) if (statuses.includes(it.status)) n++;
    return n;
  },

  setAll(list) {
    S.items = new Map(list.map((i) => [i.id, i]));
    S.order = list.map((i) => i.id);
    this.rebuild();
  },

  update(item) {
    if (!S.items.has(item.id)) return;
    S.items.set(item.id, item);
    this.cards.get(item.id)?.refresh(item);
    this.updateHeader();
  },

  rebuild() {
    const cards = new Map();
    for (const id of S.order) {
      const item = S.items.get(id);
      let c = this.cards.get(id);
      if (!c) { c = this.makeCard(item); if (this.cards.size) c.el.classList.add("enter"); }
      c.refresh(item);
      cards.set(id, c);
    }
    this.cards = cards;
    this.list.replaceChildren(...(cards.size ? [...cards.values()].map((c) => c.el)
      : [h("div.card", emptyState(t("queue.empty")))]));
    this.updateHeader();
  },

  makeCard(item) {
    const title = h("div.title.ellipsis");
    const state = h("span.state");
    const barFill = h("div");
    const bar = h("div.bar", barFill);
    const detail = h("div.detail.clamp2");
    const actions = h("div.actions");
    const el = h("div.card.qcard", kindThumb(item, 78, 44), h("div.info", h("div.top", title, state), bar, detail), actions);
    let shown = "";
    const c = {
      el,
      refresh: (it) => {
        title.textContent = it.title;
        title.dataset.tip = it.title.length > 60 ? it.title : "";
        const pct = (it.status === "downloading" || it.status === "paused") && it.fraction ? ` · ${Math.round(it.fraction * 100)}%` : "";
        state.textContent = t("status." + it.status) + pct;
        state.className = "state st-" + it.status;
        bar.hidden = !["downloading", "processing", "paused"].includes(it.status);
        bar.classList.toggle("warn", it.status === "paused");
        // Barra "infinita" mientras procesa o si aún no se sabe el tamaño
        const unknown = it.status === "processing" || it.fraction === null;
        bar.classList.toggle("indeterminate", unknown);
        barFill.style.width = unknown ? "" : `${(it.fraction || 0) * 100}%`;
        const parts = [it.label];
        if (it.status === "downloading") parts.push(it.speed, it.eta ? t("queue.eta", { eta: it.eta }) : "");
        else if (it.status === "waiting") parts.push(t("queue.waiting_turn"));
        else if (it.status === "error") parts.push(it.error);
        else if (it.status === "done") parts.push(it.file);
        detail.textContent = parts.filter(Boolean).join(" · ");
        detail.classList.toggle("err-text", it.status === "error");
        if (it.status !== shown) { shown = it.status; actions.replaceChildren(...this.buttons(it)); }
      },
    };
    return c;
  },

  buttons(it) {
    const act = (a) => () => api.queue_action(a, it.id);
    const b = [];
    if (["downloading", "processing", "waiting"].includes(it.status)) b.push(iconButton("pause", t("queue.pause"), act("pause")));
    if (it.status === "paused") b.push(iconButton("play_arrow", t("queue.resume"), act("resume")));
    if (it.status === "error") b.push(iconButton("refresh", t("common.retry"), act("retry")));
    if (it.status === "done") {
      b.push(iconButton("play_circle", t("common.open_file"), () => openItem("queue", it.id, "file"), true));
      b.push(iconButton("folder_open", t("common.open_folder"), () => openItem("queue", it.id, "folder"), true));
    } else {
      b.push(iconButton("close", t("common.cancel"), act("cancel")));
    }
    return b;
  },

  updateHeader() {
    const parts = [];
    for (const st of ["downloading", "processing", "waiting", "paused", "error"]) {
      const n = this.count(st);
      if (n) parts.push(t(st === "error" ? "queue.count_errors" : "queue.count_" + st, { n }));
    }
    this.head.sub.textContent = parts.join(" · ") || t("queue.none_pending");
    const active = this.count("waiting", "downloading", "processing");
    const paused = this.count("paused");
    if (active || !paused) setButton(this.pauseAll, t("queue.pause_all"), "pause");
    else setButton(this.pauseAll, t("queue.resume_all"), "play_arrow");
    this.pauseAll.disabled = !active && !paused;
  },
};

async function openItem(where, id, what) {
  const msg = await api.open_item(where, id, what);
  if (msg) toast(msg);
}

// ================================================================== pestaña Historial

const History = {
  kind: "all",
  days: "all",

  build() {
    this.head = header(t("history.title"), "");
    this.clearBtn = button("outlined", t("history.clear"), "delete_sweep", () => this.askClear(), { outlined: true });
    this.head.append(this.clearBtn);
    this.search = textField({ iconName: "search", placeholder: t("history.search"), onInput: () => this.render() });
    const kind = segmented([["all", t("history.all")], ["audio", t("nav.audio")], ["video", t("nav.video")]], "all", (v) => { this.kind = v; this.render(); });
    const date = selectBox({
      width: 200, value: "all",
      options: [["all", t("history.any_date")], ["0", t("history.today")], ["7", t("history.last7")], ["30", t("history.last30")]],
      onchange: (v) => { this.days = v; this.render(); },
    });
    this.list = h("div.card.flush");
    $("#view-history").append(this.head, h("div.filters", this.search, kind, date), this.list);
    this.render();
  },

  setAll(list) { S.history = list; this.render(); },

  visible() {
    const q = normalize(this.search.input.value.trim());
    let limit = null;
    if (this.days !== "all") {
      limit = new Date(); limit.setHours(0, 0, 0, 0);
      limit.setDate(limit.getDate() - Number(this.days));
    }
    return S.history.filter((e) =>
      (this.kind === "all" || e.kind === this.kind) &&
      (!limit || new Date(e.date) >= limit) &&
      (!q || normalize(e.title).includes(q)));
  },

  render() {
    const total = S.history.length;
    this.head.sub.textContent = t("history.saved", { n: total });
    this.clearBtn.disabled = total === 0;
    const entries = this.visible();
    if (entries.length) this.list.replaceChildren(...entries.slice(0, 1000).map((e) => this.row(e)));
    else this.list.replaceChildren(emptyState(t(total ? "history.no_match" : "history.empty")));
  },

  row(e) {
    const meta = h("div.meta.ellipsis", [e.label, e.size, niceDate(e.date)].filter(Boolean).join(" · "));
    if (!e.exists) meta.append(" · ", h("span.gone", { text: t("history.gone") }));
    const play = iconButton("play_circle", e.exists ? t("common.open_file") : t("history.file_gone"), () => openItem("history", e.id, "file"), true);
    play.disabled = !e.exists;
    return h("div.hrow",
      kindThumb(e, 64, 36),
      h("div.grow", h("div.title.ellipsis", { text: e.title }), meta),
      h("div.actions",
        play,
        iconButton("folder_open", t("common.open_folder"), () => openItem("history", e.id, "folder"), true),
        iconButton("refresh", t("history.again"), async () => { await api.history_again(e.id); toast(t("history.again_done")); }),
        iconButton("delete", t("history.delete"), () => this.askDelete(e), true)));
  },

  askDelete(e) {
    const also = checkBox(t("history.delete_file"), false);
    const close = openDialog({
      title: t("history.delete_title"),
      body: [h("div.muted", { text: e.title }), e.exists ? also : null],
      actions: [
        button("text", t("common.cancel"), null, () => close()),
        button("filled", t("history.remove"), null, async () => {
          close();
          await api.history_delete(e.id, also.input.checked);
          toast(t(also.input.checked ? "history.file_deleted" : "history.removed"));
        }),
      ],
    });
  },

  askClear() {
    const n = S.history.length;
    const files = S.history.filter((e) => e.exists).length;
    const also = checkBox(t("history.clear_files", { n: files }), false);
    const close = openDialog({
      title: t("history.clear_title"),
      body: [
        h("div.muted", { text: t("history.clear_text", { n }) }),
        files ? also : null,
      ],
      actions: [
        button("text", t("common.cancel"), null, () => close()),
        button("filled", t("history.clear"), null, async () => {
          close();
          await api.history_clear(also.input.checked);
          toast(t(also.input.checked ? "history.cleared_files" : "history.cleared"));
        }),
      ],
    });
  },
};

// ================================================================== pestaña Ajustes

const BROWSERS = [["firefox", "Firefox"], ["chrome", "Chrome"], ["edge", "Edge"], ["brave", "Brave"], ["opera", "Opera"], ["vivaldi", "Vivaldi"]];

const Settings = {
  versionsLoaded: false,

  build() {
    const s = S.settings;
    const set = (k) => (v) => setSetting(k, v);
    const title = (text) => h("div.card-title", { text });
    const note = (text) => h("div.small.muted", { text });

    // Idioma: "" = automático (el del sistema). Al cambiarlo, la página se vuelve a cargar
    // con los textos nuevos y se queda en Ajustes.
    const autoName = S.languages.find(([code]) => code === S.systemLang)?.[1] || S.systemLang;
    const language = card(h("div.col", title(t("settings.language")),
      selectBox({
        width: 260, value: s.language,
        options: [["", t("settings.language_auto", { name: autoName })], ...S.languages],
        onchange: async (v) => {
          await api.set_language(v);
          location.hash = "settings";
          location.reload();
        },
      }),
      note(t("settings.language_note"))));

    // Carpetas
    const folderRow = (label, key) => {
      const path = h("div.folder-path.selectable", h("span.ellipsis", { text: s[key] }));
      return h("div.folder-row", h("span.label", { text: label }), path,
        button("outlined", t("settings.change"), "folder_open", async () => {
          const p = await api.pick_folder(key);
          if (p) { s[key] = p; path.firstChild.textContent = p; }
        }, { outlined: true }));
    };
    const folders = card(h("div.col", { style: { gap: "12px" } }, title(t("settings.folders")),
      folderRow(t("nav.audio"), "audio_dir"), folderRow(t("nav.video"), "video_dir"),
      switchBox(t("settings.playlist_subfolder"), s.playlist_subfolder, set("playlist_subfolder"))));

    // Cookies
    const browser = selectBox({ width: 180, value: s.cookies_browser, options: BROWSERS, onchange: set("cookies_browser") });
    const cookiesFile = h("span.small.muted.ellipsis", { text: s.cookies_file || t("settings.cookies_no_file") });
    const fileBtn = button("outlined", t("settings.cookies_pick"), null, async () => {
      const p = await api.pick_cookies();
      if (p) cookiesFile.textContent = p;
    });
    const rules = (mode) => { browser.select.disabled = mode !== "browser"; fileBtn.disabled = mode !== "file"; };
    const cookies = card(h("div.col", title(t("settings.cookies")),
      note(t("settings.cookies_note")),
      radioGroup([["none", t("settings.cookies_none")], ["browser", t("settings.cookies_browser"), browser],
        ["file", t("settings.cookies_file"), h("div.row.grow", fileBtn, cookiesFile)]],
      s.cookies_mode, (v) => { setSetting("cookies_mode", v); rules(v); })));
    rules(s.cookies_mode);

    // Tema
    this.tiles = h("div.col", { style: { gap: "12px" } });
    const appearance = card(h("div.col", { style: { gap: "12px" } }, title(t("settings.theme")), note(t("settings.theme_note")), this.tiles));
    this.renderTiles();

    // Avisos
    const notices = card(h("div.col", { style: { gap: "2px" } }, title(t("settings.notices")),
      switchBox(t("settings.notify_all"), s.notify_queue_done, set("notify_queue_done")),
      switchBox(t("settings.notify_each"), s.notify_each, set("notify_each")),
      switchBox(t("settings.watch_clipboard"), s.watch_clipboard, set("watch_clipboard"))));

    // Búsqueda
    const searching = card(h("div.col", title(t("settings.search")),
      note(t("settings.search_note")),
      switchBox(t("settings.music_search"), s.music_search, set("music_search"))));

    // Portadas
    const covers = card(h("div.col", title(t("settings.cover")),
      note(t("settings.cover_note")),
      radioGroup(["music", "audio", "video", "both", "none"].map((v) => [v, t("settings.cover_" + v)]), s.cover_crop, set("cover_crop"), 0)));

    // Componentes
    this.ytdlpVersion = h("div.tiny.muted", { text: "…" });
    this.ffmpegVersion = h("div.tiny.muted", { text: "…" });
    this.updateStatus = h("span.small.bold");
    this.updateBtn = button("outlined", t("settings.check_update"), "refresh", () => this.updateYtdlp());
    const components = card(h("div.col", { style: { gap: "12px" } }, title(t("settings.components")),
      h("div.row", h("div.grow", h("div.bold", { text: "yt-dlp" }), this.ytdlpVersion), this.updateStatus, this.updateBtn),
      h("hr.divider"),
      h("div", h("div.bold", { text: "ffmpeg" }), this.ffmpegVersion),
      h("div.col", { style: { gap: "2px" } },
        switchBox(t("settings.auto_update"), s.auto_update_ytdlp, set("auto_update_ytdlp")),
        switchBox(t("settings.app_updates"), s.check_app_updates, set("check_app_updates")))));

    // Acerca de
    const a = S.app;
    const about = card(h("div.col", { style: { gap: "8px" } }, title(t("settings.about", { app: a.name, version: a.version })),
      h("div", { text: t("settings.about_author") }),
      note(t("settings.about_ai")),
      note(t("settings.about_license")),
      note(t("settings.about_disclaimer", { app: a.name })),
      h("div", button("text", t("settings.about_github"), "open_in_new", () => api.open_url(a.repo)))));

    $("#view-settings").append(header(t("settings.title"), t("settings.subtitle")),
      language, folders, cookies, appearance, notices, searching, covers, components, about);
  },

  renderTiles() {
    const tile = (p) => {
      const on = p.id === S.theme;
      return h("button.theme-tile", {
        type: "button",
        style: { background: p.bg, color: p.fg, border: `${on ? 2 : 1}px solid ${on ? p.primary : p.border}` },
        onclick: () => { setSetting("theme", p.id); applyTheme(p.id, true); this.renderTiles(); },
      },
      h("div.name", h("span.ellipsis", { text: p.name }), on ? h("span.i", { text: "check_circle", style: { color: p.primary, fontSize: "18px" } }) : null),
      h("div.sample", { text: t("settings.theme_sample"), style: { background: p.card, color: p.muted } }),
      h("div.swatches", [p.primary, p.secondary, p.ok, p.warn, p.info, p.error].map((c) => h("i", { style: { background: c } }))));
    };
    this.tiles.replaceChildren(
      sectionLabel(t("settings.themes_dark")), h("div.themes", S.themes.filter((p) => p.dark).map(tile)),
      sectionLabel(t("settings.themes_light")), h("div.themes", S.themes.filter((p) => !p.dark).map(tile)));
  },

  async loadVersions() {
    if (this.versionsLoaded) return;
    this.versionsLoaded = true;
    const v = await api.versions();
    this.ytdlpVersion.textContent = t("settings.version", { version: v.ytdlp });
    this.ffmpegVersion.textContent = v.ffmpeg;
  },

  showUpdateResult(ok, message) {
    this.updateStatus.textContent = message;
    this.updateStatus.className = "small bold " + (ok ? "ok-text" : "err-text");
  },

  async updateYtdlp() {
    this.updateBtn.disabled = true;
    this.updateStatus.textContent = t("settings.checking");
    this.updateStatus.className = "small bold muted";
    const r = await api.update_ytdlp();
    this.updateBtn.disabled = false;
    this.showUpdateResult(r.ok, r.message);
    this.ytdlpVersion.textContent = t("settings.version", { version: r.version });
  },
};

// ================================================================== primer arranque

const Setup = {
  steps: {},

  build() {
    const where = S.app.windows ? "%LOCALAPPDATA%\\Onitune" : "~/.local/share/onitune";
    const step = (id, name, desc) => {
      const mark = h("div.mark");
      const pct = h("span.pct");
      const bar = h("div.bar", { hidden: true }, h("div"));
      const el = h("div.step", mark, h("div.body", h("div.row", h("span.name.grow", { text: name }), pct), bar, h("div.small.muted", { text: desc })));
      this.steps[id] = { el, mark, pct, bar };
      return el;
    };
    this.error = h("div.error-msg", { hidden: true });
    this.retry = button("filled", t("common.retry"), "refresh", () => this.run());
    this.retryRow = h("div.row", { hidden: true, style: { justifyContent: "flex-end" } }, this.retry);
    $("#setup").append(h("div.setup-box",
      h("div.setup-head", h("img", { src: S.app.icon, alt: "" }),
        h("div", h("h1", { text: t("setup.title") }), h("div.muted", { text: t("setup.subtitle") }))),
      h("div.col", { style: { gap: "18px" } },
        step("yt-dlp", t("setup.ytdlp"), t("setup.ytdlp_desc")),
        step("ffmpeg", t("setup.ffmpeg"), t("setup.ffmpeg_desc")),
        step("folders", t("setup.folders"), t("setup.folders_desc"))),
      h("div.setup-note", { text: t("setup.note", { path: where }) }),
      this.error,
      this.retryRow));
    $("#setup").hidden = false;
  },

  update({ step, state, fraction, text }) {
    const st = this.steps[step];
    if (!st) return;
    st.el.className = "step " + state;
    st.mark.replaceChildren(state === "done" ? icon("check") : state === "running" ? icon("download") : state === "failed" ? icon("close") : "");
    st.bar.hidden = state !== "running";
    st.bar.classList.toggle("indeterminate", fraction === null);
    if (fraction !== undefined && fraction !== null) st.bar.firstChild.style.width = `${fraction * 100}%`;
    st.pct.textContent = state === "running" ? text || "" : "";
  },

  async run() {
    this.error.hidden = true;
    this.retryRow.hidden = true;
    const r = await api.run_setup();
    if (r.ok) return start();
    for (const st of Object.values(this.steps)) if (st.el.classList.contains("running")) { st.el.className = "step failed"; st.mark.replaceChildren(icon("close")); st.bar.hidden = true; }
    this.error.textContent = r.error;
    this.error.hidden = false;
    this.retryRow.hidden = false;
  },
};

// ================================================================== mensajes de Python

const handlers = {
  item: (it) => Queue.update(it),
  queue: (list) => Queue.setAll(list),
  counts: (c) => { S.counts = c; updateBadge(); },
  history: (list) => History.setAll(list),
  ytdlp: (st) => showYtdlpStatus(st),
  app_update: (info) => Banners.showUpdate(info),
  clip: (c) => Banners.showClip(c),
  setup: (st) => Setup.update(st),
};

window.onitune = {
  receive(events) {
    for (const [name, data] of events) {
      try { handlers[name]?.(data); } catch (err) { console.error(name, err); }
    }
  },
  // Para los scripts de prueba (ui_tour.py, marketing_shots.py)
  go: (view) => go(view),
  setTheme: (id) => { applyTheme(id); if (Settings.tiles) Settings.renderTiles(); },
  audio: () => Audio,
  video: () => Video,
  scroll: (fraction) => { const s = $("#scroll"); s.scrollTop = (s.scrollHeight - s.clientHeight) * fraction; },
};

// ================================================================== arranque

let built = false;
async function start() {
  const state = await api.init();
  Object.assign(S, {
    app: state.app, settings: state.settings, themes: state.themes,
    lang: state.lang, languages: state.languages, systemLang: state.system_lang,
  });
  TEXTS = state.texts;
  document.documentElement.lang = state.lang;
  // Textos fijos de index.html (los que tienen data-t="clave")
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  applyTheme(state.theme);
  if (state.setup) {
    if (!Setup.el) { Setup.el = true; Setup.build(); Setup.run(); }
    return;
  }
  $("#setup").hidden = true;
  if (!built) {
    built = true;
    buildNav();
    Audio.build(); Video.build(); Queue.build(); History.build(); Settings.build();
    Settings.loadVersions(); // tarda 1-2 s: se pide ya, en segundo plano
  }
  S.counts = state.counts;
  Queue.setAll(state.queue);
  History.setAll(state.history);
  showYtdlpStatus(state.ytdlp);
  if (state.app_update) Banners.showUpdate(state.app_update);
  $("#main").hidden = false;
  // Después de cambiar el idioma se vuelve a la pestaña de antes (va en la dirección: "#settings")
  const fromHash = location.hash.slice(1);
  if (NAV.some(([id]) => id === fromHash)) S.view = fromHash;
  history.replaceState(null, "", location.pathname);
  go(S.view);
}

window.addEventListener("pywebviewready", () => { api = window.pywebview.api; start(); });
// Clic derecho: solo en campos de texto (copiar/pegar); con ONITUNE_DEBUG=1, en todas partes (Inspeccionar)
document.addEventListener("contextmenu", (e) => { if (!S.app.debug && !e.target.closest("input")) e.preventDefault(); });
