// Deno Deploy Webhook — AI DevOps System
// Версия: v4.3 | BEM-395
// Добавлены: GET /gpt-dev-session, POST /gpt-dev-session
//
// ENDPOINTS:
// GET  /                           — health check
// POST /                           — Telegram webhook
// POST /autonomy                   — trigger engine (JSON body)
// GET  /autonomy-trigger           — trigger engine (query params)
// GET  /autonomy-backlog-trigger   — backlog + trigger (?preset=full_chain или tasks_b64)
// POST /autonomy-backlog           — backlog + trigger (JSON body)
// GET  /gpt-dev-session            — статус dev сессии
// POST /gpt-dev-session            — инициировать dev сессию и запустить runner

const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "bereznyi-aleksandr/ai-devops-system";
const GITHUB_ISSUE = 31;
const ALLOWED_CHAT_ID = Deno.env.get("ALLOWED_CHAT_ID") || "601442777";
const GITHUB_API = "https://api.github.com";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
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

// ─── GitHub API helpers ────────────────────────────────────────────────────

async function ghRequest(pat, method, path, body) {
  const resp = await fetch(`${GITHUB_API}${path}`, {
    method,
    headers: {
      "Authorization": `Bearer ${pat}`,
      "Accept": "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "ai-devops-deno-webhook"
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
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: "Markdown" })
  });
}

// ─── Presets ──────────────────────────────────────────────────────────────

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

// ─── Backlog logic ─────────────────────────────────────────────────────────

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
  const commitStatus = await updateFileContents(pat, "governance/state/roadmap_state.json", content, `IC-A: enqueue backlog trace=${traceId}`, sha);
  const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
    mode, trace_id: traceId, add_internal_tasks: false,
    source: "deno_backlog_gateway", backlog_tasks: addedIds, timestamp: new Date().toISOString()
  });
  return { commitStatus, dispatchStatus, addedIds };
}

// ─── GPT Dev Session logic ─────────────────────────────────────────────────

async function getDevSession(pat) {
  const fileData = await getFileContents(pat, "governance/state/gpt_dev_session.json");
  if (!fileData?.content) return null;
  try {
    const raw = decodeURIComponent(escape(atob(fileData.content.replace(/\n/g, ""))));
    return { data: JSON.parse(raw), sha: fileData.sha };
  } catch { return null; }
}

async function initDevSession(pat, traceId, preset) {
  // Инициализируем через gpt-dev-runner workflow
  const dispatchStatus = await triggerRepositoryDispatch(pat, "gpt-dev-runner", {
    mode: "init",
    trace_id: traceId,
    preset: preset || "developer_runner_selftest",
    source: "deno_gpt_dev_session",
    timestamp: new Date().toISOString()
  });
  if (dispatchStatus !== 204) return { ok: false, error: `dispatch failed: HTTP ${dispatchStatus}` };

  // Сразу запустить первый шаг
  const stepStatus = await triggerRepositoryDispatch(pat, "gpt-dev-runner", {
    mode: "step",
    trace_id: traceId,
    source: "deno_gpt_dev_session_autostart",
    timestamp: new Date().toISOString()
  });
  return {
    ok: true,
    trace_id: traceId,
    preset: preset || "developer_runner_selftest",
    init_dispatch: dispatchStatus,
    step_dispatch: stepStatus,
    message: "Dev session initiated. Runner will execute one atomic step per dispatch."
  };
}

// ─── Main handler ──────────────────────────────────────────────────────────

