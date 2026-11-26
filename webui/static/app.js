"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let dict = {};
let lang = "fr";
let state = null;
let zones = {};
let currentStep = 1;
const outputTimers = {};
const AUTO_OFF_S = 300;

function t(key, vars) {
  let s = (dict[lang] && dict[lang][key]) || key;
  if (vars) Object.keys(vars).forEach((k) => { s = s.split(`{${k}}`).join(vars[k]); });
  return s;
}

const params = new URLSearchParams(location.search);

function pickLang() {
  const forced = params.get("lang");
  if (forced === "fr" || forced === "en") return forced;
  let saved = null;
  try { saved = localStorage.getItem("mothbox-lang"); } catch (e) {}
  if (saved === "fr" || saved === "en") return saved;
  return (navigator.language || "fr").toLowerCase().startsWith("fr") ? "fr" : "en";
}

function applyI18n() {
  document.documentElement.lang = lang;
  $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $("#lang-btn").textContent = lang === "fr" ? "EN" : "FR";
  buildDays();
  if (state) render();
}

function toast(msg, isError) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("error", !!isError);
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, isError ? 6000 : 3000);
}

function showError(code) {
  toast(t(`error.${code}`), true);
}

async function api(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch (e) {
    showError("network");
    throw e;
  }
  const type = res.headers.get("Content-Type") || "";
  if (type.startsWith("image/")) {
    if (!res.ok) { showError("camera_error"); throw new Error("camera_error"); }
    return res.blob();
  }
  const data = await res.json().catch(() => ({ ok: false, error: "network" }));
  if (!res.ok || data.ok === false) {
    showError(data.error || "network");
    throw new Error(data.error || "network");
  }
  return data;
}

function pad(n) { return String(n).padStart(2, "0"); }

function fmtDateTime(d) {
  return d.toLocaleString(lang === "fr" ? "fr-FR" : "en-GB", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

function fmtBoxTime(iso) {
  if (!iso) return "–";
  const [date, time] = iso.split("T");
  const [y, m, d] = date.split("-");
  return `${d}/${m}/${y} ${time.slice(0, 5)}`;
}

function describeSchedule(s) {
  if (!s || !s.weekdays.length || !s.hours.length) return "–";
  const days = s.weekdays.length === 7
    ? t("schedule.every_day")
    : s.weekdays.map((d) => t(`day.long.${d}`)).join(", ");
  const hours = s.hours.slice().sort((a, b) => a - b).map((h) => `${pad(h)}:${pad(s.minute)}`).join(", ");
  return t("schedule.summary", { days, hours, runtime: s.runtime });
}

function goTo(step) {
  currentStep = step;
  $$(".step").forEach((el) => { el.hidden = el.id !== `step-${step}`; });
  $$("#steps button").forEach((b) => {
    const n = Number(b.dataset.step);
    b.classList.toggle("active", n === step);
    b.classList.toggle("done", n < step);
  });
  window.scrollTo(0, 0);
  if (step === 3) refreshSensors();
}

function buildDays() {
  const wrap = $("#days");
  const selected = state ? state.schedule.weekdays : [];
  wrap.innerHTML = "";
  for (let d = 1; d <= 7; d++) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.dataset.value = d;
    b.textContent = t(`day.short.${d}`);
    b.title = t(`day.long.${d}`);
    b.setAttribute("aria-pressed", selected.includes(d) ? "true" : "false");
    b.addEventListener("click", () => toggleChip(b));
    wrap.appendChild(b);
  }
}

function buildHours() {
  const wrap = $("#hours");
  wrap.innerHTML = "";
  for (let h = 0; h < 24; h++) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.dataset.value = h;
    b.textContent = pad(h);
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", () => toggleChip(b));
    wrap.appendChild(b);
  }
}

function toggleChip(b) {
  b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
}

function selectedValues(wrapSel) {
  return $$(`${wrapSel} .chip`).filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => Number(b.dataset.value));
}

function setChips(wrapSel, values) {
  $$(`${wrapSel} .chip`).forEach((b) => {
    b.setAttribute("aria-pressed", values.includes(Number(b.dataset.value)) ? "true" : "false");
  });
}

function render() {
  const s = state;
  $("#box-name").textContent = s.name || "–";
  const debugOn = s.switches.Debug === "1";
  const pill = $("#debug-pill");
  pill.textContent = debugOn ? t("debug.on") : t("debug.off");
  pill.classList.toggle("off", !debugOn);

  $("#box-time").textContent = fmtBoxTime(s.box_time);

  const fromSwitches = s.source === "switches";
  $("#switch-alert").hidden = !fromSwitches;
  $("#schedule-form").disabled = fromSwitches;
  $("#switch-schedule-text").textContent = describeSchedule(s.switch_schedule);
  const active = fromSwitches ? s.switch_schedule : s.schedule;
  const next = s.next_session ? fmtDateTime(new Date(s.next_session)) : "–";
  $("#next-session").textContent = t("schedule.next", { when: next });

  $("#r-name").textContent = s.name || "–";
  $("#r-tz").textContent = s.timezone || "–";
  $("#r-schedule").textContent = describeSchedule(active);
  $("#r-next").textContent = next;

  $("#debug-on-box").hidden = !debugOn || rebooting;
  $("#debug-off-box").hidden = debugOn || rebooting;
  $("#rebooting-box").hidden = !rebooting;

  Object.keys(s.outputs).forEach((name) => setOutputUi(name, s.outputs[name]));
}

