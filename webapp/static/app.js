const $ = (s) => document.querySelector(s);

function showTab(name) {
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
  $("#panel-" + name).classList.add("active");
  document.querySelector(`.tabs button[data-tab="${name}"]`).classList.add("active");
}

document.querySelectorAll(".tabs button[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

function errDetail(err) {
  if (err == null) return "";
  if (typeof err === "string") return err;
  if (Array.isArray(err)) return err.map((e) => e.msg || e).join("; ");
  if (err.detail != null) return errDetail(err.detail);
  return String(err);
}

let state = {
  videoId: null,
  frameIdx: 0,
  totalFrames: 0,
  lastDetections: [],
};

function setPreviewHasImage(on) {
  const w = $(".preview-wrap");
  if (on) w.classList.add("has-image");
  else w.classList.remove("has-image");
}

function renderInsight(summary) {
  const head = $("#frame-headline");
  if (summary && summary.headline_pt) {
    head.hidden = false;
    head.querySelector(".frame-headline-main").textContent = summary.headline_pt;
    head.querySelector(".frame-headline-sub").textContent = summary.subline_pt || "";
  } else {
    head.hidden = true;
  }

  const box = $("#insight-banner");
  if (!summary || !summary.banner_title) {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  box.className = "insight-banner level-" + (summary.banner_level || "info");
  box.querySelector(".insight-title").textContent = summary.banner_title;
  box.querySelector(".insight-detail").textContent = summary.banner_detail || "";
  const ul = $("#insight-lines");
  ul.innerHTML = "";
  (summary.lines || []).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line.text;
    li.className =
      "lvl-" + (line.level === "bad" ? "bad" : line.level === "ok" ? "ok" : "neutral");
    ul.appendChild(li);
  });
}

async function loadModelStrip() {
  const strip = $("#model-strip");
  try {
    const r = await fetch("/api/model-info");
    const m = await r.json();
    if (!r.ok) return;
    strip.hidden = false;
    const fb = m.using_fallback_yolov8n ? " (fallback yolov8n)" : "";
    strip.innerHTML =
      "<strong>Modelo:</strong> <code>" +
      escapeHtml(String(m.weights_effective || "?")) +
      "</code>" +
      escapeHtml(fb) +
      " · <span class='model-hint'>" +
      (m.class_names && Object.keys(m.class_names).length
        ? "Classes: " +
          escapeHtml(
            Object.values(m.class_names)
              .slice(0, 12)
              .join(", ")
          ) +
          (Object.keys(m.class_names).length > 12 ? "…" : "")
        : "") +
      "</span>";
  } catch (e) {
    strip.hidden = true;
  }
}

async function loadStats() {
  try {
    const r = await fetch("/api/stats");
    const s = await r.json();
    if (!r.ok) throw new Error(errDetail(s));

    const acc = s.accuracy_percent;
    $("#kpi-accuracy").textContent = acc == null ? "—" : `${acc}%`;
    $("#kpi-total").textContent = s.total_labels ?? 0;
    $("#kpi-ok").textContent = s.approved ?? 0;
    $("#kpi-bad").textContent = s.rejected ?? 0;

    const roll = s.rolling || {};
    const wn = roll.window ?? 0;
    $("#kpi-roll-n").textContent = wn;
    $("#kpi-rolling").textContent =
      roll.accuracy_percent == null ? "—" : `${roll.accuracy_percent}%`;

    const pct = acc == null ? 0 : acc;
    $("#progress-pct").textContent = `${pct}%`;
    $("#progress-fill").style.width = `${pct}%`;

    renderDailyChart(s.daily || []);
    renderVideoTable(s.per_video || []);
    renderRecentTable(s.recent_feedback || []);

    $("#table-empty").classList.toggle("visible", (s.total_labels || 0) === 0);
  } catch (e) {
    console.error(e);
  }
}

