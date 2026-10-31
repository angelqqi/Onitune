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

function plural(n, word, suffix = "s") { return `${n} ${word}${n === 1 ? "" : suffix}`; }

function normalize(text) {
  // Minúsculas y sin tildes, para que "cancion" encuentre "Canción"
  return (text || "").normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase();
}

const isUrl = (text) => /^https?:\/\//i.test((text || "").trim());

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
function niceDate(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const day = new Date(d); day.setHours(0, 0, 0, 0);
  const hour = d.toTimeString().slice(0, 5);
  const diff = Math.round((today - day) / 86400000);
  if (diff === 0) return `Hoy, ${hour}`;
  if (diff === 1) return `Ayer, ${hour}`;
  const text = `${d.getDate()} ${MONTHS[d.getMonth()]}`;
  return d.getFullYear() === today.getFullYear() ? text : `${text} ${d.getFullYear()}`;
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
  const clear = iconButton("close", "Borrar", () => { input.value = ""; sync(); input.focus(); });
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
    options.map(([v, t]) => h("option", { value: v, text: t })));
  sel.value = value;
  const wrap = h("div.select", { style: { width: width ? width + "px" : "" } }, sel);
  if (label) wrap.append(h("span.float", { text: label }));
  wrap.select = sel;
  return wrap;
}

