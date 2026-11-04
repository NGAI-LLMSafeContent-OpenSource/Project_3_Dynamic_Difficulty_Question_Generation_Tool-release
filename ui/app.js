const DIFFICULTY_LEVELS = ["H1", "H2", "H3", "H4"];

const state = {
  apiReady: false,
  mode: "single",
  skillVersions: [],
  topics: [],
  domains: [],
  selectedTopics: new Set(),
  activeJobId: null,
  job: null,
  pollTimer: null,
  agentTraceHasProgress: false,
  exampleSamples: [],
  exampleLevel: "ALL",
};

const nodes = {
  agentStatus: document.getElementById("agentStatus"),
  startJobButton: document.getElementById("startJobButton"),
  stopJobButton: document.getElementById("stopJobButton"),
  resumeJobButton: document.getElementById("resumeJobButton"),
  exportConfigButton: document.getElementById("exportConfigButton"),
  copyApiButton: document.getElementById("copyApiButton"),
  downloadSamplesButton: document.getElementById("downloadSamplesButton"),
  showBaseConfigButton: document.getElementById("showBaseConfigButton"),
  runId: document.getElementById("runId"),
  skillVersion: document.getElementById("skillVersion"),
  dataSourceMode: document.getElementById("dataSourceMode"),
  seedInputPath: document.getElementById("seedInputPath"),
  seedSources: document.getElementById("seedSources"),
  outputDir: document.getElementById("outputDir"),
  language: document.getElementById("language"),
  randomSeed: document.getElementById("randomSeed"),
  composerConcurrency: document.getElementById("composerConcurrency"),
  singleSettings: document.getElementById("singleSettings"),
  batchSettings: document.getElementById("batchSettings"),
  singleDomain: document.getElementById("singleDomain"),
  singleLevel: document.getElementById("singleLevel"),
  countH1: document.getElementById("countH1"),
  countH2: document.getElementById("countH2"),
  countH3: document.getElementById("countH3"),
  countH4: document.getElementById("countH4"),
  batchTotalSummary: document.getElementById("batchTotalSummary"),
  topicList: document.getElementById("topicList"),
  selectAllTopicsButton: document.getElementById("selectAllTopicsButton"),
  clearTopicsButton: document.getElementById("clearTopicsButton"),
  apiBase: document.getElementById("apiBase"),
  model: document.getElementById("model"),
  apiKeyEnv: document.getElementById("apiKeyEnv"),
  maxTokens: document.getElementById("maxTokens"),
  temperature: document.getElementById("temperature"),
  timeout: document.getElementById("timeout"),
  discardRetryLimit: document.getElementById("discardRetryLimit"),
  guardApiBase: document.getElementById("guardApiBase"),
  guardModel: document.getElementById("guardModel"),
  configSummary: document.getElementById("configSummary"),
  showConfigButton: document.getElementById("showConfigButton"),
  closeConfigButton: document.getElementById("closeConfigButton"),
  configDialog: document.getElementById("configDialog"),
  configPreview: document.getElementById("configPreview"),
  apiCommandDialog: document.getElementById("apiCommandDialog"),
  apiCommandOutput: document.getElementById("apiCommandOutput"),
  closeApiCommandButton: document.getElementById("closeApiCommandButton"),
  closeBaseConfigButton: document.getElementById("closeBaseConfigButton"),
  baseConfigDialog: document.getElementById("baseConfigDialog"),
  jobBadge: document.getElementById("jobBadge"),
  progressFill: document.getElementById("progressFill"),
  progressText: document.getElementById("progressText"),
  jobStats: document.getElementById("jobStats"),
  levelProgress: document.getElementById("levelProgress"),
  agentTrace: document.getElementById("agentTrace"),
  logBox: document.getElementById("logBox"),
  resultSummary: document.getElementById("resultSummary"),
  samplePreview: document.getElementById("samplePreview"),
  emptyTemplate: document.getElementById("emptyTemplate"),
  exampleSummary: document.getElementById("exampleSummary"),
  exampleGallery: document.getElementById("exampleGallery"),
};