function renderDailyChart(daily) {
  const el = $("#daily-chart");
  el.innerHTML = "";
  if (!daily.length) {
    el.innerHTML = '<p class="msg">Ainda sem etiquetas por dia.</p>';
    return;
  }
  const maxC = Math.max(...daily.map((d) => d.count), 1);
  daily.forEach((d) => {
    const h = Math.round((d.count / maxC) * 100);
    const div = document.createElement("div");
    div.className = "bar-item";
    div.innerHTML = `
      <div class="bar-col" style="height:${Math.max(h, 8)}px" title="${d.date}: ${d.count} etiquetas (${d.approved} ok / ${d.rejected} erro)"></div>
      <span class="bar-label">${d.date.slice(5)}</span>
    `;
    el.appendChild(div);
  });
}

function renderVideoTable(rows) {
  const tb = $("#table-videos tbody");
  tb.innerHTML = "";
  const has = rows.some((r) => r.labels > 0);
  $("#table-empty").classList.toggle("visible", !has);
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    const pct = r.accuracy_percent == null ? "—" : `${r.accuracy_percent}%`;
    tr.innerHTML = `
      <td>${escapeHtml(r.name)}</td>
      <td>${r.labels}</td>
      <td>${r.approved}</td>
      <td>${r.rejected}</td>
      <td><strong>${pct}</strong></td>
    `;
    tb.appendChild(tr);
  });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function fmtTime(ts) {
  if (ts == null) return "—";
  const d = new Date(typeof ts === "number" ? ts * 1000 : Date.parse(ts));
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("pt-PT", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderRecentTable(items) {
  const tb = $("#table-recent tbody");
  tb.innerHTML = "";
  items.forEach((it) => {
    const tr = document.createElement("tr");
    const ok = it.approved === 1 || it.approved === true;
    tr.innerHTML = `
      <td>${fmtTime(it.created_at)}</td>
      <td title="${it.video_id}">${escapeHtml(String(it.video_id).slice(0, 10))}…</td>
      <td>${it.frame_idx}</td>
      <td><span class="pill ${ok ? "ok" : "bad"}">${ok ? "Correto" : "Incorreto"}</span></td>
    `;
    tb.appendChild(tr);
  });
}

async function refreshVideos() {
  const r = await fetch("/api/videos");
  const j = await r.json();
  const ul = $("#video-list");
  ul.innerHTML = "";
  const list = j.videos || [];
  $("#video-empty").classList.toggle("visible", list.length === 0);
  list.forEach((v) => {
    const li = document.createElement("li");
    li.dataset.id = v.id;
    const left = document.createElement("span");
    left.textContent = v.original_name;
    const meta = document.createElement("span");
    meta.className = "video-meta";
    meta.textContent = v.id.slice(0, 8) + "…";
    li.appendChild(left);
    li.appendChild(meta);
    if (state.videoId === v.id) li.classList.add("selected");
    li.addEventListener("click", () => {
      state.videoId = v.id;
      state.frameIdx = 0;
      $("#frame-idx").value = 0;
      ul.querySelectorAll("li").forEach((x) => x.classList.remove("selected"));
      li.classList.add("selected");
      loadFrame();
    });
    ul.appendChild(li);
  });
}

async function loadFrame() {
  $("#train-msg").classList.remove("error");
  if (!state.videoId) {
    $("#train-msg").textContent = "Selecione um vídeo na lista.";
    setPreviewHasImage(false);
    $("#preview").removeAttribute("src");
    $("#insight-banner").hidden = true;
    $("#frame-headline").hidden = true;
    return;
  }
  const idx = parseInt($("#frame-idx").value || "0", 10);
  state.frameIdx = idx;
  $("#train-msg").textContent = "A carregar frame…";
  try {
    const r = await fetch(`/api/video/${state.videoId}/frame/${idx}`);
    const j = await r.json();
    if (!r.ok) throw new Error(errDetail(j.detail || j));
    state.totalFrames = j.total_frames || 0;
    state.lastDetections = j.detections || [];
    $("#preview").src = "data:image/jpeg;base64," + j.image_base64;
    setPreviewHasImage(true);
    $("#detections-json").textContent = JSON.stringify(j.detections || [], null, 2);
    renderInsight(j.summary || null);
    $("#train-msg").textContent = `Frame ${j.frame_idx} / ~${j.total_frames} · ${(j.detections || []).length} deteção(ões)`;
  } catch (e) {
    $("#train-msg").textContent = "Erro: " + e.message;
    $("#train-msg").classList.add("error");
    setPreviewHasImage(false);
    $("#frame-headline").hidden = true;
    $("#insight-banner").hidden = true;
  }
}

$("#btn-load-frame").addEventListener("click", () => loadFrame());
$("#btn-prev").addEventListener("click", () => {
  const v = Math.max(0, parseInt($("#frame-idx").value || "0", 10) - 5);
  $("#frame-idx").value = v;
  loadFrame();
});
$("#btn-next").addEventListener("click", () => {
  const v = parseInt($("#frame-idx").value || "0", 10) + 5;
  $("#frame-idx").value = v;
  loadFrame();
});

async function sendFeedback(approved) {
  if (!state.videoId) return;
  $("#train-msg").classList.remove("error");
  const r = await fetch(`/api/video/${state.videoId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      frame_idx: state.frameIdx,
      approved,
      detections: state.lastDetections,
      notes: $("#notes").value || "",
    }),
  });
  const j = await r.json();
  if (!r.ok) {
    $("#train-msg").textContent = "Erro ao guardar: " + errDetail(j.detail || j);
    $("#train-msg").classList.add("error");
    return;
  }
  $("#train-msg").textContent = approved
    ? "Marcado como correto. Métricas atualizadas."
    : "Marcado como incorreto. Métricas atualizadas.";
  await loadStats();
}

$("#btn-ok").addEventListener("click", () => sendFeedback(true));
$("#btn-bad").addEventListener("click", () => sendFeedback(false));

const dropZone = $("#drop-zone");
const fileInput = $("#file-input");
const dropText = $("#drop-text");

dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const f = fileInput.files[0];
  dropText.textContent = f ? f.name : "Solta o vídeo aqui ou clica para procurar";
});

["dragenter", "dragover"].forEach((ev) => {
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((ev) => {
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
  });
});
dropZone.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith("video/")) {
    fileInput.files = e.dataTransfer.files;
    dropText.textContent = f.name;
  }
});

$("#upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = fileInput.files[0];
  if (!f) {
    $("#upload-msg").textContent = "Escolhe um ficheiro de vídeo.";
    $("#upload-msg").classList.add("error");
    return;
  }
  const fd = new FormData();
  fd.append("file", f);
  $("#upload-msg").textContent = "A enviar…";
  $("#upload-msg").classList.remove("error");
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  const j = await r.json();
  if (!r.ok) {
    $("#upload-msg").textContent = errDetail(j.detail) || "Erro no upload";
    $("#upload-msg").classList.add("error");
    return;
  }
  $("#upload-msg").textContent = "Enviado: " + j.name;
  state.videoId = j.id;
  await refreshVideos();
  await loadStats();
  const li = document.querySelector(`#video-list li[data-id="${j.id}"]`);
  if (li) {
    li.classList.add("selected");
    li.scrollIntoView({ block: "nearest" });
  }
  $("#frame-idx").value = 0;
  loadFrame();
});

$("#btn-refresh-stats").addEventListener("click", () => loadStats());

$("#btn-live-start").addEventListener("click", async () => {
  const url = $("#live-url").value.trim();
  if (!url) return;
  $("#live-msg").textContent = "A iniciar…";
  const r = await fetch("/api/live/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  const j = await r.json();
  if (!r.ok) {
    $("#live-msg").textContent = errDetail(j.detail) || "Erro";
    return;
  }
  $("#live-msg").textContent = "Em curso. Stream abaixo.";
  $("#live-img").src = "/api/live/mjpeg?t=" + Date.now();
});

$("#btn-live-stop").addEventListener("click", async () => {
  await fetch("/api/live/stop", { method: "POST" });
  $("#live-img").removeAttribute("src");
  $("#live-msg").textContent = "Parado.";
});

(async function init() {
  await loadModelStrip();
  await refreshVideos();
  await loadStats();
  setInterval(loadStats, 60000);
})();
