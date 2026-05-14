// Deno Deploy Webhook — AI DevOps System
// Версия: v4.4 | BEM-409
// Изменения:
//   - BEM-409: GET /gpt-safe-run  — PUBLIC, allowlist-only, без token
//   - BEM-409: GET /gpt-safe-status — PUBLIC, read-only статус сессии
//   - BEM-402 FIX: initDevSession больше не диспатчит step одновременно с init
//   - Rate limit: in-memory + проверка активной сессии через GitHub API
//
// ENDPOINTS:
// GET  /                           — health check
// POST /                           — Telegram webhook
// POST /autonomy                   — trigger engine (JSON body)
// GET  /autonomy-trigger           — trigger engine (query params, token required)
// GET  /autonomy-backlog-trigger   — backlog + trigger (token required)
// POST /autonomy-backlog           — backlog + trigger (token required)
// GET  /gpt-dev-session            — статус dev сессии (token required)
// POST /gpt-dev-session            — инициировать dev сессию (token required, Deno fallback)
// GET  /gpt-safe-run               — PUBLIC: запустить GPT Dev Runner (allowlist-only, no token)
// GET  /gpt-safe-status            — PUBLIC: статус текущей сессии (read-only)

const GITHUB_REPO   = Deno.env.get("GITHUB_REPO")    || "bereznyi-aleksandr/ai-devops-system";
const GITHUB_ISSUE  = 31;
const ALLOWED_CHAT_ID = Deno.env.get("ALLOWED_CHAT_ID") || "601442777";
const GITHUB_API    = "https://api.github.com";

// Allowlist для публичного /gpt-safe-run
const SAFE_RUN_PRESETS = new Set(["developer_runner_selftest", "fix_internal_contour", "status"]);
const SAFE_RUN_MODES   = new Set(["init", "step", "status"]);
const SAFE_TRACE_RE    = /^[a-zA-Z0-9_]{1,60}$/;
const RATE_LIMIT_MS    = 60_000; // 60 секунд между запусками (in-memory)

// In-memory rate limiter (сбрасывается при cold start, но cold starts редки)
let lastSafeRunAt = 0;
let lastSafeRunTrace = null;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, x-gpt-secret, Authorization",
};

function corsJson(body, status = 200) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
  });
}

function checkGptToken(gptSecret, provided) {
  if (!gptSecret) return true;
  return provided === gptSecret;
}

// ─── GitHub API helpers ─────────────────────────────────────────────────────

async function ghRequest(pat, method, path, body) {
  const resp = await fetch(`${GITHUB_API}${path}`, {
    method,
    headers: {
      "Authorization":  `Bearer ${pat}`,
      "Accept":         "application/vnd.github+json",
      "Content-Type":   "application/json",
      "User-Agent":     "ai-devops-deno-webhook"
    },
    body: body ? JSON.stringify(body) : undefined
  });
  return resp;
}

async function postGitHubComment(pat, body) {
  const resp = await ghRequest(pat, "POST",
    `/repos/${GITHUB_REPO}/issues/${GITHUB_ISSUE}/comments`, { body });
  return resp.status;
}

async function triggerRepositoryDispatch(pat, eventType, payload) {
  const resp = await ghRequest(pat, "POST",
    `/repos/${GITHUB_REPO}/dispatches`,
    { event_type: eventType, client_payload: payload });
  return resp.status;
}

async function getFileContents(pat, filePath) {
  const resp = await ghRequest(pat, "GET",
    `/repos/${GITHUB_REPO}/contents/${filePath}`, null);
  if (resp.status === 404) return null;
  return await resp.json();
}

async function updateFileContents(pat, filePath, content, message, sha) {
  const encoded = btoa(unescape(encodeURIComponent(content)));
  const body = { message, content: encoded };
  if (sha) body.sha = sha;
  const resp = await ghRequest(pat, "PUT",
    `/repos/${GITHUB_REPO}/contents/${filePath}`, body);
  return resp.status;
}

async function sendTelegram(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ chat_id: chatId, text, parse_mode: "Markdown" })
  });
}

// ─── JSON helpers ───────────────────────────────────────────────────────────

function decodeGitHubFile(fileData) {
  if (!fileData?.content) return null;
  try {
    const raw = decodeURIComponent(escape(atob(fileData.content.replace(/\n/g, ""))));
    return JSON.parse(raw);
  } catch { return null; }
}