document.querySelectorAll(".mode-tab").forEach((button) => {
  button.addEventListener("click", () => switchMode(button.dataset.mode));
});
document.querySelectorAll(".example-tab").forEach((button) => {
  button.addEventListener("click", () => selectExampleLevel(button.dataset.level));
});
nodes.startJobButton.addEventListener("click", startJob);
nodes.stopJobButton.addEventListener("click", stopJob);
nodes.resumeJobButton.addEventListener("click", resumeJob);
nodes.exportConfigButton.addEventListener("click", exportConfig);
nodes.copyApiButton.addEventListener("click", copyApi);
nodes.downloadSamplesButton.addEventListener("click", downloadSamples);
nodes.showBaseConfigButton.addEventListener("click", () => nodes.baseConfigDialog.showModal());
nodes.showConfigButton.addEventListener("click", showConfigDialog);
nodes.closeConfigButton.addEventListener("click", () => nodes.configDialog.close());
nodes.closeApiCommandButton.addEventListener("click", () => nodes.apiCommandDialog.close());
nodes.closeBaseConfigButton.addEventListener("click", () => nodes.baseConfigDialog.close());
nodes.selectAllTopicsButton.addEventListener("click", () => setAllTopics(true));
nodes.clearTopicsButton.addEventListener("click", () => setAllTopics(false));
nodes.seedInputPath.addEventListener("change", loadSeedTopics);
nodes.dataSourceMode.addEventListener("change", handleDataSourceModeChange);
nodes.skillVersion.addEventListener("change", renderConfig);

document.querySelectorAll("input, select").forEach((input) => {
  input.addEventListener("input", renderConfig);
  input.addEventListener("change", renderConfig);
});

checkApi();
loadSeedTopics();
loadExampleSamples();
renderConfig();
renderJob();