function fillForms() {
  const s = state;
  setChips("#days", s.schedule.weekdays);
  setChips("#hours", s.schedule.hours);
  $("#minute").value = s.schedule.minute;
  $("#runtime").value = s.schedule.runtime;
  $("#autoname").checked = s.autoname;
  $("#name").value = s.name || "";
  $("#name").disabled = s.autoname;
  ["bat_voltage", "bat_Wh", "bat_80perVolts", "bat_20perVolts"].forEach((k) => {
    $(`#${k}`).value = s.battery[k] == null ? "" : s.battery[k];
  });
}

async function loadState(fill) {
  try {
    state = await api("GET", "/api/state");
  } catch (e) { return; }
  render();
  if (fill) fillForms();
}

function phoneZone() {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { return ""; }
}

function fillRegions(selected) {
  const region = $("#tz-region");
  region.innerHTML = "";
  Object.keys(zones).sort().forEach((r) => {
    const o = document.createElement("option");
    o.value = r; o.textContent = r.replace(/_/g, " ");
    region.appendChild(o);
  });
  if (selected) region.value = selected;
  fillCities();
}

function fillCities(selected) {
  const city = $("#tz-city");
  city.innerHTML = "";
  (zones[$("#tz-region").value] || []).forEach((c) => {
    const o = document.createElement("option");
    o.value = c; o.textContent = c.replace(/_/g, " ").replace(/\//g, " / ");
    city.appendChild(o);
  });
  if (selected) city.value = selected;
}

function zoneKnown(tz) {
  const i = tz.indexOf("/");
  if (i < 0) return (zones.Other || []).includes(tz);
  return (zones[tz.slice(0, i)] || []).includes(tz.slice(i + 1));
}

function selectZone(tz) {
  const i = tz.indexOf("/");
  const region = i < 0 ? "Other" : tz.slice(0, i);
  const city = i < 0 ? tz : tz.slice(i + 1);
  fillRegions(region);
  fillCities(city);
}

async function initClock() {
  try { zones = await api("GET", "/api/timezones"); } catch (e) { zones = {}; }
  const tz = phoneZone();
  if (tz && zoneKnown(tz)) {
    $("#tz-detected").textContent = `${tz} ✓`;
    selectZone(tz);
  } else {
    $("#tz-detected").textContent = t("clock.not_detected");
    if (state && state.timezone && zoneKnown(state.timezone)) selectZone(state.timezone);
    else fillRegions();
  }
}

function selectedZone() {
  const r = $("#tz-region").value;
  const c = $("#tz-city").value;
  return r === "Other" ? c : `${r}/${c}`;
}

async function syncClock() {
  const btn = $("#sync-btn");
  btn.disabled = true;
  try {
    const res = await api("POST", "/api/clock", { epoch_ms: Date.now(), timezone: selectedZone() });
    const out = $("#sync-result");
    const off = Math.abs(res.offset_s);
    out.textContent = off < 2 ? t("clock.synced_ok") : t("clock.synced", { s: off });
    out.hidden = false;
    await loadState(false);
  } catch (e) {
  } finally {
    btn.disabled = false;
  }
}

async function saveSchedule() {
  const body = {
    weekdays: selectedValues("#days"),
    hours: selectedValues("#hours"),
    minute: parseInt($("#minute").value, 10),
    runtime: parseInt($("#runtime").value, 10),
  };
  if (Number.isNaN(body.minute)) body.minute = -1;
  if (Number.isNaN(body.runtime)) body.runtime = 0;
  try {
    await api("POST", "/api/schedule", body);
    toast(t("schedule.saved"));
    await loadState(true);
  } catch (e) {}
}

async function saveAdvanced() {
  const num = (id) => parseFloat($(`#${id}`).value);
  const body = {
    autoname: $("#autoname").checked,
    name: $("#name").value.trim(),
    bat_voltage: num("bat_voltage"),
    bat_Wh: num("bat_Wh"),
    bat_80perVolts: num("bat_80perVolts"),
    bat_20perVolts: num("bat_20perVolts"),
  };
  Object.keys(body).forEach((k) => { if (typeof body[k] === "number" && Number.isNaN(body[k])) body[k] = null; });
  try {
    await api("POST", "/api/advanced", body);
    toast(t("adv.saved"));
    await loadState(true);
  } catch (e) {}
}

function setOutputUi(name, on) {
  const row = $(`.toggle-row[data-output="${name}"]`);
  if (!row) return;
  row.querySelector(".switch").setAttribute("aria-pressed", on ? "true" : "false");
  if (on && !outputTimers[name]) {
    const end = Date.now() + AUTO_OFF_S * 1000;
    outputTimers[name] = setInterval(() => {
      const left = Math.max(0, Math.round((end - Date.now()) / 1000));
      row.querySelector(".countdown").textContent = `${Math.floor(left / 60)}:${pad(left % 60)}`;
      if (left === 0) loadState(false);
    }, 500);
  }
  if (!on && outputTimers[name]) {
    clearInterval(outputTimers[name]);
    delete outputTimers[name];
    row.querySelector(".countdown").textContent = "";
  }
}

async function toggleOutput(name, btn) {
  const on = btn.getAttribute("aria-pressed") !== "true";
  btn.disabled = true;
  try {
    const res = await api("POST", `/api/output/${name}`, { on });
    Object.keys(res.outputs).forEach((n) => setOutputUi(n, res.outputs[n]));
  } catch (e) {
  } finally {
    btn.disabled = false;
  }
}

async function takePhoto() {
  const btn = $("#photo-btn");
  btn.disabled = true;
  btn.textContent = t("test.photo_busy");
  try {
    const blob = await api("POST", "/api/photo");
    const img = $("#photo");
    if (img.src) URL.revokeObjectURL(img.src);
    img.src = URL.createObjectURL(blob);
    img.hidden = false;
    $("#photo-hint").hidden = false;
  } catch (e) {
  } finally {
    btn.disabled = false;
    btn.textContent = t("test.photo");
  }
}

async function refreshSensors() {
  if (currentStep !== 3 || document.hidden) return;
  let s;
  try { s = await api("GET", "/api/sensors"); } catch (e) { return; }
  $("#s-battery").textContent = s.voltage == null ? "–"
    : `${s.voltage.toFixed(1)} V${s.percent == null ? "" : ` · ${s.percent} %`}`;
  $("#s-temp").textContent = s.cpu_temp == null ? "–" : `${s.cpu_temp.toFixed(0)} °C`;
  $("#s-disk").textContent = `${s.disk_free_gb.toFixed(1)} ${t("unit.gb")}`;
  $("#s-gps").textContent = s.lat == null ? t("test.no_gps") : `${s.lat}, ${s.lon}`;
}

let rebooting = false;

async function reboot() {
  try {
    await api("POST", "/api/reboot");
    rebooting = true;
    render();
  } catch (e) {}
}

function tickPhoneTime() {
  const d = new Date();
  $("#phone-time").textContent = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function heartbeat() {
  if (document.hidden || rebooting) return;
  fetch("/api/heartbeat", { method: "POST", cache: "no-store" }).catch(() => {});
}

async function init() {
  try { dict = await (await fetch("/static/i18n.json", { cache: "no-store" })).json(); } catch (e) { dict = {}; }
  lang = pickLang();
  buildHours();
  applyI18n();

  $("#lang-btn").addEventListener("click", () => {
    lang = lang === "fr" ? "en" : "fr";
    try { localStorage.setItem("mothbox-lang", lang); } catch (e) {}
    applyI18n();
  });
  $$("#steps button").forEach((b) => b.addEventListener("click", () => goTo(Number(b.dataset.step))));
  $$("[data-goto]").forEach((b) => b.addEventListener("click", () => goTo(Number(b.dataset.goto))));
  $("#tz-region").addEventListener("change", () => fillCities());
  $("#sync-btn").addEventListener("click", syncClock);
  $("#save-schedule").addEventListener("click", saveSchedule);
  $("#save-advanced").addEventListener("click", saveAdvanced);
  $("#autoname").addEventListener("change", (e) => { $("#name").disabled = e.target.checked; });
  $$(".toggle-row").forEach((row) => {
    const btn = row.querySelector(".switch");
    btn.addEventListener("click", () => toggleOutput(row.dataset.output, btn));
  });
  $("#photo-btn").addEventListener("click", takePhoto);
  $("#reboot-btn").addEventListener("click", reboot);

  await loadState(true);
  buildDays();
  if (state) fillForms();
  await initClock();
  const start = Number(params.get("step"));
  goTo(start >= 1 && start <= 4 ? start : 1);

  tickPhoneTime();
  setInterval(tickPhoneTime, 1000);
  setInterval(heartbeat, 10000);
  heartbeat();
  setInterval(refreshSensors, 5000);
  setInterval(() => { if (!document.hidden && !rebooting) loadState(false); }, 3000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) heartbeat(); });
}

init();