async function readJsonFile(pat, path, defaultVal = null) {
  const fd = await getFileContents(pat, path);
  return decodeGitHubFile(fd) || defaultVal;
}

// ─── Session / Lock helpers ─────────────────────────────────────────────────

async function getDevSession(pat) {
  const fd = await getFileContents(pat, "governance/state/gpt_dev_session.json");
  const data = decodeGitHubFile(fd);
  if (!data) return null;
  return { data, sha: fd?.sha };
}

async function getLock(pat) {
  return await readJsonFile(pat, "governance/state/gpt_dev_lock.json", { locked: false });
}

async function getLastEvent(pat) {
  const fd = await getFileContents(pat, "governance/events/gpt_dev_runner.jsonl");
  if (!fd?.content) return null;
  try {
    const raw = decodeURIComponent(escape(atob(fd.content.replace(/\n/g, ""))));
    const lines = raw.trim().split("\n").filter(Boolean);
    if (!lines.length) return null;
    return JSON.parse(lines[lines.length - 1]);
  } catch { return null; }
}

// ─── Emergency stop check ───────────────────────────────────────────────────

async function checkEmergencyStop(pat) {
  const es = await readJsonFile(pat, "governance/state/emergency_stop.json", { enabled: false });
  if (es?.enabled) return es.reason || "emergency_stop_active";
  return null;
}

// ─── Presets ────────────────────────────────────────────────────────────────

function buildFullChainPreset(traceId) {
  const safeTrace = traceId.replace(/[^a-zA-Z0-9]/g, "_").slice(0, 24);
  return [
    {
      task_id: `TC_${safeTrace}_001_JSON`,
      title: `IC-A proof: create JSON state [${safeTrace}]`,
      status: "pending",
      template: "create_json_state",
      target_path: `governance/state/test_ic_a_${safeTrace}_001.json`,
      commit_message: `IC-A-001: JSON state proof [${safeTrace}]`,
      content: { version: 1, test_id: `TC_${safeTrace}_001_JSON`, trace: traceId, status: "created_by_autonomous_engine" }
    },
    {
      task_id: `TC_${safeTrace}_002_EVENT`,
      title: `IC-A proof: append event [${safeTrace}]`,
      status: "pending",
      template: "append_event",
      target_path: "governance/events/full_chain_autonomy_test.jsonl",
      commit_message: `IC-A-002: event append proof [${safeTrace}]`,
      content: { event: "IC_A_AUTONOMY_PROOF", trace: traceId, status: "created_by_autonomous_engine" }
    },
    {
      task_id: `TC_${safeTrace}_003_JSON`,
      title: `IC-A proof: create second JSON state [${safeTrace}]`,
      status: "pending",
      template: "create_json_state",
      target_path: `governance/state/test_ic_a_${safeTrace}_003.json`,
      commit_message: `IC-A-003: second JSON state proof [${safeTrace}]`,
      content: { version: 1, test_id: `TC_${safeTrace}_003_JSON`, trace: traceId, status: "created_by_autonomous_engine" }
    }
  ];
}

// ─── Backlog logic ──────────────────────────────────────────────────────────

function decodeTasksB64(b64) {
  const standard = b64.replace(/-/g, "+").replace(/_/g, "/");
  const padded = standard + "=".repeat((4 - standard.length % 4) % 4);
  return JSON.parse(decodeURIComponent(escape(atob(padded))));
}

async function processBacklog(pat, tasks, traceId, mode) {
  const fileData = await getFileContents(pat, "governance/state/roadmap_state.json");
  let roadmap = { version: 1, tasks: [], blocker: null };
  let sha = undefined;
  if (fileData?.content) {
    const raw = decodeURIComponent(escape(atob(fileData.content.replace(/\n/g, ""))));
    roadmap = JSON.parse(raw);
    sha = fileData.sha;
  }
  const existingIds = new Map(roadmap.tasks.map((t) => [t.task_id, t]));
  const addedIds = [];
  for (const task of tasks) {
    const existing = existingIds.get(task.task_id);
    if (existing) {
      if (existing.status !== "completed") { Object.assign(existing, task); addedIds.push(task.task_id); }
    } else {
      roadmap.tasks.push({ ...task, status: task.status || "pending" });
      addedIds.push(task.task_id);
    }
  }
  roadmap.updated_at = new Date().toISOString();
  roadmap.cursor = tasks[tasks.length - 1]?.task_id || roadmap.cursor;
  roadmap.blocker = null;
  const content = JSON.stringify(roadmap, null, 2) + "\n";
  const commitStatus = await updateFileContents(pat, "governance/state/roadmap_state.json", content,
    `IC-A: enqueue backlog trace=${traceId}`, sha);
  const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
    mode, trace_id: traceId, add_internal_tasks: false,
    source: "deno_backlog_gateway", backlog_tasks: addedIds, timestamp: new Date().toISOString()
  });
  return { commitStatus, dispatchStatus, addedIds };
}

