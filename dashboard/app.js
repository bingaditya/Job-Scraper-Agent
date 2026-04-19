const dashboardStatusEl = document.getElementById("dashboard-status");
const statsEl = document.getElementById("stats");
const jobGridEl = document.getElementById("job-grid");
const generatedAtEl = document.getElementById("generated-at");
const template = document.getElementById("job-card-template");

let API_BASE = "";

const state = {
  apiAvailable: false,
  applicationState: {},
  jobs: [],
  resumeMeta: null,
  summary: null,
  suggestionsById: new Map(),
  busyJobIds: new Set(),
};

async function loadDashboard() {
  const apiConfig = await fetchJson("api_config.json", {});
  API_BASE = (apiConfig.api_url || "").replace(/\/$/, "");

  state.apiAvailable = await detectApi();
  const [jobs, summary, suggestions, applicationState, resumeMeta] = await Promise.all([
    fetchJson("jobs.json", []),
    fetchJson("summary.json", null),
    fetchJson("resume_suggestions.json", []),
    fetchJson("resume_application_state.json", {}),
    state.apiAvailable ? fetchJson(`${API_BASE}/api/resume`, null) : Promise.resolve(null),
  ]);

  state.jobs = jobs;
  state.summary = summary;
  state.applicationState = applicationState ?? {};
  state.resumeMeta = resumeMeta;
  state.suggestionsById = new Map(
    (suggestions ?? []).map((item) => [item.job_id, item.resume_suggestion]),
  );

  renderDashboard();
}

async function detectApi() {
  try {
    const response = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

async function fetchJson(path, fallbackValue) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) {
      return fallbackValue;
    }
    return await response.json();
  } catch {
    return fallbackValue;
  }
}

function renderDashboard() {
  renderStatusBanner();
  renderStats(state.summary, state.jobs);
  renderJobs(state.jobs);
}

function renderStatusBanner() {
  if (!state.apiAvailable) {
    dashboardStatusEl.textContent =
      "Read-only dashboard mode. Start `python dashboard_server.py` to enable one-click resume tailoring.";
    return;
  }

  const resumePath = state.resumeMeta?.resume_path ?? "assets/resume.md";
  dashboardStatusEl.textContent =
    `Tailor Resume writes directly to ${resumePath} and saves a timestamped backup in assets/resume.backups/.`;
}

function renderStats(summary, jobs) {
  const appliedCount = Object.keys(state.applicationState ?? {}).length;
  const stats = [
    {
      label: "Shortlisted jobs",
      value: summary?.shortlisted_jobs ?? jobs.length,
    },
    {
      label: "New matches",
      value: summary?.new_jobs ?? 0,
    },
    {
      label: "Resume actions",
      value: appliedCount,
    },
    {
      label: "Threshold",
      value: summary ? `${summary.score_threshold}+` : "n/a",
    },
  ];

  statsEl.innerHTML = "";
  for (const stat of stats) {
    const card = document.createElement("div");
    card.className = "stat-card";
    card.innerHTML = `<strong>${stat.value}</strong><span>${stat.label}</span>`;
    statsEl.appendChild(card);
  }

  if (summary?.generated_at) {
    generatedAtEl.textContent = `Last run: ${new Date(summary.generated_at).toLocaleString()}`;
  }
}

function renderJobs(jobs) {
  jobGridEl.innerHTML = "";
  if (!jobs.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Run the agent to populate ranked jobs here.";
    jobGridEl.appendChild(empty);
    return;
  }

  jobs.forEach((rankedJob, index) => {
    const jobId = rankedJob.job.fingerprint;
    const suggestion = state.suggestionsById.get(jobId) ?? rankedJob.resume_suggestion ?? null;
    const applicationState = state.applicationState[jobId] ?? null;
    const isBusy = state.busyJobIds.has(jobId);

    const clone = template.content.cloneNode(true);
    clone.querySelector(".job-card").style.animationDelay = `${index * 70}ms`;
    clone.querySelector(".source-badge").textContent = rankedJob.job.source;
    clone.querySelector(".score-pill").textContent = `Job ${rankedJob.score}/100`;
    clone.querySelector(".resume-pill").textContent = applicationState
      ? `Resume ${applicationState.resume_fit_score}/100`
      : suggestion
        ? "Resume pending"
        : "No tailoring";
    clone.querySelector(".job-title").textContent = rankedJob.job.title;
    clone.querySelector(".company-line").textContent =
      `${rankedJob.job.company} - ${rankedJob.job.location}`;
    clone.querySelector(".reason-line").textContent =
      rankedJob.reasons?.[0] ?? "Scored by the profile matcher.";
    clone.querySelector(".tailor-line").textContent =
      suggestion?.summary ?? "No resume suggestion generated for this job yet.";
    clone.querySelector(".location").textContent = rankedJob.job.published_at
      ? new Date(rankedJob.job.published_at).toLocaleDateString()
      : "Recently posted";
    clone.querySelector(".apply-link").href = rankedJob.job.url;

    const tagList = clone.querySelector(".tag-list");
    const tags = rankedJob.matched_skills?.length
      ? rankedJob.matched_skills
      : rankedJob.job.tags ?? [];
    tags.slice(0, 4).forEach((tag) => {
      const pill = document.createElement("span");
      pill.className = "tag";
      pill.textContent = tag;
      tagList.appendChild(pill);
    });

    const resumeButton = clone.querySelector(".resume-button");
    const resumeStatus = clone.querySelector(".resume-status");
    const downloadButton = clone.querySelector(".download-button");
    resumeButton.textContent = isBusy
      ? "Tailoring..."
      : applicationState
        ? "Re-tailor Resume"
        : "Tailor Resume";
    resumeButton.disabled = isBusy || !state.apiAvailable || !suggestion;
    resumeButton.addEventListener("click", () => tailorResume(jobId));
    downloadButton.hidden = !state.apiAvailable || !applicationState;
    downloadButton.addEventListener("click", () => downloadResume());

    if (!state.apiAvailable) {
      resumeStatus.textContent = "Start dashboard_server.py to enable resume updates.";
    } else if (!suggestion) {
      resumeStatus.textContent = "This job has no stored tailoring suggestion.";
    } else if (applicationState) {
      resumeStatus.textContent =
        `Updated ${new Date(applicationState.applied_at).toLocaleString()} - keyword coverage ${applicationState.resume_fit_score}%.`;
    } else {
      resumeStatus.textContent = "Writes to assets/resume.md and creates a backup.";
    }

    jobGridEl.appendChild(clone);
  });
}

async function tailorResume(jobId) {
  if (!state.apiAvailable || state.busyJobIds.has(jobId)) {
    return;
  }

  state.busyJobIds.add(jobId);
  renderJobs(state.jobs);

  try {
    const response = await fetch(`${API_BASE}/api/tailor-resume`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ job_id: jobId }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ?? "Resume tailoring failed.");
    }
    state.applicationState[jobId] = payload;
    state.resumeMeta = await fetchJson(`${API_BASE}/api/resume`, state.resumeMeta);
    renderStatusBanner();
    renderStats(state.summary, state.jobs);
  } catch (error) {
    dashboardStatusEl.textContent = error.message;
  } finally {
    state.busyJobIds.delete(jobId);
    renderJobs(state.jobs);
  }
}

async function downloadResume() {
  try {
    const response = await fetch(`${API_BASE}/api/resume/download`);
    if (!response.ok) throw new Error("Resume download failed.");
    const text = await response.text();
    const blob = new Blob([text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "resume.md";
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    dashboardStatusEl.textContent = error.message;
  }
}

loadDashboard();
