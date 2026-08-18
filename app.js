const state = {
  view: "conversation",
  data: null,
  metrics: null,
  listening: false,
  wakeArmed: true,
  ambient: false,
  speaking: false,
  bootComplete: false,
  energy: 0.34,
  audioLevel: 0,
  transcript: "",
  voices: [],
  selectedVoice: null,
  voiceProfile: "friday",
  recognition: null,
  micStream: null,
  micContext: null,
  micSource: null,
  micAnalyser: null,
  micProcessor: null,
  voiceResumeAfterSpeech: false,
  voiceFallbackActive: false,
  transcribing: false,
  finalizingVoiceCapture: false,
  recordedChunks: [],
  recordingSampleRate: 0,
  recordingStartedAt: 0,
  recordingLastVoiceAt: 0,
  recordingHeardVoice: false,
  ambientContext: null,
  ambientNodes: [],
  weather: null,
  weatherRequested: false,
  lastEventIds: new Set(),
  modelIndex: 0,
  three: null,
  renderer: null,
  scene: null,
  camera: null,
  threeGroup: null,
  threeOrb: null,
  lastVoiceDispatchAt: 0,
  reducedMotion: window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches || false,
  particleCtx: null,
  particles: [],
  mouseX: 0,
  mouseY: 0,
  currentProtocol: "core",
  allProtocols: {},
  audioCtx: null,
  voiceEngineReady: false,
};

const QUICK_COMMANDS = [
  { title: "Natural command", text: "Open browser and search the internet for Friday voice tech", detail: "Try a multi-step command." },
  { title: "Search web", text: "Search the internet for the latest FRIDAY voice tech", detail: "Open a browser search." },
  { title: "Open web app", text: "Open YouTube", detail: "Launch an approved web link." },
  { title: "Power down", text: "Power down", detail: "Put the HUD in standby." },
  { title: "Start timer", text: "Start timer for 5 minutes", detail: "Set a quick countdown." },
  { title: "Screenshot", text: "Take a screenshot", detail: "Capture the desktop." },
  { title: "Download MP4", text: "Download MP4 from https://example.com/video.mp4", detail: "Direct-link downloader." },
  { title: "Add note", text: "Note: cinematic HUD layout", detail: "Store a memory entry." },
  { title: "Security mode", text: "Security mode shield", detail: "Tighten FRIDAY controls." },
  { title: "Call contact", text: "Call Kenan on 5551234", detail: "Launch a phone action." },
  { title: "Summarize file", text: "Summarize file C:\\\\Users\\\\forho\\\\Documents\\\\report.txt", detail: "Read a document." },
  { title: "Switch model", text: "Use model gpt-4o", detail: "Change the active model." },
  { title: "Clear memory", text: "Clear memory", detail: "Reset notes, tasks, and history." },
];

const VOICE_PROFILES = {
  friday:   { rate: 0.88, pitch: 1.18, volume: 1.0, label: "F.R.I.D.A.Y." },
  cinematic:{ rate: 0.92, pitch: 1.12, volume: 1.0, label: "Cinematic" },
  natural:  { rate: 1.00, pitch: 1.00, volume: 1.0, label: "Natural" },
  fast:     { rate: 1.15, pitch: 1.05, volume: 1.0, label: "Fast" },
  jarvis:   { rate: 0.85, pitch: 0.95, volume: 1.0, label: "J.A.R.V.I.S." },
};

// Voice names that sound closest to Friday (Kerry Condon / Irish-British female)
const VOICE_PRIORITY = [
  "Samantha", "Victoria", "Karen", "Moira", "Tessa",
  "Google UK English Female", "Microsoft Hazel",
  "Google US English Female", "Microsoft Zira",
  "Microsoft Catherine", "Google Translate English",
  "en-GB", "en-AU", "en-IE", "en-US"
];

const els = {
  boot: id("boot"),
  bootLog: id("bootLog"),
  bootBar: id("bootBar"),
  shell: id("shell"),
  leftTabs: id("leftTabs"),
  leftPanel: id("leftPanel"),
  rightPanel: id("rightPanel"),
  commandInput: id("commandInput"),
  sendBtn: id("sendBtn"),
  voiceBtn: id("voiceBtn"),
  wakeBtn: id("wakeBtn"),
  ambientBtn: id("ambientBtn"),
  fullBtn: id("fullBtn"),
  clearBtn: id("clearBtn"),
  cloudChip: id("cloudChip"),
  modelChip: id("modelChip"),
  protocolChip: id("protocolChip"),
  wakeChip: id("wakeChip"),
  ownerChip: id("ownerChip"),
  voiceChip: id("voiceChip"),
  listenChip: id("listenChip"),
  telemetryChip: id("telemetryChip"),
  memoryChip: id("memoryChip"),
  powerChip: id("powerChip"),
  securityChip: id("securityChip"),
  timeChip: id("timeChip"),
  statusLine: id("statusLine"),
  subLine: id("subLine"),
  transcriptLine: id("transcriptLine"),
  memorySummary: id("memorySummary"),
  metricsSummary: id("metricsSummary"),
  voiceSummary: id("voiceSummary"),
  quickSummary: id("quickSummary"),
  dashboardStatus: id("dashboardStatus"),
  dashboardSummary: id("dashboardSummary"),
  dashboardTelemetry: id("dashboardTelemetry"),
  dashboardModel: id("dashboardModel"),
  dashboardMemory: id("dashboardMemory"),
  dashboardProtocol: id("dashboardProtocol"),
  dashboardVoice: id("dashboardVoice"),
  dashboardWake: id("dashboardWake"),
  dashboardTime: id("dashboardTime"),
  dashboardWeather: id("dashboardWeather"),
  toastStack: id("toastStack"),
  waveCanvas: id("waveCanvas"),
  threeStage: id("threeStage"),
  protocolBtn: document.getElementById("protocolBtn"),
  protocolMenu: document.getElementById("protocolMenu"),
  voiceProfileBtn: document.getElementById("voiceProfileBtn"),
  voiceProfileMenu: document.getElementById("voiceProfileMenu"),
};

