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

/**
 * Base da API (uvicorn). Por defeito usa caminhos relativos (mesmo host/porta que o HTML).
 * Se abrires o site na porta 80 e o FastAPI só estiver na 8090, define antes de app.js:
 *   window.__EPI_API_BASE__ = "http://SEU_IP:8090"
 * ou no index.html: <meta name="epi-api-base" content="http://SEU_IP:8090" />
 */
function getApiBase() {
  if (typeof window !== "undefined" && window.__EPI_API_BASE__) {
    return String(window.__EPI_API_BASE__).replace(/\/$/, "");
  }
  const m = document.querySelector('meta[name="epi-api-base"]');
  if (m && m.content && String(m.content).trim()) {
    return String(m.content).trim().replace(/\/$/, "");
  }
  return "";
}

function apiUrl(path) {
  const p = path.startsWith("/") ? path : "/" + path;
  const b = getApiBase();
  return b ? b + p : p;
}

/** Mensagem útil quando a API responde 404 (rota em falta vs recurso). */
function httpErrorMessage(r, j, text) {
  let msg = errDetail(j.detail || j) || (text || "").trim();
  if (r.status === 404) {
    if (msg === "Not Found" || !msg) {
      const port = typeof location !== "undefined" ? location.port : "";
      const same8090 = port === "8090" || (getApiBase() || "").includes(":8090");
      if (same8090) {
        return (
          "404 na porta 8090: o processo que escuta aqui NÃO é o uvicorn deste projeto " +
          "(ou está desatualizado). Na VPS SSH: cd /opt/epi && source .venv/bin/activate && " +
          "fuser -k 8090/tcp ; python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8090. " +
          "Teste: curl -s http://127.0.0.1:8090/openapi.json | head -c 80"
        );
      }
      return (
        "404: esta origem não tem a API FastAPI (rota em falta). " +
        "Abre o painel diretamente em http://IP:8090 ou define no HTML " +
        '<meta name="epi-api-base" content="http://IP:8090"> se o site estiver noutra porta. ' +
        "Na VPS: git pull + reinicia o uvicorn."
      );
    }
  }
  return msg || "HTTP " + r.status;
}

let state = {
  videoId: null,
  frameIdx: 0,
  totalFrames: 0,
  lastDetections: [],
};

/** false se GET /api/health não for JSON válido do painel (service=epi-web). */
let apiServerOk = true;

/** Após 404 em /api/stats, deixa de repetir pedidos ao minuto. */
let statsPollDisabled = false;
let statsIntervalId = null;

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

/**
 * Faixa visível: alerta vermelho se modelo EPI e há sem_epi / hint_bad;
 * aviso âmbar se modelo COCO e há pessoas (não há alerta «sem EPI» real).
 */
function renderEpiAlert(summary, modelInfo) {
  const strip = $("#epi-alert-strip");
  if (!strip) return;
  const iconEl = strip.querySelector(".epi-alert-icon");
  const textEl = strip.querySelector(".epi-alert-text");
  if (!textEl) return;

  if (!summary) {
    strip.hidden = true;
    return;
  }

  const counts = summary.counts || {};
  const sem = Number(counts.sem_epi || 0);
  const pessoas = Number(counts.pessoa || 0);
  const hintBad = Number(counts.hint_bad || 0);
  const capable =
    summary.model_epi_capable === true ||
    (modelInfo && modelInfo.model_epi_capable === true);

  strip.className = "epi-alert-strip";
  strip.hidden = false;

  if (capable && (sem > 0 || hintBad > 0)) {
    strip.classList.add("alert-danger");
    if (iconEl) iconEl.textContent = "🚨";
    const n = sem > 0 ? sem : hintBad;
    textEl.textContent =
      "Alerta: " +
      n +
      " indício(s) de possível falta de EPI neste frame. Confirma na imagem antes de validar.";
    return;
  }

  const fallback =
    summary.using_fallback_yolov8n === true ||
    (modelInfo && modelInfo.using_fallback_yolov8n === true);
  if (!capable && pessoas > 0) {
    strip.classList.add("alert-warn");
    if (iconEl) iconEl.textContent = "ℹ️";
    textEl.textContent =
      "Sem alerta «pessoas sem EPI»: este modelo (" +
      (fallback ? "COCO / yolov8n" : "genérico") +
      ") detetou " +
      pessoas +
      " pessoa(s) mas não classifica EPI. Para alertas reais, usa um modelo treinado (ex.: models/ppe.pt).";
    return;
  }

  strip.hidden = true;
}