/** Botón segmentado (MP3 | M4A | ...). */
function segmented(options, value, onchange) {
  const wrap = h("div.segmented");
  const buttons = options.map(([v, t]) => h("button", {
    type: "button", text: t, className: v === value ? "on" : "",
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
  const t = h("div.toast", { text: message });
  $("#toasts").append(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 250); }, 2500);
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
  app: {}, settings: {}, themes: [], theme: "dracula",
  items: new Map(), order: [], history: [], counts: { pending: 0, running: 0 },
  view: "audio",
};

async function setSetting(name, value) {
  S.settings[name] = value;
  await api.set_setting(name, value);
}

const THEME_VARS = ["bg", "rail", "card", "high", "border", "fg", "muted", "primary", "secondary", "ok", "warn", "info", "error"];
function applyTheme(id, animate = false) {
  const p = S.themes.find((t) => t.id === id) || S.themes[0];
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

const NAV = [
  ["audio", "Audio", "music_note"],
  ["video", "Video", "movie"],
  ["queue", "Descargas", "download"],
  ["history", "Historial", "history"],
  ["settings", "Ajustes", "tune"],
];
const navButtons = {};

function buildNav() {
  const box = $("#destinations");
  for (const [id, label, ic] of NAV) {
    const ind = h("span.ind", icon(ic, true));
    const b = h("button.dest", { type: "button", onclick: () => go(id) }, ind, h("span", { text: label }));
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
  txt.textContent = running ? `${running} descargando ahora` : "Sin descargas activas";
  txt.className = running ? "" : "muted";
}

function showYtdlpStatus(status) {
  $("#dot-ytdlp").className = "dot " + (status.ok ? "ok" : "warn");
  $("#txt-ytdlp").textContent = status.ok ? "yt-dlp listo" : "yt-dlp sin actualizar";
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
      h("div.text", h("div.t", { text: `Hay una versión nueva de ${S.app.name}: ${info.version}` }),
        h("div.small.muted", { text: `Versión instalada: ${S.app.version}` })),
      button("text", "Ahora no", null, () => { this.update.remove(); this.update = null; }),
      button("filled", "Descargar", "open_in_new", () => api.open_url(info.url)));
    $("#banners").prepend(this.update);
  },

  showClip({ url, playlist }) {
    this.clip?.remove();
    this.clipUrl = url;
    this.clip = h("div.banner",
      icon("content_paste"),
      h("div.text", h("div.t", { text: playlist ? "Enlace de playlist copiado" : "Enlace de YouTube copiado" }),
        h("div.small.muted.ellipsis", { text: url })),
      button("text", "Ignorar", null, () => this.dismissClip()),
      button("outlined", "Video", "movie", () => this.useClip("video"), { outlined: true }),
      button("filled", "Audio", "music_note", () => this.useClip("audio")));
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

const FORMATS = {
  mp3: "El más compatible: funciona en cualquier reproductor, auto o celular.",
  m4a: "Muy compatible y con mejor calidad que MP3 al mismo tamaño. YouTube ya lo entrega así, sin reconvertir.",
  opus: "El audio original de YouTube: la mejor calidad por tamaño. Algunos reproductores antiguos no lo abren.",
  flac: "Sin pérdida al guardar, pero YouTube no tiene audio sin pérdida: no suena mejor, solo ocupa más.",
  wav: "Sin compresión, útil para editar audio. Los archivos son muy grandes.",
};

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
    h("div.row", { style: { gap: "4px" } }, button("text", "Seleccionar todo", null, () => setAll(true)), button("text", "Ninguno", null, () => setAll(false))),
    h("div.pl-list", checks.map((c) => c.row)),
  ];
  if (kind === "video") {
    res = selectBox({ label: "Calidad máxima", width: 220, value: "0", options: GENERIC_RES });
    container = segmented([["mp4", "MP4"], ["mkv", "MKV"]], S.settings.video_container);
    body.push(h("div.row", { style: { gap: "16px" } }, res, container));
  }
  body.push(h("div.small.muted", { text: data.folder_note }));

  const close = openDialog({
    title: info.title, subtitle: `Playlist · ${plural(info.entries.length, "video")}`, wide: true, body,
    actions: [button("text", "Cancelar", null, () => close()), addBtn],
  });

  function selected() { return checks.filter((c) => c.input.checked).map((c) => ({ url: c.e.url, title: c.e.title })); }
  function refresh() {
    const n = selected().length;
    setButton(addBtn, `Descargar ${plural(n, "video")}`);
    addBtn.disabled = n === 0;
  }
  async function add() {
    const items = selected();
    const opts = kind === "video"
      ? { res: Number(res.select.value) || null, container: container.value, subs: false, music: data.music }
      : { music: data.music };
    close();
    const n = await api.add(kind, items, opts, info.title);
    toast(`${plural(n, "video")} agregado${n === 1 ? "" : "s"} a descargas`);
  }
  refresh();
}

const Audio = {
  build() {
    const s = S.settings;
    this.query = textField({
      iconName: "search", placeholder: "Enlace de YouTube o nombre de una canción",
      onEnter: () => this.go(), onInput: () => this.updateButton(),
    });
    this.goBtn = button("filled", "Buscar", "search", () => this.go(), { big: true });
    const paste = button("outlined", "Pegar", "content_paste", async () => {
      const text = await api.get_clipboard();
      if (text) { this.query.set(text); this.query.input.focus(); }
    }, { big: true });

    // Opciones
    this.formatDesc = h("div.small.muted", { text: FORMATS[s.audio_format] });
    const format = segmented(Object.keys(FORMATS).map((k) => [k, k.toUpperCase()]), s.audio_format, (v) => {
      setSetting("audio_format", v);
      this.formatDesc.textContent = FORMATS[v];
      this.applyRules();
    });
    this.quality = selectBox({
      label: "Calidad", width: 220, value: s.audio_quality,
      options: [["best", "Mejor disponible"], ["320", "320 kbps"], ["256", "256 kbps"], ["192", "192 kbps"], ["128", "128 kbps"]],
      onchange: (v) => setSetting("audio_quality", v),
    });
    this.qualityNote = h("div.small.muted", { text: "No aplica a formatos sin pérdida.", hidden: true });
    this.cover = switchBox("Incrustar portada", s.audio_cover, (v) => setSetting("audio_cover", v));
    const meta = switchBox("Agregar metadatos (título, artista, álbum)", s.audio_metadata, (v) => setSetting("audio_metadata", v));

    const options = card(h("div.col", { style: { gap: "14px" } },
      h("div.options-grid",
        h("div.col", sectionLabel("Formato"), format, this.formatDesc),
        h("div.col", sectionLabel("Calidad"), this.quality, this.qualityNote)),
      h("hr.divider"),
      h("div.row.wrap", { style: { gap: "8px 32px" } }, this.cover, meta)));

    this.status = h("div", { hidden: true });
    this.error = h("div.error-msg", { hidden: true });
    this.resultsTitle = h("div.results-title");
    this.resultsList = h("div.card.flush");
    this.results = h("div.col", { hidden: true, style: { gap: "12px" } }, this.resultsTitle, this.resultsList);

    $("#view-audio").append(
      header("Descargar audio", "Enlace de YouTube o nombre de una canción para buscar."),
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
    if (isUrl(this.query.input.value)) setButton(this.goBtn, "Descargar", "download");
    else setButton(this.goBtn, "Buscar", "search");
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
      this.busy("Analizando el enlace…");
      const r = await api.analyze(text, "audio");
      this.busy(null);
      if (r.error) return this.showError(r.error);
      if (r.type === "playlist") return playlistDialog(r, "audio", text);
      await api.add("audio", [{ url: text, title: r.info.title }], { music: r.info.music });
      this.query.set("");
      this.updateButton();
      toast("Agregado a descargas");
    } else {
      this.results.hidden = true;
      const where = S.settings.music_search ? " en YouTube Music" : "";
      this.busy(`Buscando “${text}”${where}…`);
      const r = await api.search(text);
      this.busy(null);
      if (r.error) return this.showError(r.error);
      this.resultsTitle.textContent = `Resultados para “${text}”`;
      this.resultsList.replaceChildren(...(r.results.length ? r.results.map((x) => this.resultRow(x)) : [emptyState("No se encontró nada.")]));
      this.results.hidden = false;
    }
  },

  resultRow(r) {
    let action;
    if (r.live) {
      action = h("span.live", { text: "En vivo", tip: "Las transmisiones en vivo no se pueden descargar" });
    } else {
      action = button("outlined", "Descargar", "download", async () => {
        action.replaceWith(h("span.added", icon("check"), "En descargas"));
        await api.add("audio", [{ url: r.url, title: r.title }], { music: r.music });
        toast("Agregado a descargas");
      });
    }
    return h("div.result",
      thumb(r.thumbnail, 104, 58, r.live ? "EN VIVO" : r.duration),
      h("div.grow", h("div.bold.clamp2", { text: r.title }), h("div.small.muted", { text: r.channel })),
      action);
  },
};

// ================================================================== pestaña Video

const CONTAINERS = {
  mp4: "Se reproduce en todo: Windows, celulares, televisores.",
  mkv: "Guarda la calidad original sin convertir. Algunos televisores y celulares no lo abren.",
};
// Para playlists no se analiza cada video: se ofrecen calidades típicas
const GENERIC_RES = [["0", "Mejor disponible"], ["2160", "2160p 4K"], ["1440", "1440p"], ["1080", "1080p"], ["720", "720p"], ["480", "480p"], ["360", "360p"]];

const Video = {
  info: null,
  res: 0,

  build() {
    this.url = textField({ iconName: "link", placeholder: "https://www.youtube.com/watch?v=…", onEnter: () => this.analyze() });
    this.analyzeBtn = button("filled", "Analizar", "search", () => this.analyze(), { big: true });
    const paste = button("outlined", "Pegar", "content_paste", async () => {
      const text = await api.get_clipboard();
      if (text) this.url.set(text);
    }, { big: true });
    this.status = h("div", { hidden: true });
    this.error = h("div.error-msg", { hidden: true });
    this.empty = h("div.card", emptyState("Las calidades disponibles aparecerán aquí después de analizar un enlace."));
    this.details = h("div.col", { hidden: true, style: { gap: "12px" } });
    $("#view-video").append(
      header("Descargar video", "Al analizar un enlace se muestran las calidades disponibles del video."),
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
    if (!isUrl(url)) { this.error.textContent = "El enlace debe empezar por https://"; this.error.hidden = false; return; }
    this.details.hidden = true;
    this.empty.hidden = true;
    const isList = url.includes("list=") && !url.includes("v=");
    this.busy(isList ? "Leyendo la playlist…" : "Leyendo los formatos del video…");
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
    const choices = [[0, "Mejor", best ? `${best} · la más alta` : "la más alta"], ...info.resolutions.map((r) => [r.res, r.label, r.detail])];
    this.chips = choices.map(([value, label, detail]) => {
      const c = h("button.chip", { type: "button", className: value === 0 ? "on" : "", onclick: () => {
        this.res = value;
        this.chips.forEach((x) => x.classList.toggle("on", x === c));
        this.updateSummary();
      } }, h("b", { text: label }), h("small", { text: detail || " " }));
      return c;
    });

    // Formato
    const containerDesc = h("div.small.muted", { text: CONTAINERS[s.video_container] });
    const container = segmented([["mp4", "MP4"], ["mkv", "MKV"]], s.video_container, (v) => {
      setSetting("video_container", v);
      containerDesc.textContent = CONTAINERS[v];
      this.updateSummary();
    });

    // Subtítulos
    const subs = info.subtitles;
    const hasSubs = subs.length > 0;
    const def = subs.find((x) => x.code.startsWith("es") && !x.auto) || subs[0];
    this.subLang = selectBox({
      label: "Idioma", width: 320, value: def ? `${def.code}|${def.auto ? 1 : 0}` : "",
      options: subs.map((x) => [`${x.code}|${x.auto ? 1 : 0}`, x.label]), onchange: () => this.updateSummary(),
    });
    this.subMode = s.video_subs_embed ? "embed" : "file";
    const mode = radioGroup([["embed", "Incrustar en el video"], ["file", "Archivo .srt aparte"]], this.subMode, (v) => {
      this.subMode = v;
      setSetting("video_subs_embed", v === "embed");
    });
    mode.style.flexDirection = "row";
    mode.style.gap = "16px";
    const subBox = h("div.col", { style: { gap: "8px" }, hidden: !(s.video_subs && hasSubs) }, this.subLang, mode);
    this.subs = switchBox("Descargar subtítulos", s.video_subs && hasSubs, (v) => {
      setSetting("video_subs", v);
      subBox.hidden = !v;
      this.updateSummary();
    });
    this.subs.setDisabled(!hasSubs);

    let found = `${info.resolutions.length} calidades encontradas`;
    if (hasSubs) found += ` · subtítulos en ${plural(subs.length, "idioma")}`;
    this.summary = h("div.bold");

    this.details.replaceChildren(
      card(h("div.video-head",
        thumb(info.thumbnail, 224, 126, info.duration),
        h("div.col", { style: { gap: "6px" } },
          h("div.video-title", { text: info.title }),
          h("div.muted", { text: [info.channel, info.duration].filter(Boolean).join(" · ") }),
          h("div.row.small.ok-text", { style: { gap: "6px" } }, icon("check"), found)))),
      card(h("div.col", { style: { gap: "16px" } },
        h("div.col", sectionLabel("Resolución"), h("div.row.wrap", { style: { gap: "8px" } }, this.chips),
          h("div.small.muted", { text: "Solo aparecen las calidades que este video tiene de verdad. Los tamaños son aproximados." })),
        h("hr.divider"),
        h("div.video-grid",
          h("div.col", sectionLabel("Formato"), container, containerDesc),
          h("div.col", sectionLabel("Subtítulos"), this.subs, subBox,
            hasSubs ? null : h("div.small.muted", { text: "Este video no tiene subtítulos." }))))),
      card(h("div.row", { style: { gap: "12px" } },
        h("div.grow", this.summary, h("div.tiny.muted.ellipsis", { text: `Se guardará en: ${s.video_dir}` })),
        button("filled", "Descargar", "download", () => this.add(), { big: true }))));
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
    toast("Agregado a descargas");
  },
};

// ================================================================== pestaña Descargas

const STATUS = {
  waiting: "En espera", downloading: "Descargando", processing: "Procesando…",
  paused: "Pausado", error: "Error", done: "Completado",
};

const Queue = {
  cards: new Map(),

  build() {
    this.head = header("Descargas", "");
    this.parallel = h("span.num", { text: S.settings.max_parallel });
    const step = async (d) => { this.parallel.textContent = await api.set_parallel(d); };
    this.pauseAll = button("outlined", "Pausar todo", "pause", () => {
      api.queue_all(this.count("waiting", "downloading", "processing") ? "pause" : "resume");
    });
    this.list = h("div.col", { style: { gap: "10px" } });
    $("#view-queue").append(
      this.head,
      h("div.toolbar",
        h("div.stepper", h("span", { text: "Descargas a la vez" }),
          iconButton("remove", "Menos", () => step(-1)), this.parallel, iconButton("add", "Más", () => step(1))),
        h("div.row", this.pauseAll, button("outlined", "Quitar completadas", "done_all", () => api.queue_all("clear_done")))),
      this.list,
      h("div.small.muted", { text: "Las descargas pendientes se guardan: continúan al volver a abrir la app." }));
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
      : [h("div.card", emptyState("No hay descargas. Se pueden agregar desde Audio o Video."))]));
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
        state.textContent = (STATUS[it.status] || "") + pct;
        state.className = "state st-" + it.status;
        bar.hidden = !["downloading", "processing", "paused"].includes(it.status);
        bar.classList.toggle("warn", it.status === "paused");
        // Barra "infinita" mientras procesa o si aún no se sabe el tamaño
        const unknown = it.status === "processing" || it.fraction === null;
        bar.classList.toggle("indeterminate", unknown);
        barFill.style.width = unknown ? "" : `${(it.fraction || 0) * 100}%`;
        const parts = [it.label];
        if (it.status === "downloading") parts.push(it.speed, it.eta ? `quedan ${it.eta}` : "");
        else if (it.status === "waiting") parts.push("Esperando turno");
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
    if (["downloading", "processing", "waiting"].includes(it.status)) b.push(iconButton("pause", "Pausar", act("pause")));
    if (it.status === "paused") b.push(iconButton("play_arrow", "Reanudar", act("resume")));
    if (it.status === "error") b.push(iconButton("refresh", "Reintentar", act("retry")));
    if (it.status === "done") {
      b.push(iconButton("play_circle", "Abrir archivo", () => openItem("queue", it.id, "file"), true));
      b.push(iconButton("folder_open", "Abrir carpeta", () => openItem("queue", it.id, "folder"), true));
    } else {
      b.push(iconButton("close", "Cancelar", act("cancel")));
    }
    return b;
  },

  updateHeader() {
    const parts = [];
    for (const [st, word] of [["downloading", "descargando"], ["processing", "procesando"], ["waiting", "en espera"], ["paused", "en pausa"]]) {
      const n = this.count(st);
      if (n) parts.push(`${n} ${word}`);
    }
    const errors = this.count("error");
    if (errors) parts.push(`${errors} con error${errors === 1 ? "" : "es"}`);
    this.head.sub.textContent = parts.join(" · ") || "No hay descargas pendientes";
    const active = this.count("waiting", "downloading", "processing");
    const paused = this.count("paused");
    if (active || !paused) setButton(this.pauseAll, "Pausar todo", "pause");
    else setButton(this.pauseAll, "Reanudar todo", "play_arrow");
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
    this.head = header("Historial", "");
    this.clearBtn = button("outlined", "Limpiar historial", "delete_sweep", () => this.askClear(), { outlined: true });
    this.head.append(this.clearBtn);
    this.search = textField({ iconName: "search", placeholder: "Buscar por título", onInput: () => this.render() });
    const kind = segmented([["all", "Todo"], ["audio", "Audio"], ["video", "Video"]], "all", (v) => { this.kind = v; this.render(); });
    const date = selectBox({
      width: 200, value: "all",
      options: [["all", "Cualquier fecha"], ["0", "Hoy"], ["7", "Últimos 7 días"], ["30", "Últimos 30 días"]],
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
    this.head.sub.textContent = `${plural(total, "descarga")} guardada${total === 1 ? "" : "s"}`;
    this.clearBtn.disabled = total === 0;
    const entries = this.visible();
    if (entries.length) this.list.replaceChildren(...entries.slice(0, 1000).map((e) => this.row(e)));
    else this.list.replaceChildren(emptyState(total ? "No hay descargas que coincidan con el filtro." : "Todavía no hay descargas."));
  },

  row(e) {
    const meta = h("div.meta.ellipsis", [e.label, e.size, niceDate(e.date)].filter(Boolean).join(" · "));
    if (!e.exists) meta.append(" · ", h("span.gone", { text: "archivo movido o borrado" }));
    const play = iconButton("play_circle", e.exists ? "Abrir archivo" : "El archivo ya no está", () => openItem("history", e.id, "file"), true);
    play.disabled = !e.exists;
    return h("div.hrow",
      kindThumb(e, 64, 36),
      h("div.grow", h("div.title.ellipsis", { text: e.title }), meta),
      h("div.actions",
        play,
        iconButton("folder_open", "Abrir carpeta", () => openItem("history", e.id, "folder"), true),
        iconButton("refresh", "Volver a descargar", async () => { await api.history_again(e.id); toast("Agregado de nuevo a descargas"); }),
        iconButton("delete", "Borrar del historial", () => this.askDelete(e), true)));
  },

  askDelete(e) {
    const also = checkBox("Borrar también el archivo del disco", false);
    const close = openDialog({
      title: "¿Quitar del historial?",
      body: [h("div.muted", { text: e.title }), e.exists ? also : null],
      actions: [
        button("text", "Cancelar", null, () => close()),
        button("filled", "Quitar", null, async () => {
          close();
          await api.history_delete(e.id, also.input.checked);
          toast(also.input.checked ? "Archivo borrado" : "Quitado del historial");
        }),
      ],
    });
  },

  askClear() {
    const n = S.history.length;
    const files = S.history.filter((e) => e.exists).length;
    const also = checkBox(`Borrar también los archivos del disco (${plural(files, "archivo")})`, false);
    const close = openDialog({
      title: "¿Limpiar todo el historial?",
      body: [
        h("div.muted", { text: `Se quitarán ${plural(n, "descarga")} del historial. Los archivos se quedan en su carpeta, salvo que se marque la casilla.` }),
        files ? also : null,
      ],
      actions: [
        button("text", "Cancelar", null, () => close()),
        button("filled", "Limpiar historial", null, async () => {
          close();
          await api.history_clear(also.input.checked);
          toast(also.input.checked ? "Historial y archivos borrados" : "Historial limpio");
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
    const title = (t) => h("div.card-title", { text: t });
    const note = (t) => h("div.small.muted", { text: t });

    // Carpetas
    const folderRow = (label, key) => {
      const path = h("div.folder-path.selectable", h("span.ellipsis", { text: s[key] }));
      return h("div.folder-row", h("span.label", { text: label }), path,
        button("outlined", "Cambiar", "folder_open", async () => {
          const p = await api.pick_folder(key);
          if (p) { s[key] = p; path.firstChild.textContent = p; }
        }, { outlined: true }));
    };
    const folders = card(h("div.col", { style: { gap: "12px" } }, title("Carpetas de descarga"),
      folderRow("Audio", "audio_dir"), folderRow("Video", "video_dir"),
      switchBox("Guardar cada playlist en su propia subcarpeta", s.playlist_subfolder, set("playlist_subfolder"))));

    // Cookies
    const browser = selectBox({ width: 180, value: s.cookies_browser, options: BROWSERS, onchange: set("cookies_browser") });
    const cookiesFile = h("span.small.muted.ellipsis", { text: s.cookies_file || "Ningún archivo elegido" });
    const fileBtn = button("outlined", "Elegir archivo…", null, async () => {
      const p = await api.pick_cookies();
      if (p) cookiesFile.textContent = p;
    });
    const rules = (mode) => { browser.select.disabled = mode !== "browser"; fileBtn.disabled = mode !== "file"; };
    const cookies = card(h("div.col", title("Cookies"),
      note("Sirven para videos con restricción de edad, privados o de miembros. La app usa la sesión de YouTube del navegador, sin pedir la contraseña. Con Chrome o Edge puede fallar si el navegador está abierto."),
      radioGroup([["none", "No usar cookies"], ["browser", "Usar las del navegador", browser],
        ["file", "Usar un archivo cookies.txt", h("div.row.grow", fileBtn, cookiesFile)]],
      s.cookies_mode, (v) => { setSetting("cookies_mode", v); rules(v); })));
    rules(s.cookies_mode);

    // Tema
    this.tiles = h("div.col", { style: { gap: "12px" } });
    const appearance = card(h("div.col", { style: { gap: "12px" } }, title("Tema"), note("Colores de la app."), this.tiles));
    this.renderTiles();

    // Avisos
    const notices = card(h("div.col", { style: { gap: "2px" } }, title("Avisos"),
      switchBox("Notificar cuando terminen todas las descargas", s.notify_queue_done, set("notify_queue_done")),
      switchBox("Notificar cada descarga terminada", s.notify_each, set("notify_each")),
      switchBox("Detectar enlaces de YouTube copiados", s.watch_clipboard, set("watch_clipboard"))));

    // Búsqueda
    const searching = card(h("div.col", title("Búsqueda"),
      note("Al buscar en la pestaña Audio, busca solo canciones en YouTube Music. Traen artista, álbum y portada bien puestos, pero la búsqueda tarda unos segundos más. Apagado, busca en YouTube normal (incluye videos musicales, en vivo, con letra…)."),
      switchBox("Buscar canciones en YouTube Music", s.music_search, set("music_search"))));

    // Portadas
    const covers = card(h("div.col", title("Portada cuadrada"),
      note("YouTube guarda las miniaturas en formato rectangular y rellena los lados de las portadas de álbum. Recortar deja solo el cuadrado del centro, como en YouTube Music. En videos con una imagen rectangular de verdad se pierden los lados."),
      radioGroup([
        ["music", "Solo canciones de YouTube Music (búsqueda o enlaces music.youtube.com)"],
        ["audio", "Todas las descargas de audio"],
        ["video", "Todas las descargas de video"],
        ["both", "Audio y video"],
        ["none", "Nunca (dejar la miniatura como viene)"],
      ], s.cover_crop, set("cover_crop"), 0)));

    // Componentes
    this.ytdlpVersion = h("div.tiny.muted", { text: "…" });
    this.ffmpegVersion = h("div.tiny.muted", { text: "…" });
    this.updateStatus = h("span.small.bold");
    this.updateBtn = button("outlined", "Buscar actualización", "refresh", () => this.updateYtdlp());
    const components = card(h("div.col", { style: { gap: "12px" } }, title("Componentes"),
      h("div.row", h("div.grow", h("div.bold", { text: "yt-dlp" }), this.ytdlpVersion), this.updateStatus, this.updateBtn),
      h("hr.divider"),
      h("div", h("div.bold", { text: "ffmpeg" }), this.ffmpegVersion),
      h("div.col", { style: { gap: "2px" } },
        switchBox("Buscar actualizaciones de yt-dlp al abrir la app", s.auto_update_ytdlp, set("auto_update_ytdlp")),
        switchBox("Avisar cuando haya una versión nueva de Onitune", s.check_app_updates, set("check_app_updates")))));

    // Acerca de
    const a = S.app;
    const about = card(h("div.col", { style: { gap: "8px" } }, title(`Acerca de ${a.name} ${a.version}`),
      h("div", { text: "Idea, diseño y dirección: angelqqi." }),
      note("El código se escribió con ayuda de inteligencia artificial (Claude, de Anthropic)."),
      note("Software libre con licencia MIT. Usa yt-dlp, FFmpeg y pywebview; sus licencias están en THIRD_PARTY_LICENSES.md."),
      note(`${a.name} no está afiliado a YouTube ni a Google. Solo se debe descargar contenido que se tenga derecho a guardar.`),
      h("div", button("text", "Ver el proyecto en GitHub", "open_in_new", () => api.open_url(a.repo)))));

    $("#view-settings").append(header("Ajustes", "Los cambios se guardan automáticamente."),
      folders, cookies, appearance, notices, searching, covers, components, about);
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
      h("div.sample", { text: "Texto de ejemplo", style: { background: p.card, color: p.muted } }),
      h("div.swatches", [p.primary, p.secondary, p.ok, p.warn, p.info, p.error].map((c) => h("i", { style: { background: c } }))));
    };
    this.tiles.replaceChildren(
      sectionLabel("Oscuros"), h("div.themes", S.themes.filter((t) => t.dark).map(tile)),
      sectionLabel("Claros"), h("div.themes", S.themes.filter((t) => !t.dark).map(tile)));
  },

  async loadVersions() {
    if (this.versionsLoaded) return;
    this.versionsLoaded = true;
    const v = await api.versions();
    this.ytdlpVersion.textContent = `versión ${v.ytdlp}`;
    this.ffmpegVersion.textContent = v.ffmpeg;
  },

  showUpdateResult(ok, message) {
    this.updateStatus.textContent = message;
    this.updateStatus.className = "small bold " + (ok ? "ok-text" : "err-text");
  },

  async updateYtdlp() {
    this.updateBtn.disabled = true;
    this.updateStatus.textContent = "Buscando…";
    this.updateStatus.className = "small bold muted";
    const r = await api.update_ytdlp();
    this.updateBtn.disabled = false;
    this.showUpdateResult(r.ok, r.message);
    this.ytdlpVersion.textContent = `versión ${r.version}`;
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
    this.retry = button("filled", "Reintentar", "refresh", () => this.run());
    this.retryRow = h("div.row", { hidden: true, style: { justifyContent: "flex-end" } }, this.retry);
    $("#setup").append(h("div.setup-box",
      h("div.setup-head", h("img", { src: S.app.icon, alt: "" }),
        h("div", h("h1", { text: "Preparando Onitune" }), h("div.muted", { text: "Primera configuración de la app. Solo ocurre una vez." }))),
      h("div.col", { style: { gap: "18px" } },
        step("yt-dlp", "Descargar yt-dlp", "El programa que habla con YouTube."),
        step("ffmpeg", "Descargar ffmpeg", "Convierte el audio y une el video con el sonido."),
        step("folders", "Crear carpetas Audio y Video", "Donde se guardarán las descargas.")),
      h("div.setup-note", { text: `Se guardan dentro de la carpeta de la app (${where}). No hace falta instalar nada ni permisos de administrador.` }),
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
  Object.assign(S, { app: state.app, settings: state.settings, themes: state.themes });
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
  go(S.view);
}

window.addEventListener("pywebviewready", () => { api = window.pywebview.api; start(); });
// Clic derecho: solo en campos de texto (copiar/pegar); con ONITUNE_DEBUG=1, en todas partes (Inspeccionar)
document.addEventListener("contextmenu", (e) => { if (!S.app.debug && !e.target.closest("input")) e.preventDefault(); });