const MODEL_ORDER = [
  "gemini-2.5-flash",
  "gemini-2.5-pro"
];

function id(name) { return document.getElementById(name); }
function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

function computeRms(samples) {
  if (!samples || !samples.length) return 0;
  let total = 0;
  for (let i = 0; i < samples.length; i++) total += samples[i] * samples[i];
  return Math.sqrt(total / samples.length);
}

function concatFloat32Arrays(chunks) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) { output.set(chunk, offset); offset += chunk.length; }
  return output;
}

function encodeWavBuffer(samples, sampleRate) {
  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);
  const writeString = (offset, value) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeString(8, "WAVE"); writeString(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true); view.setUint16(34, 16, true);
  writeString(36, "data"); view.setUint32(40, samples.length * bytesPerSample, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const value = clamp(samples[i], -1, 1);
    view.setInt16(offset, value < 0 ? value * 0x8000 : value * 0x7fff, true);
    offset += bytesPerSample;
  }
  return buffer;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const slice = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...slice);
  }
  return btoa(binary);
}

function escapeHtml(text) {
  return String(text ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

async function apiGet(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`GET ${path} failed`);
  return response.json();
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error || data.message || `POST ${path} failed`;
    throw new Error(error);
  }
  return data;
}

function setEnergy(value) {
  state.energy = clamp(value, 0.12, 1);
  document.documentElement.style.setProperty("--energy", state.energy.toFixed(2));
}

function setFridayMode(mode) {
  document.body.setAttribute("data-friday-mode", mode);
  if (mode === "listening") setEnergy(0.85);
  else if (mode === "speaking") setEnergy(0.65);
  else if (mode === "thinking") setEnergy(0.5);
  else setEnergy(0.34);
}

function setBootProgress(percent) {
  document.documentElement.style.setProperty("--boot-progress", `${percent}%`);
  if (els.bootBar) els.bootBar.style.width = `${percent}%`;
}

function showToast(title, message, type = "info") {
  if (!els.toastStack) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>`;
  els.toastStack.prepend(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(16px) scale(0.95)";
    setTimeout(() => toast.remove(), 300);
  }, 3800);
}

function showError(message) {
  showToast("Error", message, "error");
  const orb = document.querySelector(".orb-panel");
  if (orb) { orb.classList.add("error-shake"); setTimeout(() => orb.classList.remove("error-shake"), 600); }
}

function showSuccess(title, message) {
  showToast(title, message, "success");
}

function formatClock(date = new Date()) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDate(date = new Date()) {
  return date.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

function formatBytes(mb) {
  if (mb === null || mb === undefined) return "—";
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb.toFixed(1)} MB`;
}

function formatMetricPercent(value) {
  if (value === null || value === undefined) return "—";
  return `${Math.round(Number(value))}%`;
}

function currentState() { return state.data || {}; }
function memorySummary() { return currentState().memory_summary || "No stored memory yet."; }

function updateChips() {
  const data = currentState();
  const cloud = data.cloud_ready ? "Cloud ready" : "Cloud offline";
  els.cloudChip.textContent = cloud;
  els.modelChip.textContent = data.model || "gpt-5";
  if (els.dashboardModel) els.dashboardModel.textContent = data.model || "gpt-5";
  const proto = data.protocol || state.allProtocols[state.currentProtocol];
  const protoName = proto?.name || state.currentProtocol || "Core";
  if (els.protocolChip) els.protocolChip.textContent = `${protoName} Protocol`;
  if (els.dashboardProtocol) els.dashboardProtocol.textContent = `${protoName} Protocol`;
  els.wakeChip.textContent = state.wakeArmed ? "FRIDAY" : "Direct";
  const ownerName = data.owner_name || data.owner_profile?.name || "Kenan Novruzov";
  const ownerTitle = data.owner_title || data.owner_profile?.title || "Boss";
  if (els.ownerChip) els.ownerChip.textContent = `${ownerTitle}: ${ownerName}`;
  els.voiceChip.textContent = state.speaking ? "Speaking" : state.listening ? "Listening" : "Voice idle";
  els.listenChip.textContent = state.wakeArmed ? "Wake word armed" : "Direct capture";
  els.telemetryChip.textContent = "Telemetry live";
  const notesCount = (data.notes || []).length;
  const tasksCount = (data.tasks || []).length;
  els.memoryChip.textContent = `${notesCount} notes`;
  if (els.powerChip) els.powerChip.textContent = `Power ${data.power_state || "online"}`;
  if (els.securityChip) els.securityChip.textContent = `Security ${data.security_mode || "normal"}`;
  els.timeChip.textContent = formatClock();
  els.memorySummary.textContent = memorySummary();
  els.metricsSummary.textContent = summarizeMetrics(state.metrics);
  els.voiceSummary.textContent = voiceSummaryText();
  els.quickSummary.textContent = "Private command center for voice, memory, telemetry, web search, timers, screenshots, and safe device actions.";
  const statusText = state.speaking ? "FRIDAY is speaking." : state.listening ? "FRIDAY is listening." : "FRIDAY online.";
  const summaryText = `${ownerTitle}: ${ownerName} • ${state.wakeArmed ? "Wake enabled" : "Direct capture"} • ${notesCount} notes`;
  els.statusLine.textContent = statusText;
  els.subLine.textContent = memorySummary();
  if (els.dashboardStatus) els.dashboardStatus.textContent = statusText;
  if (els.dashboardSummary) els.dashboardSummary.textContent = summaryText;
  if (els.dashboardTelemetry) els.dashboardTelemetry.textContent = summarizeMetrics(state.metrics);
  if (els.dashboardMemory) els.dashboardMemory.textContent = `${notesCount} notes • ${tasksCount} tasks`;
  if (els.dashboardVoice) {
    const profile = VOICE_PROFILES[state.voiceProfile] || VOICE_PROFILES.friday;
    const voiceName = state.selectedVoice ? state.selectedVoice.name : profile.label;
    els.dashboardVoice.textContent = `${voiceName} • ${state.listening ? "armed" : "ready"}`;
  }
  if (els.dashboardWake) els.dashboardWake.textContent = state.wakeArmed ? "Wake word armed" : "Direct capture";
  if (els.dashboardTime) els.dashboardTime.textContent = formatClock();
  if (els.dashboardWeather) {
    const weatherSummary = state.weather
      ? (state.weather.condition || state.weather.summary || (state.weather.temperature !== undefined ? `${formatNumber(state.weather.temperature)}°` : "Weather online"))
      : "Weather unavailable";
    els.dashboardWeather.textContent = weatherSummary;
  }
}