function hideEpiAlert() {
  const strip = $("#epi-alert-strip");
  if (strip) strip.hidden = true;
}

async function loadModelStrip() {
  if (!apiServerOk) return;
  const strip = $("#model-strip");
  try {
    const r = await fetch(apiUrl("/api/model-info"));
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

async function verifyApiServer() {
  try {
    const r = await fetch(apiUrl("/api/health"));
    const text = await r.text();
    let j = {};
    try {
      if (text) j = JSON.parse(text);
    } catch (_) {
      /* não é JSON — proxy/página a fingir 200 */
    }
    const isEpi =
      r.ok &&
      j &&
      (j.service === "epi-web" || j.ok === "true");
    if (isEpi) {
      apiServerOk = true;
      return true;
    }
  } catch (e) {
    /* rede / offline */
  }
  apiServerOk = false;
  const b = $("#server-banner");
  if (b) {
    b.hidden = false;
    b.innerHTML =
      "<strong>API inválida ou em falta:</strong> <code>GET /api/health</code> tem de devolver JSON " +
      '<code>{"ok":"true","service":"epi-web"}</code>. Se vês 200 mas HTML ou outro serviço, o processo na porta não é o uvicorn certo. ' +
      "Na VPS: <code>cd /opt/epi && source .venv/bin/activate && fuser -k 8090/tcp</code> e depois " +
      "<code>python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8090</code>. " +
      "Confirma: <code>curl -s http://127.0.0.1:8090/api/health</code>";
  }
  return false;
}

async function loadStats() {
  if (!apiServerOk || statsPollDisabled) return;
  try {
    const r = await fetch(apiUrl("/api/stats"));
    const text = await r.text();
    let s = {};
    try {
      if (text) s = JSON.parse(text);
    } catch (_) {}
    if (!r.ok) {
      if (r.status === 404) {
        statsPollDisabled = true;
        if (statsIntervalId != null) {
          clearInterval(statsIntervalId);
          statsIntervalId = null;
        }
        apiServerOk = false;
        const b = $("#server-banner");
        if (b) {
          b.hidden = false;
          b.innerHTML =
            "<strong>/api/stats devolveu 404:</strong> o uvicorn do projeto não está a servir esta porta " +
            "(ou outro programa ocupa a 8090). " +
            escapeHtml(httpErrorMessage(r, s, text));
        }
      } else {
        console.error(httpErrorMessage(r, s, text));
      }
      return;
    }

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
  const r = await fetch(apiUrl("/api/videos"));
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
    hideEpiAlert();
    return;
  }
  const idx = parseInt($("#frame-idx").value || "0", 10);
  state.frameIdx = idx;
  $("#train-msg").textContent = "A carregar frame…";
  try {
    const r = await fetch(apiUrl(`/api/video/${state.videoId}/frame/${idx}`));
    const j = await r.json();
    if (!r.ok) throw new Error(errDetail(j.detail || j));
    state.totalFrames = j.total_frames || 0;
    state.lastDetections = j.detections || [];
    $("#preview").src = "data:image/jpeg;base64," + j.image_base64;
    setPreviewHasImage(true);
    $("#detections-json").textContent = JSON.stringify(j.detections || [], null, 2);
    renderInsight(j.summary || null);
    renderEpiAlert(j.summary || null, j.model_info || null);
    $("#train-msg").textContent = `Frame ${j.frame_idx} / ~${j.total_frames} · ${(j.detections || []).length} deteção(ões)`;
  } catch (e) {
    $("#train-msg").textContent = "Erro: " + e.message;
    $("#train-msg").classList.add("error");
    setPreviewHasImage(false);
    $("#frame-headline").hidden = true;
    $("#insight-banner").hidden = true;
    hideEpiAlert();
  }
}

$("#btn-load-frame").addEventListener("click", () => loadFrame());

async function analyzeFullVideo() {
  $("#train-msg").classList.remove("error");
  if (!state.videoId) {
    $("#train-msg").textContent = "Selecione um vídeo na lista.";
    return;
  }
  const box = $("#full-report");
  box.hidden = false;
  box.className = "full-report loading";
  box.innerHTML =
    "<p class=\"msg\">A analisar o vídeo (várias inferências)… pode demorar.</p>";
  const btn = $("#btn-analyze-full");
  btn.disabled = true;
  const stride = Math.max(1, parseInt($("#full-stride").value || "30", 10));
  const maxFrames = Math.max(1, parseInt($("#full-max").value || "400", 10));
  try {
    const r = await fetch(apiUrl(`/api/video/${state.videoId}/analyze-full`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frame_stride: stride, max_frames: maxFrames }),
    });
    const text = await r.text();
    let j = {};
    try {
      if (text) j = JSON.parse(text);
    } catch (_) {}
    if (!r.ok) throw new Error(httpErrorMessage(r, j, text));

    const mi = j.model_info || {};
    const fb = mi.using_fallback_yolov8n ? " (modelo COCO / fallback)" : "";
    const trunc = j.truncated
      ? `<p class="msg warn">Análise truncada: limite de ${j.max_frames_limit} inferências; aumenta o salto ou o máximo se precisares de mais cobertura.</p>`
      : "";

    const agg = j.aggregated || {};
    const semAgg = Number(agg.sem_epi || 0);
    const pAgg = Number(agg.pessoa || 0);
    const epiCap = mi.model_epi_capable === true;
    let aggAlert = "";
    if (epiCap && semAgg > 0) {
      aggAlert = `<div class="full-report-alert-block danger" role="alert">🚨 Alerta (vídeo agregado): ${semAgg} ocorrência(s) de possível falta de EPI nas amostras. Revê os frames com deteção.</div>`;
    } else if (!epiCap && pAgg > 0) {
      aggAlert = `<div class="full-report-alert-block warn" role="status">ℹ️ Não há alerta «sem EPI» com este modelo: foram somadas ${pAgg} deteção(ões) de «pessoa» (a mesma pessoa pode repetir em vários frames). Para alertas de EPI, usa um modelo treinado (ppe.pt).</div>`;
    }

    box.className = "full-report";
    box.innerHTML = `
      <h3 class="full-report-title">Relatório do vídeo completo</h3>
      <p class="full-report-meta"><code>${escapeHtml(String(mi.weights_effective || "?"))}</code>${escapeHtml(fb)} · ${j.frames_sampled} frame(s) amostrado(s) · stride ${j.frame_stride}</p>
      ${aggAlert}
      <p class="full-report-main">${escapeHtml(j.report_pt || "")}</p>
      <p class="full-report-detail">${escapeHtml(j.detail_pt || "")}</p>
      ${trunc}
      <details class="json-details"><summary>Totais (JSON)</summary><pre class="det-json">${escapeHtml(JSON.stringify(j.aggregated || {}, null, 2))}</pre></details>
    `;
    $("#train-msg").textContent = "Relatório global do vídeo pronto (abaixo).";
  } catch (e) {
    box.className = "full-report";
    box.innerHTML = `<p class="msg error">${escapeHtml(e.message)}</p>`;
    $("#train-msg").textContent = "Erro na análise completa: " + e.message;
    $("#train-msg").classList.add("error");
  } finally {
    btn.disabled = false;
  }
}