// ─── GPT Dev Session (Deno fallback — BEM-402 contract) ────────────────────

async function initDevSessionSafe(pat, traceId, preset) {
  // BEM-402 FIX: dispatch ТОЛЬКО init.
  // First step запускается ТОЛЬКО после commit init state внутри workflow.
  // Запрещено: одновременный dispatch init + step.
  const dispatchStatus = await triggerRepositoryDispatch(pat, "gpt-dev-runner", {
    mode:      "init",
    trace_id:  traceId,
    preset:    preset || "developer_runner_selftest",
    source:    "deno_gpt_dev_session_fallback",
    timestamp: new Date().toISOString()
  });
  if (dispatchStatus !== 204) {
    return { ok: false, error: `dispatch failed: HTTP ${dispatchStatus}`, dispatch_status: dispatchStatus };
  }
  return {
    ok:              true,
    trace_id:        traceId,
    preset:          preset || "developer_runner_selftest",
    init_dispatch:   dispatchStatus,
    step_dispatch:   "pending_after_commit",  // first step запустится из workflow после commit
    source:          "deno_fallback",
    message:         "Init dispatched. First step will auto-start after workflow commits init state."
  };
}

// ─── /gpt-safe-run handler ──────────────────────────────────────────────────

async function handleSafeRun(pat, url) {
  const now = Date.now();

  // 1. Validate preset
  const preset  = (url.searchParams.get("preset") || "").trim();
  const traceRaw = (url.searchParams.get("trace_id") || "").trim();
  const modeRaw  = (url.searchParams.get("mode") || "init").trim();

  if (!preset || !SAFE_RUN_PRESETS.has(preset)) {
    return corsJson({
      ok:    false,
      error: "invalid_preset",
      detail: `preset must be one of: ${[...SAFE_RUN_PRESETS].join(", ")}`,
      preset_received: preset || "(empty)"
    }, 400);
  }

  // Special: preset=status → just return session status
  if (preset === "status") {
    const session = await getDevSession(pat);
    const lock    = await getLock(pat);
    return corsJson({ ok: true, session: session?.data || null, lock });
  }

  // 2. Validate trace_id
  const traceId = traceRaw || `safe_${Date.now()}`;
  if (traceRaw && !SAFE_TRACE_RE.test(traceRaw)) {
    return corsJson({
      ok:    false,
      error: "invalid_trace_id",
      detail: "trace_id must match [a-zA-Z0-9_]{1,60}"
    }, 400);
  }

  // 3. Emergency stop check
  const stopReason = await checkEmergencyStop(pat);
  if (stopReason) {
    return corsJson({
      ok:     false,
      error:  "emergency_stop",
      reason: stopReason,
      detail: "System emergency stop is active. Set emergency_stop.json enabled=false to resume."
    }, 503);
  }

  // 4. Check active session (duplicate-run guard via GitHub state)
  const session = await getDevSession(pat);
  if (session?.data) {
    const s = session.data;
    if (s.trace_id === traceId && s.status === "completed") {
      // Completed — OK, tell caller and don't re-run
      return corsJson({
        ok:      true,
        already: "completed",
        trace_id: traceId,
        session: s,
        message: "Session already completed. Use a different trace_id to start a new run."
      });
    }
    if (s.status === "queued" || s.status === "running") {
      return corsJson({
        ok:      false,
        error:   "session_active",
        detail:  `Active session exists: trace=${s.trace_id} status=${s.status}. Wait for completion or use /gpt-safe-status.`,
        session: { trace_id: s.trace_id, status: s.status, cursor: s.cursor, updated_at: s.updated_at }
      }, 429);
    }
  }

  // 5. In-memory rate limit (60s cooldown)
  const elapsed = now - lastSafeRunAt;
  if (lastSafeRunAt > 0 && elapsed < RATE_LIMIT_MS) {
    const waitSec = Math.ceil((RATE_LIMIT_MS - elapsed) / 1000);
    return corsJson({
      ok:     false,
      error:  "rate_limited",
      detail: `Please wait ${waitSec}s before next safe-run.`,
      retry_after_seconds: waitSec
    }, 429);
  }

  // 6. Dispatch init (ONLY init — first step via workflow handoff)
  const dispatchStatus = await triggerRepositoryDispatch(pat, "gpt-dev-runner", {
    mode:      "init",
    preset,
    trace_id:  traceId,
    source:    "deno_gpt_safe_run",
    timestamp: new Date().toISOString()
  });

  if (dispatchStatus !== 204) {
    return corsJson({
      ok:              false,
      error:           "dispatch_failed",
      dispatch_status: dispatchStatus,
      detail:          `GitHub dispatch returned HTTP ${dispatchStatus}`
    }, 500);
  }

  // Update in-memory rate limit
  lastSafeRunAt    = now;
  lastSafeRunTrace = traceId;

  return corsJson({
    ok:              true,
    trace_id:        traceId,
    preset,
    dispatch_status: dispatchStatus,
    source:          "deno_gpt_safe_run",
    message:         "Init dispatched. First step will auto-start after workflow commits init state. Use /gpt-safe-status to monitor.",
    monitor_url:     `/gpt-safe-status?trace_id=${traceId}`
  });
}

