const $ = (s) => document.querySelector(s);

function showTab(name) {
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
  $("#panel-" + name).classList.add("active");
  document.querySelector(`nav button[data-tab="${name}"]`).classList.add("active");
}

document.querySelectorAll("nav button[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

let state = {
  videoId: null,
  frameIdx: 0,
  totalFrames: 0,
  lastDetections: [],
};

async function refreshVideos() {
  const r = await fetch("/api/videos");
  const j = await r.json();
  const ul = $("#video-list");
  ul.innerHTML = "";
  (j.videos || []).forEach((v) => {
    const li = document.createElement("li");
    li.textContent = v.original_name + " — " + v.id.slice(0, 8) + "…";
    li.dataset.id = v.id;
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
  if (!state.videoId) {
    $("#train-msg").textContent = "Selecione um vídeo na lista.";
    return;
  }
  const idx = parseInt($("#frame-idx").value || "0", 10);
  state.frameIdx = idx;
  $("#train-msg").textContent = "A carregar frame…";
  try {
    const r = await fetch(`/api/video/${state.videoId}/frame/${idx}`);
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || r.statusText);
    state.totalFrames = j.total_frames || 0;
    state.lastDetections = j.detections || [];
    $("#preview").src = "data:image/jpeg;base64," + j.image_base64;
    $("#detections-json").textContent = JSON.stringify(j.detections || [], null, 2);
    $("#train-msg").textContent = `Frame ${j.frame_idx} / ~${j.total_frames} · ${(j.detections || []).length} deteções`;
  } catch (e) {
    $("#train-msg").textContent = "Erro: " + e.message;
    $("#train-msg").classList.add("error");
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
    $("#train-msg").textContent = "Erro ao guardar: " + (j.detail || r.statusText);
    $("#train-msg").classList.add("error");
    return;
  }
  $("#train-msg").textContent = approved ? "Marcado como correto ✓" : "Marcado como incorreto (registado para revisão)";
  loadFeedbackList();
}

$("#btn-ok").addEventListener("click", () => sendFeedback(true));
$("#btn-bad").addEventListener("click", () => sendFeedback(false));

$("#upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = $("#file-input").files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  $("#upload-msg").textContent = "A enviar…";
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  const j = await r.json();
  if (!r.ok) {
    $("#upload-msg").textContent = j.detail || "Erro no upload";
    $("#upload-msg").classList.add("error");
    return;
  }
  $("#upload-msg").textContent = "Enviado: " + j.name;
  $("#upload-msg").classList.remove("error");
  state.videoId = j.id;
  await refreshVideos();
  document.querySelector(`#video-list li[data-id="${j.id}"]`)?.classList.add("selected");
  $("#frame-idx").value = 0;
  loadFrame();
});

async function loadFeedbackList() {
  const r = await fetch("/api/feedback");
  const j = await r.json();
  const el = $("#feedback-list");
  el.innerHTML = "";
  (j.items || []).slice(0, 30).forEach((it) => {
    const p = document.createElement("p");
    p.className = "msg";
    p.textContent = `${it.video_id.slice(0, 8)}… frame ${it.frame_idx} — ${it.approved ? "OK" : "rejeitado"}`;
    el.appendChild(p);
  });
}

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
    $("#live-msg").textContent = j.detail || "Erro";
    return;
  }
  $("#live-msg").textContent = "Em curso. Stream abaixo (pode demorar alguns segundos).";
  $("#live-img").src = "/api/live/mjpeg?t=" + Date.now();
});

$("#btn-live-stop").addEventListener("click", async () => {
  await fetch("/api/live/stop", { method: "POST" });
  $("#live-img").removeAttribute("src");
  $("#live-msg").textContent = "Parado.";
});

refreshVideos();
loadFeedbackList();