function summarizeMetrics(metrics) {
  if (!metrics) return "Telemetry is warming up.";
  const parts = [];
  if (metrics.cpu_percent !== null && metrics.cpu_percent !== undefined) parts.push(`CPU ${formatMetricPercent(metrics.cpu_percent)}`);
  const ram = metrics.ram || {};
  if (ram.used_gb !== null && ram.total_gb !== null && ram.used_gb !== undefined && ram.total_gb !== undefined) {
    parts.push(`RAM ${formatNumber(ram.used_gb)} / ${formatNumber(ram.total_gb)} GB`);
  }
  const gpu = metrics.gpu || {};
  if (gpu.name) parts.push(gpu.utilization !== null && gpu.utilization !== undefined ? `GPU ${gpu.name} ${formatMetricPercent(gpu.utilization)}` : `GPU ${gpu.name}`);
  const battery = metrics.battery || {};
  if (battery.percent !== null && battery.percent !== undefined) parts.push(`Battery ${formatMetricPercent(battery.percent)}`);
  const network = metrics.network || {};
  if (network.name) parts.push(`Network ${network.name}`);
  return parts.join(" • ") || "Telemetry is warming up.";
}

function voiceSummaryText() {
  if (!("speechSynthesis" in window)) return "Speech synthesis unavailable in this browser.";
  const profile = VOICE_PROFILES[state.voiceProfile] || VOICE_PROFILES.friday;
  const ownerName = currentState().owner_name || currentState().owner_profile?.name || "Kenan Novruzov";
  const voice = state.selectedVoice ? `Voice: ${state.selectedVoice.name}` : "Browser voice ready.";
  const capture = state.listening ? (state.transcribing ? "Transcribing microphone input." : "Microphone capture armed.") : "Microphone capture ready.";
  return `${voice} | Profile: ${profile.label} | ${capture} Boss: ${ownerName}.`;
}