Deno.serve(async (req) => {
  const pat = Deno.env.get("GITHUB_PAT");
  const token = Deno.env.get("TELEGRAM_BOT_TOKEN");
  const telegramSecret = Deno.env.get("TELEGRAM_WEBHOOK_SECRET");
  const gptSecret = Deno.env.get("GPT_WEBHOOK_SECRET");

  const url = new URL(req.url);
  const method = req.method;

  if (method === "OPTIONS") return new Response(null, { status: 204, headers: CORS_HEADERS });

  // ─── HEALTH CHECK ────────────────────────────────────────────────────────
  if (method === "GET" && url.pathname === "/") {
    return corsJson({
      ok: true, service: "ai-devops-telegram-curator-webhook",
      repo: GITHUB_REPO, issue: GITHUB_ISSUE, version: "4.3",
      github_pat_present: !!pat, gpt_webhook_secret_present: !!gptSecret,
      endpoints: {
        "GET  /": "health check",
        "POST /": "Telegram webhook",
        "POST /autonomy": "trigger engine (JSON body)",
        "GET  /autonomy-trigger": "trigger engine (query params)",
        "GET  /autonomy-backlog-trigger": "backlog + trigger (?preset=full_chain или tasks_b64)",
        "POST /autonomy-backlog": "backlog + trigger (JSON body)",
        "GET  /gpt-dev-session": "GPT dev session status",
        "POST /gpt-dev-session": "init GPT dev session + start runner"
      }
    });
  }

  // ─── GET /gpt-dev-session — статус dev сессии ─────────────────────────
  if (method === "GET" && url.pathname === "/gpt-dev-session") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) return corsJson({ ok: false, error: "Forbidden" }, 403);
    const session = await getDevSession(pat);
    if (!session) return corsJson({ ok: false, error: "Session not found" }, 404);
    return corsJson({ ok: true, session: session.data });
  }

  // ─── POST /gpt-dev-session — инициировать dev сессию ─────────────────
  if (method === "POST" && url.pathname === "/gpt-dev-session") {
    const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization") || "";
    if (!checkGptToken(gptSecret, authHeader.replace("Bearer ", "")))
      return corsJson({ ok: false, error: "Forbidden" }, 403);
    let body;
    try { body = await req.json(); } catch { return corsJson({ ok: false, error: "Invalid JSON" }, 400); }
    const traceId = body.trace_id || ("gds_" + Date.now());
    const preset = body.preset || "developer_runner_selftest";
    const result = await initDevSession(pat, traceId, preset);
    return corsJson(result, result.ok ? 200 : 500);
  }

  // ─── GET /autonomy-trigger ───────────────────────────────────────────────
  if (method === "GET" && url.pathname === "/autonomy-trigger") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) return corsJson({ ok: false, error: "Forbidden" }, 403);
    const mode = url.searchParams.get("mode") || "production_loop";
    const traceId = url.searchParams.get("trace_id") || ("auto_" + Date.now());
    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode, trace_id: traceId, add_internal_tasks: url.searchParams.get("add_internal_tasks") === "true",
      source: "deno_get_trigger", timestamp: new Date().toISOString()
    });
    const ok = dispatchStatus === 204;
    return corsJson({ ok, event_type: "autonomy-engine", mode, trace_id: traceId, dispatch_status: dispatchStatus }, ok ? 200 : 500);
  }

  // ─── GET /autonomy-backlog-trigger ───────────────────────────────────────
  if (method === "GET" && url.pathname === "/autonomy-backlog-trigger") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) return corsJson({ ok: false, error: "Forbidden" }, 403);
    const mode = url.searchParams.get("mode") || "production_loop";
    const traceId = url.searchParams.get("trace_id") || ("bl_" + Date.now());
    const preset = url.searchParams.get("preset");
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
    return corsJson({ ok, trace_id: traceId, mode, preset: preset || "custom", roadmap_commit_status: commitStatus, dispatch_status: dispatchStatus, tasks_added: addedIds, tasks_count: addedIds.length, stage: "dispatch" }, ok ? 200 : 500);
  }

  // ─── POST /autonomy-backlog ──────────────────────────────────────────────
  if (method === "POST" && url.pathname === "/autonomy-backlog") {
    const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization") || "";
    if (!checkGptToken(gptSecret, authHeader.replace("Bearer ", ""))) return corsJson({ ok: false, error: "Forbidden" }, 403);
    let body; try { body = await req.json(); } catch { return corsJson({ ok: false, error: "Invalid JSON" }, 400); }
    const mode = body.mode || "production_loop";
    const traceId = body.trace_id || ("bl_post_" + Date.now());
    const preset = body.preset;
    let tasks;
    if (preset === "full_chain") { tasks = buildFullChainPreset(traceId); }
    else { tasks = body.tasks; if (!Array.isArray(tasks) || !tasks.length) return corsJson({ ok: false, error: "tasks required or use preset=full_chain" }, 400); }
    const { commitStatus, dispatchStatus, addedIds } = await processBacklog(pat, tasks, traceId, mode);
    const ok = (commitStatus === 200 || commitStatus === 201) && dispatchStatus === 204;
    return corsJson({ ok, trace_id: traceId, mode, roadmap_commit_status: commitStatus, dispatch_status: dispatchStatus, tasks_added: addedIds, tasks_count: addedIds.length }, ok ? 200 : 500);
  }

  // ─── POST /autonomy ──────────────────────────────────────────────────────
  if (method === "POST" && url.pathname === "/autonomy") {
    const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization") || "";
    if (!checkGptToken(gptSecret, authHeader.replace("Bearer ", ""))) return corsJson({ ok: false, error: "Forbidden" }, 403);
    let body; try { body = await req.json(); } catch { return corsJson({ ok: false, error: "Invalid JSON" }, 400); }
    const mode = body.mode || "production_loop";
    const traceId = body.trace_id || ("post_" + Date.now());
    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode, trace_id: traceId, add_internal_tasks: body.add_internal_tasks || false,
      source: "deno_post_autonomy", timestamp: new Date().toISOString()
    });
    const ok = dispatchStatus === 204;
    return corsJson({ ok, mode, trace_id: traceId, dispatch_status: dispatchStatus }, ok ? 200 : 500);
  }

  // ─── POST / — TELEGRAM WEBHOOK ───────────────────────────────────────────
  if (method === "POST" && url.pathname === "/") {
    if (telegramSecret) {
      const secretHeader = req.headers.get("x-telegram-bot-api-secret-token");
      if (secretHeader !== telegramSecret) return new Response("Forbidden", { status: 403 });
    }
    let body; try { body = await req.json(); } catch { return new Response("Bad Request", { status: 400 }); }
    const message = body?.message;
    if (!message) return new Response("OK");
    const chatId = String(message.chat?.id);
    const messageId = String(message.message_id);
    const text = (message.text || "").trim();
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