$("#btn-analyze-full").addEventListener("click", () => analyzeFullVideo());
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
  const r = await fetch(apiUrl(`/api/video/${state.videoId}/feedback`), {
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
  if (!apiServerOk) {
    $("#upload-msg").textContent =
      "Servidor API indisponível. Usa uvicorn (ver faixa no topo ou README).";
    $("#upload-msg").classList.add("error");
    return;
  }
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
  const r = await fetch(apiUrl("/api/upload"), { method: "POST", body: fd });
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

$("#btn-refresh-stats").addEventListener("click", async () => {
  statsPollDisabled = false;
  apiServerOk = true;
  await loadStats();
  if (!statsPollDisabled && apiServerOk && statsIntervalId == null) {
    statsIntervalId = setInterval(loadStats, 60000);
  }
});

$("#btn-live-start").addEventListener("click", async () => {
  const url = $("#live-url").value.trim();
  if (!url) return;
  $("#live-msg").textContent = "A iniciar…";
  const r = await fetch(apiUrl("/api/live/start"), {
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
  $("#live-img").src = apiUrl("/api/live/mjpeg") + "?t=" + Date.now();
});

$("#btn-live-stop").addEventListener("click", async () => {
  await fetch(apiUrl("/api/live/stop"), { method: "POST" });
  $("#live-img").removeAttribute("src");
  $("#live-msg").textContent = "Parado.";
});

(async function init() {
  await verifyApiServer();
  if (!apiServerOk) return;
  await loadModelStrip();
  await refreshVideos();
  await loadStats();
  if (!statsPollDisabled && apiServerOk) {
    statsIntervalId = setInterval(loadStats, 60000);
  }
})();