async function loadExampleSamples() {
  try {
    const response = await fetch("/api/example-samples", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ?? `HTTP ${response.status}`);
    }
    state.exampleSamples = payload.samples ?? [];
    renderExampleSamples();
  } catch (error) {
    nodes.exampleSummary.textContent = "读取失败";
    nodes.exampleGallery.innerHTML = `<div class="empty-state"><h3>样例加载失败</h3><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function selectExampleLevel(level) {
  state.exampleLevel = level;
  document.querySelectorAll(".example-tab").forEach((button) => {
    const active = button.dataset.level === level;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  renderExampleSamples();
}

function renderExampleSamples() {
  const visibleSamples = state.exampleSamples.filter((sample) => (
    state.exampleLevel === "ALL" || sample.difficulty_level === state.exampleLevel
  ));
  const levelLabel = state.exampleLevel === "ALL" ? "H1–H4" : state.exampleLevel;
  nodes.exampleSummary.textContent = `${levelLabel} · ${visibleSamples.length} 条`;
  nodes.exampleGallery.replaceChildren();
  visibleSamples.forEach((sample, index) => {
    const card = document.createElement("article");
    card.className = "sample-item example-card";
    const harmfulCount = sample.harmful_spans?.length ?? sample.harmful_count ?? 0;
    const harmlessCount = sample.harmless_spans?.length ?? sample.harmless_count ?? 0;
    card.innerHTML = `
      <div class="sample-title">
        <strong>${escapeHtml(sample.difficulty_level ?? "-")} · 样例 ${index + 1}</strong>
        <span>${harmfulCount}H + ${harmlessCount}S</span>
      </div>
      <div class="sample-text example-text">${renderMarkedSampleText(sample)}</div>
      <div class="sample-meta example-meta">
        <span>${escapeHtml(sample.risk_category_id ?? "-")} · ${escapeHtml(sample.risk_category ?? "-")}</span>
        <code>${escapeHtml(sample.sample_id ?? "-")}</code>
      </div>
    `;
    nodes.exampleGallery.append(card);
  });
}

function switchMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  nodes.singleSettings.classList.toggle("active", mode === "single");
  nodes.batchSettings.classList.toggle("active", mode === "batch");
  if (mode === "single") {
    applyRunDefaults("dynamic_difficulty_ui_single");
  } else {
    applyRunDefaults("dynamic_difficulty_ui_batch");
  }
  renderConfig();
}

function applyRunDefaults(runId) {
  if (nodes.runId.value.startsWith("dynamic_difficulty_ui_")) {
    nodes.runId.value = runId;
    nodes.outputDir.value = `runs/${runId}`;
  }
}

async function checkApi() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    state.apiReady = Boolean(payload.ok);
    nodes.agentStatus.textContent = state.apiReady ? `后端已连接 · ${payload.active_jobs ?? 0} 个任务运行中` : "后端不可用";
    if (state.apiReady) {
      await loadGenerationOptions();
    }
    if (state.apiReady && !state.topics.length) {
      await loadSeedTopics();
    }
  } catch {
    state.apiReady = false;
    nodes.agentStatus.textContent = "静态模式：可导出配置，启动后端后可生成";
  }
  renderConfig();
}

async function loadGenerationOptions() {
  const response = await fetch("/api/generation/options", { cache: "no-store" });
  if (!response.ok) {
    return;
  }
  const payload = await response.json();
  state.skillVersions = payload.skill_versions ?? [];
  const current = nodes.skillVersion.value;
  nodes.skillVersion.replaceChildren();
  state.skillVersions.forEach((skill) => {
    const option = document.createElement("option");
    option.value = skill.path;
    option.textContent = skill.label;
    option.dataset.skillId = skill.id;
    option.dataset.supportsHarmfulSeedLibrary = String(Boolean(skill.supports_harmful_seed_library));
    nodes.skillVersion.append(option);
  });
  if ([...nodes.skillVersion.options].some((option) => option.value === current)) {
    nodes.skillVersion.value = current;
  }
}

function handleDataSourceModeChange() {
  if (nodes.dataSourceMode.value === "harmful_seed_library") {
    nodes.seedInputPath.value = "seed_data/harmful_zh_17class_v1";
  }
  loadSeedTopics();
  renderConfig();
}

async function loadSeedTopics() {
  if (!state.apiReady) {
    return;
  }
  try {
    const path = encodeURIComponent(nodes.seedInputPath.value.trim());
    const response = await fetch(`/api/seed-topics?path=${path}`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ?? `HTTP ${response.status}`);
    }
    state.topics = payload.topics ?? [];
    state.domains = payload.domains ?? [];
    state.selectedTopics = new Set(state.topics.map((topic) => topic.topic));
    renderTopicControls();
    renderConfig();
  } catch (error) {
    nodes.topicList.innerHTML = `<div class="empty-inline">Topic 读取失败：${escapeHtml(error.message)}</div>`;
  }
}

function renderTopicControls() {
  nodes.singleDomain.replaceChildren();
  state.domains.forEach((domain) => {
    const option = document.createElement("option");
    option.value = domain.domain;
    option.textContent = `${domain.domain} · H${domain.harmful_count}/S${domain.harmless_count}`;
    nodes.singleDomain.append(option);
  });

  nodes.topicList.replaceChildren();
  state.topics.forEach((topic) => {
    const label = document.createElement("label");
    label.className = "topic-item";
    label.innerHTML = `
      <input type="checkbox" value="${escapeHtml(topic.topic)}" checked>
      <span>
        <strong>${escapeHtml(topic.topic)}</strong>
        <small>${topic.domain_count} 个 subtopic · H${topic.harmful_count}/S${topic.harmless_count}</small>
      </span>
    `;
    const input = label.querySelector("input");
    input.addEventListener("change", () => {
      if (input.checked) {
        state.selectedTopics.add(topic.topic);
      } else {
        state.selectedTopics.delete(topic.topic);
      }
      renderConfig();
    });
    nodes.topicList.append(label);
  });
}

function setAllTopics(checked) {
  state.selectedTopics = new Set(checked ? state.topics.map((topic) => topic.topic) : []);
  nodes.topicList.querySelectorAll("input").forEach((input) => {
    input.checked = checked;
  });
  renderConfig();
}

function readConfig() {
  const runId = nodes.runId.value.trim() || (state.mode === "single" ? "dynamic_difficulty_ui_single" : "dynamic_difficulty_ui_batch");
  const outputDir = nodes.outputDir.value.trim() || `runs/${runId}`;
  const difficultyCounts = readDifficultyCounts();
  const total = sumCounts(difficultyCounts);
  if (total < 1) {
    throw new Error("生成数量必须大于 0");
  }
  const generation = {
    total_sample_count: total,
    resume: true,
    language: nodes.language.value.trim() || "zh",
    sample_mode: "paired_mixed",
    metric_targets: ["edit_success", "harmless_retention"],
    data_origin_modes: ["splice_constructed"],
    difficulty_sequence: DIFFICULTY_LEVELS,
    difficulty_counts: difficultyCounts,
  };
  const randomSeed = nodes.randomSeed.value.trim();
  if (randomSeed) {
    if (!/^\d+$/.test(randomSeed)) {
      throw new Error("随机种子必须是非负整数，留空则自动生成");
    }
    generation.random_seed = Number(randomSeed);
  }
  if (state.mode === "single") {
    const domain = nodes.singleDomain.value;
    if (domain) {
      generation.allowed_domains = [domain];
    }
  } else {
    const topics = Array.from(state.selectedTopics);
    if (!topics.length) {
      throw new Error("批量生成至少选择一个 topic");
    }
    generation.allowed_topics = topics;
  }

  const skill = selectedSkill();
  const dataSourceMode = nodes.dataSourceMode.value;

  const config = {
    run_id: runId,
    output_dir: outputDir,
    skill: {
      path: skill.path,
      fail_on_quality_error: true,
    },
    generation,
    llm_composer: {
      enabled: true,
      api_base: nodes.apiBase.value.trim(),
      api_key_env: nodes.apiKeyEnv.value.trim(),
      model: nodes.model.value.trim() || "Qwen3.5-9B",
      temperature: Number(nodes.temperature.value),
      top_p: 0.9,
      max_tokens: Number(nodes.maxTokens.value),
      timeout: Number(nodes.timeout.value),
      retries: 1,
      concurrency: Math.max(1, Number(nodes.composerConcurrency.value)),
      discard_retry_limit: Math.max(1, Number(nodes.discardRetryLimit.value)),
      bridge_review: {
        enabled: true,
        temperature: 0,
        max_tokens: 256,
      },
      chat_template_kwargs: {
        enable_thinking: false,
      },
    },
    llm: {
      enabled: false,
    },
    seed_generation: {
      enabled: false,
    },
  };
  if (dataSourceMode === "harmful_seed_library") {
    config.harmful_seed_library = {
      path: nodes.seedInputPath.value.trim(),
      sources: readSeedSources(),
      deduplicate: true,
    };
  } else {
    config.seed_input_path = nodes.seedInputPath.value.trim();
  }
  config.harmless_companion_generator = {
    api_base: nodes.apiBase.value.trim(),
    api_key_env: nodes.apiKeyEnv.value.trim(),
    model: nodes.model.value.trim() || "Qwen3.5-9B",
    temperature: Number(nodes.temperature.value),
    top_p: 0.9,
    max_tokens: Number(nodes.maxTokens.value),
    timeout: Number(nodes.timeout.value),
    retries: 2,
    max_attempts: 4,
    harmful_candidate_window: 10,
    min_chars: 24,
    max_chars: 260,
    chat_template_kwargs: {
      enable_thinking: false,
    },
    guard: {
      enabled: true,
      api_base: nodes.guardApiBase.value.trim(),
      api_key_env: nodes.apiKeyEnv.value.trim(),
      model: nodes.guardModel.value.trim() || "Qwen3Guard-Gen-4B",
      timeout: 120,
      retries: 2,
      chat_template_kwargs: {
        enable_thinking: false,
      },
    },
  };
  config.final_guard = {
    api_base: nodes.guardApiBase.value.trim(),
    api_key_env: nodes.apiKeyEnv.value.trim(),
    model: nodes.guardModel.value.trim() || "Qwen3Guard-Gen-4B",
    max_tokens: 64,
    timeout: 120,
    retries: 2,
    chat_template_kwargs: {
      enable_thinking: false,
    },
  };
  return config;
}

function selectedSkill() {
  const option = nodes.skillVersion.selectedOptions[0];
  return {
    id: option?.dataset.skillId ?? "dynamic_difficulty_question_generation_skill",
    path: nodes.skillVersion.value || "skills",
  };
}

function readSeedSources() {
  return nodes.seedSources.value
    .split(",")
    .map((source) => source.trim())
    .filter(Boolean);
}

function readDifficultyCounts() {
  if (state.mode === "single") {
    return Object.fromEntries(DIFFICULTY_LEVELS.map((level) => [level, level === nodes.singleLevel.value ? 1 : 0]));
  }
  return {
    H1: Math.max(0, Number(nodes.countH1.value)),
    H2: Math.max(0, Number(nodes.countH2.value)),
    H3: Math.max(0, Number(nodes.countH3.value)),
    H4: Math.max(0, Number(nodes.countH4.value)),
  };
}

function renderConfig() {
  try {
    const config = readConfig();
    const total = config.generation.total_sample_count;
    const topicCount = config.generation.allowed_topics?.length ?? config.generation.allowed_domains?.length ?? 0;
    const skillName = selectedSkill().id;
    nodes.configSummary.textContent = `${skillName} · ${state.mode === "single" ? "单条" : "批量"} · ${total} 条 · ${topicCount} 个 topic/domain`;
    nodes.batchTotalSummary.textContent = `${total} 条`;
    nodes.startJobButton.disabled = !state.apiReady;
    nodes.showConfigButton.disabled = false;
  } catch (error) {
    nodes.configSummary.textContent = "配置错误";
    nodes.batchTotalSummary.textContent = "-";
    nodes.startJobButton.disabled = true;
    nodes.showConfigButton.disabled = true;
  }
}

function showConfigDialog() {
  try {
    nodes.configPreview.textContent = JSON.stringify(readConfig(), null, 2);
  } catch (error) {
    nodes.configPreview.textContent = `配置错误：${error.message}`;
  }
  nodes.configDialog.showModal();
}

async function startJob() {
  let config;
  try {
    config = readConfig();
  } catch (error) {
    window.alert(`配置错误：${error.message}`);
    return;
  }
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
  state.activeJobId = null;
  state.agentTraceHasProgress = false;
  state.job = {
    job_id: config.run_id,
    status: "submitting",
    running: true,
    generated: 0,
    total: config.generation.total_sample_count,
    progress: 0,
    difficulty_level_counts: {},
    output_dir: config.output_dir,
    samples_path: `${config.output_dir}/samples.jsonl`,
    manifest: { discard_counts: {} },
    log_tail: ["提交任务中"],
    samples: [],
  };
  renderJob();
  nodes.startJobButton.disabled = true;
  nodes.agentStatus.textContent = "提交任务中";
  try {
    const response = await fetch("/api/generation/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ?? `HTTP ${response.status}`);
    }
    state.activeJobId = payload.job_id;
    state.job = payload;
    nodes.agentStatus.textContent = `任务已启动：${payload.job_id}`;
    renderJob();
    startPolling();
  } catch (error) {
    nodes.agentStatus.textContent = "任务启动失败";
    window.alert(`任务启动失败：${error.message}`);
  } finally {
    renderConfig();
  }
}

async function stopJob() {
  if (!state.activeJobId) {
    return;
  }
  const response = await fetch(`/api/generation/jobs/${state.activeJobId}/stop`, { method: "POST" });
  state.job = await response.json();
  renderJob();
}

async function resumeJob() {
  if (!state.activeJobId) {
    return;
  }
  const response = await fetch(`/api/generation/jobs/${state.activeJobId}/resume`, { method: "POST" });
  state.job = await response.json();
  renderJob();
  startPolling();
}

function startPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
  }
  state.pollTimer = window.setInterval(pollJob, 2000);
  pollJob();
}

async function pollJob() {
  if (!state.activeJobId) {
    return;
  }
  try {
    const response = await fetch(`/api/generation/jobs/${state.activeJobId}`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ?? `HTTP ${response.status}`);
    }
    state.job = payload;
    renderJob();
    if (!payload.running && ["completed", "failed", "stopped"].includes(payload.status)) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  } catch (error) {
    nodes.agentStatus.textContent = `进度读取失败：${error.message}`;
  }
}

function renderJob() {
  const job = state.job;
  nodes.samplePreview.replaceChildren();
  if (!job) {
    nodes.jobBadge.textContent = "未启动";
    nodes.progressFill.style.width = "0%";
    nodes.progressText.textContent = "0 / 0";
    nodes.jobStats.innerHTML = "";
    nodes.levelProgress.innerHTML = "";
    renderAgentTrace(null);
    nodes.logBox.textContent = "等待任务日志";
    nodes.resultSummary.textContent = "尚未生成";
    nodes.samplePreview.append(nodes.emptyTemplate.content.cloneNode(true));
    nodes.stopJobButton.disabled = true;
    nodes.resumeJobButton.disabled = true;
    nodes.downloadSamplesButton.disabled = true;
    return;
  }
  nodes.jobBadge.textContent = job.status;
  nodes.progressFill.style.width = `${Math.min(100, job.progress ?? 0)}%`;
  nodes.progressText.textContent = `${job.generated ?? 0} / ${job.total ?? 0} · ${job.progress ?? 0}%`;
  const discardCounts = {
    ...(job.manifest?.discard_counts ?? {}),
    ...(job.worker_state?.discard_counts ?? {}),
  };
  nodes.jobStats.innerHTML = `
    <div class="stat-card"><span>job_id</span><strong>${escapeHtml(job.job_id)}</strong></div>
    <div class="stat-card"><span>随机种子</span><strong>${escapeHtml(job.random_seed ?? "-")}</strong></div>
    <div class="stat-card"><span>适配丢弃</span><strong>${escapeHtml(discardCounts.pairing_review_rejected ?? 0)}</strong></div>
    <div class="stat-card"><span>衔接丢弃</span><strong>${escapeHtml(discardCounts.bridge_review_rejected ?? 0)}</strong></div>
    <div class="stat-card"><span>span 丢弃</span><strong>${escapeHtml(discardCounts.span_backfill_rejected ?? 0)}</strong></div>
    <div class="path-card"><span>输出目录</span><strong>${escapeHtml(job.output_dir)}</strong></div>
    <div class="path-card"><span>样本文件</span><strong>${escapeHtml(job.samples_path)}</strong></div>
  `;
  renderLevelProgress(job);
  renderAgentTrace(job.worker_state);
  nodes.logBox.textContent = (job.log_tail ?? []).join("\n") || "等待任务日志";
  nodes.resultSummary.textContent = `已完成 ${job.generated ?? 0} 条 · 显示最近 ${job.samples?.length ?? 0} 条`;
  nodes.stopJobButton.disabled = !job.running;
  nodes.resumeJobButton.disabled = job.running || job.status === "completed";
  nodes.downloadSamplesButton.disabled = !job.generated;
  (job.samples ?? []).forEach((sample) => {
    const item = document.createElement("article");
    item.className = "sample-item";
    item.innerHTML = `
      <div class="sample-title">
        <strong>${escapeHtml(sample.sample_id)}</strong>
        <span>${escapeHtml(sample.difficulty_level ?? "-")}</span>
      </div>
      <div class="source-legend">
        <span class="legend-chip harmful">原始有害</span>
        <span class="legend-chip harmless">原始无害</span>
      </div>
      <div class="sample-text">${renderMarkedSampleText(sample)}</div>
      <div class="sample-meta">
        <span>${sample.harmful_spans?.length ?? 0}H</span>
        <span>${sample.harmless_spans?.length ?? 0}S</span>
        <span>${escapeHtml(sample.domain ?? "-")}</span>
      </div>
    `;
    nodes.samplePreview.append(item);
  });
  if (!(job.samples ?? []).length) {
    nodes.samplePreview.append(nodes.emptyTemplate.content.cloneNode(true));
  }
}

function renderAgentTrace(workerState) {
  const sample = workerState?.active_sample;
  if (!workerState || !sample) {
    if (state.agentTraceHasProgress) {
      return;
    }
    nodes.agentTrace.innerHTML = `
      <div class="trace-empty">
        <strong>Agent 流水线</strong>
        <span>任务启动后，这里展示当前正在处理的一条样本。</span>
      </div>
    `;
    return;
  }
  state.agentTraceHasProgress = true;
  const selected = sample.selected_sources ?? [];
  const checks = sample.checks ?? [];
  nodes.agentTrace.innerHTML = `
    <div class="trace-head">
      <div>
        <strong>${escapeHtml(workerState.phase ?? "处理中")}</strong>
        <span>${escapeHtml(workerState.message ?? "")}</span>
      </div>
      <span>${escapeHtml(sample.sample_id ?? "-")} · ${escapeHtml(sample.difficulty_level ?? "-")}</span>
    </div>
    <div class="trace-grid">
      <div>
        <span>Topic / Subtopic</span>
        <strong>${escapeHtml(sample.domain ?? "-")}</strong>
      </div>
      <div>
        <span>样本序号</span>
        <strong>${escapeHtml(sample.global_index ?? sample.local_index ?? "-")}</strong>
      </div>
      <div>
        <span>重试轮次</span>
        <strong>${escapeHtml(sample.retry ?? 1)}</strong>
      </div>
    </div>
    <div class="trace-block">
      <h3>选中的 seed 片段</h3>
      ${selected.map(renderSelectedSource).join("") || "<p>等待选择候选片段</p>"}
    </div>
    <div class="trace-block">
      <h3>检查结果</h3>
      ${checks.map(renderCheck).join("") || "<p>等待审核结果</p>"}
    </div>
    ${renderBridgePreview(sample)}
  `;
}

function renderSelectedSource(source) {
  const kind = source.kind === "harmful" ? "harmful" : "harmless";
  const label = kind === "harmful" ? "原始有害" : "原始无害";
  return `
    <article class="trace-source ${kind}">
      <div><b>${label}</b><span>${escapeHtml(source.id ?? "-")}</span></div>
      <p>${escapeHtml(source.preview ?? "")}</p>
    </article>
  `;
}

function renderCheck(check) {
  const status = check.status === "rejected" ? "rejected" : check.status === "running" ? "running" : "passed";
  return `
    <div class="trace-check ${status}">
      <span>${escapeHtml(check.name ?? "检查")}</span>
      <strong>${escapeHtml(check.result ?? check.status ?? "-")}</strong>
    </div>
  `;
}

function renderBridgePreview(sample) {
  const bridges = sample.bridge_texts ?? [];
  const order = sample.source_order ?? [];
  const edits = sample.source_boundary_edits ?? [];
  if (!bridges.length && !order.length && !edits.length) {
    return "";
  }
  return `
    <div class="trace-block">
      <h3>模型拼接返回</h3>
      ${order.length ? `<p>顺序：${escapeHtml(order.join(" → "))}</p>` : ""}
      ${edits.length ? `<p>边界清理：${edits.map(renderBoundaryEdit).join(" ")}</p>` : ""}
      ${bridges.length ? `<p>桥接语：${bridges.map((text) => `「${escapeHtml(text)}」`).join(" ")}</p>` : ""}
    </div>
  `;
}

function renderBoundaryEdit(edit) {
  const action = edit.delete && edit.insert ? "替换" : edit.delete ? "删除" : "添加";
  return `${escapeHtml(edit.source_id ?? "-")} ${action}「${escapeHtml(edit.delete ?? "")}」→「${escapeHtml(edit.insert ?? "")}」`;
}

function renderMarkedSampleText(sample) {
  const text = String(sample.edited_input ?? "");
  const markers = [
    ...(sample.harmful_spans ?? []).map((span) => ({ ...span, kind: "harmful" })),
    ...(sample.harmless_spans ?? []).map((span) => ({ ...span, kind: "harmless" })),
  ]
    .map((span) => ({
      kind: span.kind,
      start: Number(span.start),
      end: Number(span.end),
    }))
    .filter((span) => Number.isFinite(span.start) && Number.isFinite(span.end) && span.end > span.start)
    .sort((left, right) => left.start - right.start || right.end - left.end);

  let cursor = 0;
  let html = "";
  for (const marker of markers) {
    const start = Math.max(cursor, Math.min(text.length, marker.start));
    const end = Math.max(start, Math.min(text.length, marker.end));
    if (end <= cursor) {
      continue;
    }
    html += escapeHtml(text.slice(cursor, start));
    html += `<span class="source-span ${marker.kind}">${escapeHtml(text.slice(start, end))}</span>`;
    cursor = end;
  }
  html += escapeHtml(text.slice(cursor));
  return html;
}

function renderLevelProgress(job) {
  const counts = job.difficulty_level_counts ?? {};
  const total = job.total || 0;
  nodes.levelProgress.innerHTML = DIFFICULTY_LEVELS.map((level) => {
    const value = counts[level] ?? 0;
    const width = total ? Math.min(100, (value / total) * 100) : 0;
    return `
      <div class="level-row">
        <span>${level}</span>
        <div><i style="width:${width}%"></i></div>
        <strong>${value}</strong>
      </div>
    `;
  }).join("");
}

function exportConfig() {
  try {
    const config = readConfig();
    downloadText(`${config.run_id}_generation_config.json`, JSON.stringify(config, null, 2), "application/json");
  } catch (error) {
    window.alert(`配置错误：${error.message}`);
  }
}

async function copyApi() {
  try {
    const config = readConfig();
    const body = JSON.stringify({ config }, null, 2);
    const origin = window.location.origin;
    const command = [
      `curl -X POST ${origin}/api/generation/jobs \\`,
      "  -H 'Content-Type: application/json' \\",
      `  -d '${body.replaceAll("'", "'\\''")}'`,
      "",
      `curl ${origin}/api/generation/jobs/${config.run_id}`,
      `curl -X POST ${origin}/api/generation/jobs/${config.run_id}/stop`,
      `curl -X POST ${origin}/api/generation/jobs/${config.run_id}/resume`,
    ].join("\n");
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(command);
        nodes.agentStatus.textContent = "API 调用已复制";
        return;
      } catch {
        // Fall through to manual copying when browser permissions reject clipboard access.
      }
    }
    nodes.apiCommandOutput.value = command;
    nodes.apiCommandDialog.showModal();
    nodes.apiCommandOutput.focus();
    nodes.apiCommandOutput.select();
    nodes.agentStatus.textContent = "请在弹窗中手动复制 API 调用";
  } catch (error) {
    window.alert(`无法复制 API：${error.message}`);
  }
}

async function downloadSamples() {
  if (!state.activeJobId) {
    return;
  }
  const response = await fetch(`/api/generation/jobs/${state.activeJobId}/samples`);
  const payload = await response.json();
  const lines = (payload.samples ?? []).map((sample) => JSON.stringify(sample)).join("\n") + "\n";
  downloadText(`${state.activeJobId}.jsonl`, lines, "application/x-ndjson");
}

function sumCounts(counts) {
  return DIFFICULTY_LEVELS.reduce((total, level) => total + (Number(counts[level]) || 0), 0);
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