function eventLabel(item) {
  return `${item.kind || "event"} • ${new Date(item.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  const bigint = parseInt(clean, 16);
  return `${(bigint >> 16) & 255}, ${(bigint >> 8) & 255}, ${bigint & 255}`;
}

function applyProtocolColors(colors) {
  if (!colors) return;
  const primary = colors.primary || "#59e6ff";
  const secondary = colors.secondary || "#378dff";
  const root = document.documentElement;
  root.style.setProperty("--cyan", primary);
  root.style.setProperty("--cyan-rgb", hexToRgb(primary));
  root.style.setProperty("--blue", secondary);
  root.style.setProperty("--blue-rgb", hexToRgb(secondary));
  if (state.threeOrb && state.threeScene) {
    try {
      state.threeOrb.material.color.set(primary);
      state.threeScene.ring.material.color.set(secondary);
      state.threeScene.points.material.color.set(primary);
    } catch { /* ignore */ }
  }
}

async function loadProtocol() {
  try {
    const data = await apiGet("/api/protocol");
    if (data.protocols) state.allProtocols = data.protocols;
    if (data.current) state.currentProtocol = data.current;
    if (data.protocol && data.protocol.colors) applyProtocolColors(data.protocol.colors);
    updateChips();
    updateProtocolMenuHighlight();
  } catch (err) { console.warn("Protocol load failed:", err); }
}

function updateProtocolMenuHighlight() {
  if (!els.protocolMenu) return;
  els.protocolMenu.querySelectorAll("button[data-protocol]").forEach(btn => {
    btn.classList.toggle("active-protocol", btn.dataset.protocol === state.currentProtocol);
  });
}

async function switchProtocol(name) {
  try {
    const data = await apiPost("/api/protocol", { protocol: name });
    if (data.ok && data.protocol) {
      state.currentProtocol = data.current;
      if (data.protocol.colors) applyProtocolColors(data.protocol.colors);
      const protoName = data.protocol.name || data.current;
      showSuccess("Protocol", `${protoName} protocol engaged.`);
      updateChips();
      updateProtocolMenuHighlight();
      const protocolVoice = data.protocol.voice || `${protoName} protocol engaged.`;
      updateTranscript(protocolVoice, false);
      finalizeSpeech(protocolVoice, { mood: { tone: "neutral", rate: 0.95, pitch: 0.86, volume: 1 } });
    } else {
      showError("Failed to switch protocol.");
    }
  } catch (err) { showError(err instanceof Error ? err.message : "Protocol switch failed."); }
}

/* ════════════════════════════════════════
   CINEMATIC VOICE ENGINE
   ════════════════════════════════════════ */

function initAudioContext() {
  if (state.audioCtx) return;
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    state.audioCtx = new AudioContext();
    state.voiceEngineReady = true;
  } catch (e) {
    console.warn("Web Audio API not available");
  }
}

function resumeAudioContext() {
  if (state.audioCtx && state.audioCtx.state === "suspended") {
    state.audioCtx.resume();
  }
}

// ─── Activation Chirp (Iron Man style boot-up sound) ───
function playActivationChirp() {
  if (!state.audioCtx || state.reducedMotion) return;
  resumeAudioContext();
  const ctx = state.audioCtx;
  const now = ctx.currentTime;

  // High-tech chirp: two-tone sweep
  const osc1 = ctx.createOscillator();
  const osc2 = ctx.createOscillator();
  const gain = ctx.createGain();
  const filter = ctx.createBiquadFilter();

  filter.type = "bandpass";
  filter.frequency.value = 3000;
  filter.Q.value = 5;

  osc1.type = "sine";
  osc1.frequency.setValueAtTime(1200, now);
  osc1.frequency.exponentialRampToValueAtTime(2400, now + 0.08);
  osc1.frequency.exponentialRampToValueAtTime(1800, now + 0.15);

  osc2.type = "sine";
  osc2.frequency.setValueAtTime(1800, now);
  osc2.frequency.exponentialRampToValueAtTime(3600, now + 0.1);
  osc2.frequency.exponentialRampToValueAtTime(2400, now + 0.18);

  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(0.08, now + 0.03);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

  osc1.connect(filter);
  osc2.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);

  osc1.start(now);
  osc2.start(now);
  osc1.stop(now + 0.3);
  osc2.stop(now + 0.3);
}

// ─── Deactivation Chirp ───
function playDeactivationChirp() {
  if (!state.audioCtx || state.reducedMotion) return;
  resumeAudioContext();
  const ctx = state.audioCtx;
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = "sine";
  osc.frequency.setValueAtTime(2000, now);
  osc.frequency.exponentialRampToValueAtTime(800, now + 0.2);

  gain.gain.setValueAtTime(0.06, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(now);
  osc.stop(now + 0.3);
}

// ─── Ambient drone when speaking ───
let droneOsc = null;
let droneGain = null;

function startDrone() {
  if (!state.audioCtx || state.reducedMotion) return;
  resumeAudioContext();
  if (droneOsc) return;

  const ctx = state.audioCtx;
  droneOsc = ctx.createOscillator();
  droneGain = ctx.createGain();
  const filter = ctx.createBiquadFilter();

  droneOsc.type = "sine";
  droneOsc.frequency.value = 80;
  filter.type = "lowpass";
  filter.frequency.value = 200;

  droneGain.gain.setValueAtTime(0, ctx.currentTime);
  droneGain.gain.linearRampToValueAtTime(0.025, ctx.currentTime + 0.5);

  droneOsc.connect(filter);
  filter.connect(droneGain);
  droneGain.connect(ctx.destination);
  droneOsc.start();
}

function stopDrone() {
  if (!droneOsc || !droneGain || !state.audioCtx) return;
  const ctx = state.audioCtx;
  droneGain.gain.cancelScheduledValues(ctx.currentTime);
  droneGain.gain.setValueAtTime(droneGain.gain.value, ctx.currentTime);
  droneGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
  setTimeout(() => {
    if (droneOsc) { try { droneOsc.stop(); } catch {} droneOsc = null; }
    droneGain = null;
  }, 450);
}

// ─── Smart Voice Selection ───
function scoreVoice(voice) {
  let score = 0;
  const name = voice.name.toLowerCase();
  const lang = voice.lang.toLowerCase();

  // Prefer female voices
  if (name.includes("female")) score += 20;
  if (name.includes("zira") || name.includes("hazel") || name.includes("samantha") ||
      name.includes("victoria") || name.includes("karen") || name.includes("moira") ||
      name.includes("tessa") || name.includes("catherine")) score += 30;

  // Prefer British / Irish / Australian English (closer to Kerry Condon)
  if (lang.includes("en-gb") || lang.includes("en-ie") || lang.includes("en-au")) score += 15;
  if (name.includes("uk") || name.includes("british") || name.includes("english")) score += 10;

  // Deprioritize male voices and low-quality voices
  if (name.includes("male")) score -= 15;
  if (name.includes("microsoft") && !name.includes("zira") && !name.includes("hazel")) score -= 5;

  // Google voices are usually high quality
  if (name.includes("google")) score += 8;

  // Prefer local voices (lower latency)
  if (voice.localService) score += 5;

  return score;
}

function selectBestVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  state.voices = voices;

  // Try exact name matches first
  for (const preferred of VOICE_PRIORITY) {
    const match = voices.find(v => v.name.toLowerCase().includes(preferred.toLowerCase()));
    if (match) { state.selectedVoice = match; return match; }
  }

  // Fallback to scoring
  const scored = voices.map(v => ({ voice: v, score: scoreVoice(v) }));
  scored.sort((a, b) => b.score - a.score);

  state.selectedVoice = scored[0]?.voice || voices[0];
  return state.selectedVoice;
}

// ─── Enhanced Speech with Voice Profile ───
function finalizeSpeech(text, options) {
  if (!("speechSynthesis" in window)) return;

  // Init audio context on first speech (user gesture required)
  initAudioContext();
  resumeAudioContext();

  window.speechSynthesis.cancel();

  const profile = VOICE_PROFILES[state.voiceProfile] || VOICE_PROFILES.friday;
  const utterance = new SpeechSynthesisUtterance(text);

  utterance.rate = options?.mood?.rate ?? profile.rate;
  utterance.pitch = options?.mood?.pitch ?? profile.pitch;
  utterance.volume = options?.mood?.volume ?? profile.volume;

  if (state.selectedVoice) utterance.voice = state.selectedVoice;

  // Add slight pauses for punctuation (cinematic cadence)
  const enhancedText = text
    .replace(/\./g, ". ")
    .replace(/\,/g, ", ")
    .replace(/\?/g, "? ")
    .replace(/\!/g, "! ");

  utterance.onstart = () => {
    state.speaking = true;
    setFridayMode("speaking");
    updateChips();
    playActivationChirp();
    startDrone();
  };

  utterance.onend = () => {
    state.speaking = false;
    setFridayMode("idle");
    updateChips();
    playDeactivationChirp();
    stopDrone();
  };

  utterance.onerror = (e) => {
    if (e.error !== "canceled") {
      state.speaking = false;
      setFridayMode("idle");
      updateChips();
      stopDrone();
    }
  };

  window.speechSynthesis.speak(utterance);
}

function setVoiceProfile(profileKey) {
  if (!VOICE_PROFILES[profileKey]) return;
  state.voiceProfile = profileKey;
  updateChips();
  showSuccess("Voice Profile", `Switched to ${VOICE_PROFILES[profileKey].label} mode.`);

  // Demo the new voice
  const demoText = profileKey === "friday" 
    ? "Voice profile updated. Ready to assist you, Boss."
    : profileKey === "jarvis"
    ? "Voice profile updated. At your service, sir."
    : "Voice profile updated.";
  finalizeSpeech(demoText);
}

function updateVoiceProfileMenu() {
  if (!els.voiceProfileMenu) return;
  els.voiceProfileMenu.querySelectorAll("button[data-profile]").forEach(btn => {
    btn.classList.toggle("active-profile", btn.dataset.profile === state.voiceProfile);
  });
}

/* ════════════════════════════════════════
   PARTICLES & VISUALS
   ════════════════════════════════════════ */

function initParticles() {
  const canvas = document.createElement("canvas");
  canvas.className = "particle-canvas";
  const shell = document.querySelector(".orb-shell");
  if (!shell || state.reducedMotion) return;
  shell.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  state.particleCtx = ctx;

  function resize() {
    const rect = shell.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
  }
  resize();
  window.addEventListener("resize", resize);

  const particleCount = 40;
  state.particles = [];
  for (let i = 0; i < particleCount; i++) {
    state.particles.push({
      x: Math.random() * canvas.width, y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 2 + 0.5, opacity: Math.random() * 0.5 + 0.1,
      pulse: Math.random() * Math.PI * 2,
    });
  }

  function animate() {
    if (!state.particleCtx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const energy = state.energy;
    const rgb = getComputedStyle(document.documentElement).getPropertyValue("--cyan-rgb").trim() || "89, 230, 255";

    state.particles.forEach((p, i) => {
      p.x += p.vx * (1 + energy); p.y += p.vy * (1 + energy);
      p.pulse += 0.02 + energy * 0.03;
      if (p.x < 0) p.x = canvas.width; if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height; if (p.y > canvas.height) p.y = 0;

      const pulseOpacity = p.opacity * (0.7 + 0.3 * Math.sin(p.pulse));
      const size = p.size * (1 + energy * 0.5);
      ctx.beginPath(); ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb}, ${pulseOpacity})`; ctx.fill();

      for (let j = i + 1; j < state.particles.length; j++) {
        const p2 = state.particles[j];
        const dx = p.x - p2.x, dy = p.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 80 * energy + 40) {
          ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(${rgb}, ${0.08 * energy})`; ctx.lineWidth = 0.5; ctx.stroke();
        }
      }
    });
    requestAnimationFrame(animate);
  }
  animate();
}

function initMouseParallax() {
  if (state.reducedMotion) return;
  document.addEventListener("mousemove", (e) => {
    state.mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    state.mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    const orbShell = document.querySelector(".orb-shell");
    if (orbShell) {
      orbShell.style.transform = `perspective(1000px) rotateY(${state.mouseX * 2.4}deg) rotateX(${-state.mouseY * 2.4}deg)`;
    }
  });
}

function initMagneticButtons() {
  if (window.matchMedia("(pointer: coarse)").matches) return;
  document.querySelectorAll("button").forEach(btn => {
    btn.classList.add("magnetic");
    btn.addEventListener("mousemove", (e) => {
      const rect = btn.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      btn.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px) translateY(-2px) scale(1.03)`;
    });
    btn.addEventListener("mouseleave", () => { btn.style.transform = ""; });
  });
}