// ─── /gpt-safe-status handler ───────────────────────────────────────────────

async function handleSafeStatus(pat, url) {
  const traceId = (url.searchParams.get("trace_id") || "").trim();

  const session   = await getDevSession(pat);
  const lock      = await getLock(pat);
  const lastEvent = await getLastEvent(pat);

  const s = session?.data || null;

  // Check proof file if trace_id given
  let proofExists = null;
  if (traceId && s) {
    const proofPath = `governance/state/gpt_dev_runner_selftest_${traceId}.json`;
    const proofFd   = await getFileContents(pat, proofPath);
    proofExists = proofFd !== null;
  }

  return corsJson({
    ok: true,
    session: s,
    lock,
    last_event:   lastEvent,
    proof_exists: proofExists,
    blocker:      s?.blocker || null,
    status_summary: s ? {
      trace_id:   s.trace_id,
      status:     s.status,
      cursor:     s.cursor,
      queue_len:  (s.queue || []).length,
      updated_at: s.updated_at,
      blocker:    s.blocker
    } : null
  });
}

// ─── Main handler ───────────────────────────────────────────────────────────

Deno.serve(async (req) => {
  const pat           = Deno.env.get("GITHUB_PAT");
  const token         = Deno.env.get("TELEGRAM_BOT_TOKEN");
  const telegramSecret = Deno.env.get("TELEGRAM_WEBHOOK_SECRET");
  const gptSecret     = Deno.env.get("GPT_WEBHOOK_SECRET");

  const url    = new URL(req.url);
  const method = req.method;

  if (method === "OPTIONS") return new Response(null, { status: 204, headers: CORS_HEADERS });

  // ─── HEALTH CHECK ──────────────────────────────────────────────────────────
  if (method === "GET" && url.pathname === "/") {
    return corsJson({
      ok: true, service: "ai-devops-telegram-curator-webhook",
      repo: GITHUB_REPO, issue: GITHUB_ISSUE, version: "4.4",
      github_pat_present: !!pat, gpt_webhook_secret_present: !!gptSecret,
      endpoints: {
        "GET  /":                      "health check",
        "POST /":                      "Telegram webhook",
        "POST /autonomy":              "trigger engine (JSON body, token required)",
        "GET  /autonomy-trigger":      "trigger engine (query, token required)",
        "GET  /autonomy-backlog-trigger": "backlog + trigger (token required)",
        "POST /autonomy-backlog":      "backlog + trigger (token required)",
        "GET  /gpt-dev-session":       "GPT dev session status (token required)",
        "POST /gpt-dev-session":       "init GPT dev session — Deno fallback (token required)",
        "GET  /gpt-safe-run":          "PRIMARY GPT ENTRYPOINT — no token, allowlist-only preset",
        "GET  /gpt-safe-status":       "session status — no token, read-only"
      },
      safe_run_presets: [...SAFE_RUN_PRESETS],
      rate_limit_seconds: RATE_LIMIT_MS / 1000
    });
  }

  // ─── GET /gpt-safe-run — PUBLIC PRIMARY ENTRYPOINT (BEM-409) ───────────
  if (method === "GET" && url.pathname === "/gpt-safe-run") {
    if (!pat) return corsJson({ ok: false, error: "server_not_configured" }, 503);
    return await handleSafeRun(pat, url);
  }

  // ─── GET /gpt-safe-status — PUBLIC READ-ONLY (BEM-409) ─────────────────
  if (method === "GET" && url.pathname === "/gpt-safe-status") {
    if (!pat) return corsJson({ ok: false, error: "server_not_configured" }, 503);
    return await handleSafeStatus(pat, url);
  }

  // ─── GET /gpt-dev-session — статус dev сессии (token required) ─────────
  if (method === "GET" && url.pathname === "/gpt-dev-session") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) return corsJson({ ok: false, error: "Forbidden" }, 403);
    const session = await getDevSession(pat);
    if (!session) return corsJson({ ok: false, error: "Session not found" }, 404);
    return corsJson({ ok: true, session: session.data });
  }

  // ─── POST /gpt-dev-session — Deno fallback (token required, BEM-402 fixed) ─
  if (method === "POST" && url.pathname === "/gpt-dev-session") {
    const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization") || "";
    if (!checkGptToken(gptSecret, authHeader.replace("Bearer ", "")))
      return corsJson({ ok: false, error: "Forbidden" }, 403);
    let body;
    try { body = await req.json(); } catch { return corsJson({ ok: false, error: "Invalid JSON" }, 400); }
    const traceId = body.trace_id || ("gds_" + Date.now());
    const preset  = body.preset || "developer_runner_selftest";
    if (!SAFE_RUN_PRESETS.has(preset)) {
      return corsJson({ ok: false, error: "invalid_preset", preset_received: preset }, 400);
    }
    const result = await initDevSessionSafe(pat, traceId, preset);
    return corsJson(result, result.ok ? 200 : 500);
  }

  // ─── GET /autonomy-trigger ─────────────────────────────────────────────────
  if (method === "GET" && url.pathname === "/autonomy-trigger") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) return corsJson({ ok: false, error: "Forbidden" }, 403);
    const mode    = url.searchParams.get("mode") || "production_loop";
    const traceId = url.searchParams.get("trace_id") || ("auto_" + Date.now());
    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode, trace_id: traceId,
      add_internal_tasks: url.searchParams.get("add_internal_tasks") === "true",
      source: "deno_get_trigger", timestamp: new Date().toISOString()
    });
    const ok = dispatchStatus === 204;
    return corsJson({ ok, event_type: "autonomy-engine", mode, trace_id: traceId, dispatch_status: dispatchStatus }, ok ? 200 : 500);
  }

  // ─── GET /autonomy-backlog-trigger ─────────────────────────────────────────
  if (method === "GET" && url.pathname === "/autonomy-backlog-trigger") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) return corsJson({ ok: false, error: "Forbidden" }, 403);
    const mode    = url.searchParams.get("mode") || "production_loop";
    const traceId = url.searchParams.get("trace_id") || ("bl_" + Date.now());
    const preset  = url.searchParams.get("preset");
    let tasks;
    if (preset === "full_chain") {
      tasks = buildFullChainPreset(traceId);
    } else {
      const tasksB64 = url.searchParams.get("tasks_b64");
      if (!tasksB64) return corsJson({ ok: false, error: "preset=full_chain or tasks_b64 required" }, 400);
      try { const d = decodeTasksB64(tasksB64); tasks = d.tasks; if (!Array.isArray(tasks) || !tasks.length) throw new Error("empty"); }
      catch (e) { return corsJson({ ok: false, error: "Invalid tasks_b64: " + e.message }, 400); }
    }
    const { commitStatus, dispatchStatus, addedIds } = await processBacklog(pat, tasks, traceId, mode);
    const ok = (commitStatus === 200 || commitStatus === 201) && dispatchStatus === 204;
    return corsJson({ ok, trace_id: traceId, mode, preset: preset || "custom", roadmap_commit_status: commitStatus, dispatch_status: dispatchStatus, tasks_added: addedIds, tasks_count: addedIds.length }, ok ? 200 : 500);
  }

  // ─── POST /autonomy-backlog ────────────────────────────────────────────────
  if (method === "POST" && url.pathname === "/autonomy-backlog") {
    const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization") || "";
    if (!checkGptToken(gptSecret, authHeader.replace("Bearer ", ""))) return corsJson({ ok: false, error: "Forbidden" }, 403);
    let body; try { body = await req.json(); } catch { return corsJson({ ok: false, error: "Invalid JSON" }, 400); }
    const mode    = body.mode || "production_loop";
    const traceId = body.trace_id || ("bl_post_" + Date.now());
    const preset  = body.preset;
    let tasks;
    if (preset === "full_chain") { tasks = buildFullChainPreset(traceId); }
    else { tasks = body.tasks; if (!Array.isArray(tasks) || !tasks.length) return corsJson({ ok: false, error: "tasks required or use preset=full_chain" }, 400); }
    const { commitStatus, dispatchStatus, addedIds } = await processBacklog(pat, tasks, traceId, mode);
    const ok = (commitStatus === 200 || commitStatus === 201) && dispatchStatus === 204;
    return corsJson({ ok, trace_id: traceId, mode, roadmap_commit_status: commitStatus, dispatch_status: dispatchStatus, tasks_added: addedIds, tasks_count: addedIds.length }, ok ? 200 : 500);
  }

  // ─── POST /autonomy ────────────────────────────────────────────────────────
  if (method === "POST" && url.pathname === "/autonomy") {
    const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization") || "";
    if (!checkGptToken(gptSecret, authHeader.replace("Bearer ", ""))) return corsJson({ ok: false, error: "Forbidden" }, 403);
    let body; try { body = await req.json(); } catch { return corsJson({ ok: false, error: "Invalid JSON" }, 400); }
    const mode    = body.mode || "production_loop";
    const traceId = body.trace_id || ("post_" + Date.now());
    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode, trace_id: traceId, add_internal_tasks: body.add_internal_tasks || false,
      source: "deno_post_autonomy", timestamp: new Date().toISOString()
    });
    const ok = dispatchStatus === 204;
    return corsJson({ ok, mode, trace_id: traceId, dispatch_status: dispatchStatus }, ok ? 200 : 500);
  }

  // ─── POST / — TELEGRAM WEBHOOK ────────────────────────────────────────────
  if (method === "POST" && url.pathname === "/") {
    if (telegramSecret) {
      const secretHeader = req.headers.get("x-telegram-bot-api-secret-token");
      if (secretHeader !== telegramSecret) return new Response("Forbidden", { status: 403 });
    }
    let body; try { body = await req.json(); } catch { return new Response("Bad Request", { status: 400 }); }
    const message = body?.message;
    if (!message) return new Response("OK");
    const chatId    = String(message.chat?.id);
    const messageId = String(message.message_id);
    const text      = (message.text || "").trim();
    if (chatId !== ALLOWED_CHAT_ID) return new Response("Forbidden", { status: 403 });
    const now = new Date().toLocaleTimeString("uk-UA", { timeZone: "Europe/Kiev", hour: "2-digit", minute: "2-digit" });
    const dedupeKey = `telegram:${chatId}:${messageId}`;
    const curatorComment = `@curator\n\nTYPE: OPERATOR_TO_CURATOR\nSOURCE: telegram\nDEDUP_KEY: ${dedupeKey}\n\n\`\`\`json\n{\n  "chat_id": "${chatId}",\n  "message_id": "${messageId}",\n  "text": ${JSON.stringify(text)}\n}\n\`\`\``;
    const status = await postGitHubComment(pat, curatorComment);
    if (status === 201) { await sendTelegram(token, chatId, `📨 *${now} UA* | Отправлено куратору:\n_${text.slice(0, 100)}_`); }
    else { await sendTelegram(token, chatId, `❌ *${now} UA* | Ошибка (HTTP ${status})`); }
    return new Response("OK");
  }

  return corsJson({ ok: false, error: "Not Found" }, 404);
});