/* ════════════════════════════════════════
   RENDER FUNCTIONS
   ════════════════════════════════════════ */

function renderLeftPanel() {
  const data = currentState();
  const view = state.view;
  const notes = data.notes || [];
  const tasks = data.tasks || [];
  const history = data.history || [];
  const events = data.events || [];

  if (view === "commands") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Quick Commands</div>
        <div class="command-grid">
          ${QUICK_COMMANDS.map((item) => `
            <button class="command-card" type="button" data-command="${escapeHtml(item.text)}">
              <strong>${escapeHtml(item.title)}</strong>
              <span>${escapeHtml(item.detail)}</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
    return;
  }

  if (view === "notes") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Notes</div>
        ${notes.length ? notes.map((item) => `
          <article class="card message-card">
            <div class="message-role">Note</div>
            <div class="message-text">${escapeHtml(item.text)}</div>
            <div class="message-time">${escapeHtml(new Date(item.created_at).toLocaleString())}</div>
          </article>
        `).join("") : '<div class="empty-state">No notes stored yet. Ask FRIDAY to remember something and it will live here.</div>'}
      </div>
    `;
    return;
  }

  if (view === "tasks") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Tasks</div>
        ${tasks.length ? tasks.map((item) => `
          <label class="card task-row ${item.done ? "done" : ""}">
            <input type="checkbox" data-task-id="${escapeHtml(item.id)}" ${item.done ? "checked" : ""}>
            <span class="message-text">${escapeHtml(item.text)}</span>
            <span class="message-time">${escapeHtml(new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</span>
          </label>
        `).join("") : '<div class="empty-state">No tasks active right now. Say "task ..." to create one and FRIDAY will track it.</div>'}
      </div>
    `;
    return;
  }

  if (view === "history") {
    els.leftPanel.innerHTML = `
      <div class="stack">
        <div class="stack-title">Timeline</div>
        ${events.length ? events.slice().reverse().map((item) => `
          <article class="card event-row">
            <strong>${escapeHtml(item.text)}</strong>
            <span class="meta-row">${escapeHtml(eventLabel(item))}</span>
          </article>
        `).join("") : '<div class="empty-state">No events recorded yet. FRIDAY will surface updates here as they happen.</div>'}
      </div>
    `;
    return;
  }

  els.leftPanel.innerHTML = `
    <div class="stack">
      <div class="stack-title">Live Conversation</div>
      ${history.length ? history.map((item) => `
        <article class="card message-card ${item.role === "user" ? "user" : "friday"}">
          <div class="message-role">${escapeHtml(item.role === "user" ? "You" : "FRIDAY")}</div>
          <div class="message-text">${escapeHtml(item.text)}</div>
          <div class="message-time">${escapeHtml(new Date(item.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</div>
        </article>
      `).join("") : '<div class="empty-state">The channel is clear. Say something and FRIDAY will answer here.</div>'}
    </div>
  `;
  requestAnimationFrame(() => { els.leftPanel.scrollTop = els.leftPanel.scrollHeight; });
}

function renderRightPanel() {
  const metrics = state.metrics || {};
  const data = currentState();
  const ram = metrics.ram || {};
  const battery = metrics.battery || {};
  const gpu = metrics.gpu || {};
  const network = metrics.network || {};
  const vision = data.camera_status || {};
  const uptime = metrics.uptime || "—";
  const ramUsedText = ram.used_gb !== undefined && ram.total_gb !== undefined
    ? `${formatNumber(ram.used_gb)} / ${formatNumber(ram.total_gb)} GB` : "—";
  const ramPercent = ram.used_gb !== undefined && ram.total_gb ? Math.round((ram.used_gb / ram.total_gb) * 100) : 0;
  const batteryPercent = battery.percent ?? 0;
  const gpuUtil = gpu.utilization ?? 0;
  const networkName = network.name || "Offline";
  const cameraStatus = vision.status || "Inactive";
  const weatherSummary = state.weather
    ? (state.weather.condition || state.weather.summary || (state.weather.temperature !== undefined ? `${formatNumber(state.weather.temperature)}°` : "Unknown"))
    : "Unknown";

  els.rightPanel.innerHTML = `
    <div class="stack">
      <div class="stack-title">Telemetry Snapshot</div>
      <div class="metric-grid">
        <article class="card metric-card">
          <strong>CPU</strong>
          <span>${formatMetricPercent(metrics.cpu_percent)}</span>
          <div class="metric-value">${formatMetricPercent(metrics.cpu_percent)}</div>
          <div class="metric-bar"><span style="--metric-width:${metrics.cpu_percent ?? 0}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>RAM</strong>
          <span>${ramUsedText}</span>
          <div class="metric-value">${ramUsedText}</div>
          <div class="metric-bar"><span style="--metric-width:${ramPercent}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>Battery</strong>
          <span>${battery.percent !== undefined ? formatMetricPercent(battery.percent) : "—"}</span>
          <div class="metric-value">${battery.percent !== undefined ? formatMetricPercent(battery.percent) : "—"}</div>
          <div class="metric-bar"><span style="--metric-width:${batteryPercent}%"></span></div>
        </article>
      </div>
      <div class="metric-grid">
        <article class="card metric-card">
          <strong>GPU</strong>
          <span>${gpu.name || "Unknown"}</span>
          <div class="metric-value">${gpu.utilization !== undefined ? formatMetricPercent(gpu.utilization) : "—"}</div>
          <div class="metric-bar"><span style="--metric-width:${gpuUtil}%"></span></div>
        </article>
        <article class="card metric-card">
          <strong>Network</strong>
          <span>${escapeHtml(networkName)}</span>
          <div class="metric-value">${escapeHtml(networkName)}</div>
        </article>
        <article class="card metric-card">
          <strong>Camera</strong>
          <span>${escapeHtml(cameraStatus)}</span>
          <div class="metric-value">${escapeHtml(cameraStatus)}</div>
        </article>
      </div>
      <div class="metric-grid">
        <article class="card metric-card">
          <strong>Uptime</strong>
          <span>${escapeHtml(uptime)}</span>
        </article>
        <article class="card metric-card">
          <strong>Weather</strong>
          <span>${escapeHtml(weatherSummary)}</span>
        </article>
      </div>
    </div>
  `;
}

/* ════════════════════════════════════════
   AUDIO WAVE VISUALIZATION
   ════════════════════════════════════════ */

function drawWaveform() {
  const canvas = els.waveCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  const width = rect.width, height = rect.height, centerY = height / 2;
  let time = 0;

  function draw() {
    ctx.clearRect(0, 0, width, height);
    const energy = state.energy;
    const rgb = getComputedStyle(document.documentElement).getPropertyValue("--cyan-rgb").trim() || "89, 230, 255";

    if (state.listening || state.speaking || energy > 0.5) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${rgb}, ${0.3 + energy * 0.4})`;
      ctx.lineWidth = 2;
      for (let x = 0; x < width; x += 2) {
        const nx = x / width;
        const wave1 = Math.sin(nx * Math.PI * 8 + time) * (energy * 20);
        const wave2 = Math.sin(nx * Math.PI * 14 + time * 1.5) * (energy * 12);
        const wave3 = Math.sin(nx * Math.PI * 4 + time * 0.7) * (energy * 8);
        const y = centerY + wave1 + wave2 + wave3;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();

      ctx.beginPath();
      ctx.strokeStyle = `rgba(${rgb}, ${0.15 + energy * 0.2})`;
      ctx.lineWidth = 1.5;
      for (let x = 0; x < width; x += 2) {
        const nx = x / width;
        const wave1 = Math.sin(nx * Math.PI * 6 + time + 1) * (energy * 15);
        const wave2 = Math.sin(nx * Math.PI * 10 + time * 1.2) * (energy * 10);
        const y = centerY - wave1 - wave2;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    time += 0.05 + energy * 0.08;
    requestAnimationFrame(draw);
  }
  draw();
}

/* ════════════════════════════════════════
   BOOT SEQUENCE
   ════════════════════════════════════════ */

async function runBootSequence() {
  const logs = [
    "Initializing FRIDAY core systems...",
    "Loading neural interface modules...",
    "Calibrating optical sensors...",
    "Syncing memory banks...",
    "Establishing secure connection...",
    "Loading protocol definitions...",
    "Voice synthesis engine ready...",
    "Telemetry systems online...",
    "Wake word detection armed...",
    "Boss profile loaded: Kenan Novruzov",
    "FRIDAY is online.",
  ];

  for (let i = 0; i < logs.length; i++) {
    const line = document.createElement("div");
    line.className = "boot-line";
    line.style.animationDelay = "0ms";
    line.textContent = logs[i];
    els.bootLog.appendChild(line);
    setBootProgress(Math.round(((i + 1) / logs.length) * 100));
    await sleep(180 + Math.random() * 150);
  }

  await sleep(400);
  els.boot.classList.add("hidden");
  document.body.classList.add("ready");
  state.bootComplete = true;

  initParticles();
  initMouseParallax();
  setTimeout(initMagneticButtons, 500);
  drawWaveform();

  // Init voice engine after boot (needs user interaction, but we'll prepare it)
  initAudioContext();
}

/* ════════════════════════════════════════
   EVENT LISTENERS
   ════════════════════════════════════════ */

function initEventListeners() {
  // Tab switching
  els.leftTabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab) return;
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    state.view = tab.dataset.view;
    els.leftPanel.style.opacity = "0";
    els.leftPanel.style.transform = "translateX(-10px)";
    setTimeout(() => {
      renderLeftPanel();
      els.leftPanel.style.transition = "opacity 300ms ease, transform 300ms ease";
      els.leftPanel.style.opacity = "1";
      els.leftPanel.style.transform = "translateX(0)";
    }, 150);
  });

  // Command input
  els.commandInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); sendMessage(); }
  });
  els.sendBtn.addEventListener("click", sendMessage);

  // Voice button
  els.voiceBtn.addEventListener("click", () => {
    initAudioContext();
    resumeAudioContext();
    toggleVoice();
  });

  // Protocol menu
  if (els.protocolBtn && els.protocolMenu) {
    els.protocolBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      els.protocolMenu.classList.toggle("hidden");
    });
    els.protocolMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      const btn = e.target.closest("button[data-protocol]");
      if (!btn) return;
      switchProtocol(btn.dataset.protocol);
      els.protocolMenu.classList.add("hidden");
    });
    document.addEventListener("click", (e) => {
      if (!els.protocolMenu.contains(e.target) && e.target !== els.protocolBtn)
        els.protocolMenu.classList.add("hidden");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") els.protocolMenu.classList.add("hidden");
    });
  }

  // Voice Profile menu
  if (els.voiceProfileBtn && els.voiceProfileMenu) {
    els.voiceProfileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      initAudioContext();
      resumeAudioContext();
      els.voiceProfileMenu.classList.toggle("hidden");
    });
    els.voiceProfileMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      const btn = e.target.closest("button[data-profile]");
      if (!btn) return;
      setVoiceProfile(btn.dataset.profile);
      els.voiceProfileMenu.classList.add("hidden");
    });
    document.addEventListener("click", (e) => {
      if (!els.voiceProfileMenu.contains(e.target) && e.target !== els.voiceProfileBtn)
        els.voiceProfileMenu.classList.add("hidden");
    });
  }

  // Wake button
  els.wakeBtn.addEventListener("click", () => {
    state.wakeArmed = !state.wakeArmed;
    updateChips();
    showToast("Wake Word", state.wakeArmed ? "Wake word armed." : "Direct capture mode.");
  });

  // Fullscreen
  els.fullBtn.addEventListener("click", () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {});
    else document.exitFullscreen();
  });

  // Clear
  els.clearBtn.addEventListener("click", async () => {
    try {
      await apiPost("/api/clear");
      state.data = null;
      await syncState();
      showSuccess("Memory", "Memory cleared successfully.");
    } catch { showError("Failed to clear memory."); }
  });

  // Left panel delegation
  els.leftPanel.addEventListener("click", (e) => {
    const cmdCard = e.target.closest(".command-card");
    if (cmdCard) {
      const command = cmdCard.dataset.command;
      if (command) { els.commandInput.value = command; sendMessage(); }
      return;
    }
    const checkbox = e.target.closest('input[type="checkbox"][data-task-id]');
    if (checkbox) {
      apiPost("/api/task/complete", { target: checkbox.dataset.taskId })
        .then(() => syncState())
        .catch(() => showError("Failed to update task."));
    }
  });

  // Init audio on any user interaction (autoplay policy)
  document.addEventListener("click", () => {
    initAudioContext();
    resumeAudioContext();
  }, { once: true });
}

/* ════════════════════════════════════════
   MESSAGE HANDLING
   ════════════════════════════════════════ */

async function sendMessage() {
  const text = els.commandInput.value.trim();
  if (!text) return;
  els.commandInput.value = "";
  setFridayMode("thinking");

  try {
    const result = await apiPost("/api/chat", { text, source: "typed" });
    if (result.state) state.data = result.state;
    renderLeftPanel();
    renderRightPanel();
    updateChips();
    if (result.reply) {
      updateTranscript(result.reply, false);
      finalizeSpeech(result.reply);
    }
    setFridayMode("idle");
  } catch (err) {
    showError(err instanceof Error ? err.message : "Message failed.");
    setFridayMode("idle");
  }
}

function updateTranscript(text, isInterim) {
  els.transcriptLine.textContent = text;
  if (!isInterim) {
    els.transcriptLine.style.animation = "none";
    els.transcriptLine.offsetHeight;
    els.transcriptLine.style.animation = "boot-fade 400ms ease";
  }
}

/* ════════════════════════════════════════
   VOICE
   ════════════════════════════════════════ */

async function toggleVoice() {
  if (state.listening) stopListening();
  else startListening();
}

function startListening() {
  state.listening = true;
  setFridayMode("listening");
  updateChips();
  showToast("Voice", "Listening... Speak now.");

  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    state.recognition = new SpeechRecognition();
    state.recognition.continuous = true;
    state.recognition.interimResults = true;
    state.recognition.lang = "en-US";

    state.recognition.onresult = (e) => {
      let final = "", interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      if (interim) updateTranscript(interim, true);
      if (final) { updateTranscript(final, false); handleVoiceInput(final); }
    };
    state.recognition.onerror = () => { stopListening(); };
    state.recognition.onend = () => {
      if (state.listening) { try { state.recognition.start(); } catch { stopListening(); } }
    };
    try { state.recognition.start(); } catch { stopListening(); }
  }
}

function stopListening() {
  state.listening = false;
  setFridayMode("idle");
  updateChips();
  if (state.recognition) { try { state.recognition.stop(); } catch {} state.recognition = null; }
}

async function handleVoiceInput(text) {
  setFridayMode("thinking");
  try {
    const result = await apiPost("/api/chat", { text, source: "voice" });
    if (result.state) state.data = result.state;
    renderLeftPanel();
    renderRightPanel();
    updateChips();
    if (result.reply) finalizeSpeech(result.reply);
  } catch { showError("Voice command failed."); }
  setFridayMode(state.listening ? "listening" : "idle");
}

/* ════════════════════════════════════════
   SYNC
   ════════════════════════════════════════ */

async function syncState() {
  try {
    const data = await apiGet("/api/state");
    state.data = data;
    if (data.protocol) {
      state.currentProtocol = data.protocol.id || data.protocol.name?.toLowerCase() || "core";
      if (data.protocol.colors) applyProtocolColors(data.protocol.colors);
    }
    renderLeftPanel();
    renderRightPanel();
    updateChips();
  } catch (err) { console.warn("State sync failed:", err); }
}

async function syncMetrics() {
  try {
    const data = await apiGet("/api/metrics");
    state.metrics = data;
    renderRightPanel();
    updateChips();
  } catch { /* silent */ }
}

function startClock() {
  setInterval(() => { els.timeChip.textContent = formatClock(); }, 1000);
}

/* ════════════════════════════════════════
   INIT
   ════════════════════════════════════════ */

async function init() {
  await syncState();
  await syncMetrics();
  initEventListeners();
  startClock();
  runBootSequence();

  setInterval(syncMetrics, 5000);
  setInterval(syncState, 10000);

  if ("speechSynthesis" in window) {
    const loadVoices = () => {
      state.voices = window.speechSynthesis.getVoices();
      selectBestVoice();
      updateChips();
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  loadProtocol();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
