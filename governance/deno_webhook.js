// Deno Deploy Webhook — AI DevOps System
// Версия: v4.0 | BM-333
//
// ENDPOINTS:
// GET  /                           — health check
// POST /                           — Telegram webhook
// POST /autonomy                   — GPT autonomy trigger (JSON body)
// GET  /autonomy-trigger           — GPT autonomy trigger (query params)
// GET  /autonomy-backlog-trigger   — GPT backlog + trigger (query params, tasks_b64)
// POST /autonomy-backlog           — GPT backlog + trigger (JSON body, long payloads)

const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "bereznyi-aleksandr/ai-devops-system";
const GITHUB_ISSUE = 31;
const ALLOWED_CHAT_ID = Deno.env.get("ALLOWED_CHAT_ID") || "601442777";
const GITHUB_API = "https://api.github.com";

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
    `/repos/${GITHUB_REPO}/issues/${GITHUB_ISSUE}/comments`,
    { body });
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
  const data = await resp.json();
  return data;
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

// ─── Backlog logic ─────────────────────────────────────────────────────────

function decodeTasksB64(b64) {
  // Поддержка base64url (заменяем - → + и _ → /)
  const standard = b64.replace(/-/g, "+").replace(/_/g, "/");
  const padded = standard + "=".repeat((4 - standard.length % 4) % 4);
  const decoded = atob(padded);
  return JSON.parse(decodeURIComponent(escape(decoded)));
}

async function processBacklog(pat, tasks, traceId, mode) {
  // 1. Читать текущий roadmap_state.json
  const fileData = await getFileContents(pat, "governance/state/roadmap_state.json");
  let roadmap = { version: 1, tasks: [], blocker: null };
  let sha = undefined;

  if (fileData && fileData.content) {
    const raw = decodeURIComponent(escape(atob(fileData.content.replace(/\n/g, ""))));
    roadmap = JSON.parse(raw);
    sha = fileData.sha;
  }

  // 2. Добавить/обновить задачи
  const existingIds = new Map(roadmap.tasks.map((t) => [t.task_id, t]));
  const addedIds = [];

  for (const task of tasks) {
    const existing = existingIds.get(task.task_id);
    if (existing) {
      // Обновить только если не completed
      if (existing.status !== "completed") {
        Object.assign(existing, task);
        addedIds.push(task.task_id);
      }
    } else {
      roadmap.tasks.push({ ...task, status: task.status || "pending" });
      addedIds.push(task.task_id);
    }
  }

  roadmap.updated_at = new Date().toISOString();
  roadmap.cursor = tasks[tasks.length - 1]?.task_id || roadmap.cursor;
  roadmap.blocker = null;

  // 3. Записать roadmap_state.json через GitHub Contents API
  const content = JSON.stringify(roadmap, null, 2) + "\n";
  const commitStatus = await updateFileContents(
    pat,
    "governance/state/roadmap_state.json",
    content,
    `BM-333: enqueue autonomy backlog ${traceId}`,
    sha
  );

  // 4. Запустить repository_dispatch
  const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
    mode: mode,
    trace_id: traceId,
    add_internal_tasks: false,
    source: "gpt_backlog_trigger",
    backlog_tasks: addedIds,
    timestamp: new Date().toISOString()
  });

  return { commitStatus, dispatchStatus, addedIds };
}

// ─── Token check ───────────────────────────────────────────────────────────

function checkGptToken(gptSecret, provided) {
  if (!gptSecret) return true; // no secret configured — allow all
  return provided === gptSecret;
}

// ─── Main handler ──────────────────────────────────────────────────────────

Deno.serve(async (req) => {
  const pat = Deno.env.get("GITHUB_PAT");
  const token = Deno.env.get("TELEGRAM_BOT_TOKEN");
  const telegramSecret = Deno.env.get("TELEGRAM_WEBHOOK_SECRET");
  const gptSecret = Deno.env.get("GPT_WEBHOOK_SECRET");

  const url = new URL(req.url);
  const method = req.method;

  // ─── HEALTH CHECK ────────────────────────────────────────────────────────
  if (method === "GET" && url.pathname === "/") {
    return new Response(JSON.stringify({
      ok: true,
      service: "ai-devops-telegram-curator-webhook",
      repo: GITHUB_REPO,
      issue: GITHUB_ISSUE,
      version: "4.0",
      endpoints: {
        "GET  /": "health check",
        "POST /": "Telegram webhook",
        "POST /autonomy": "GPT trigger (JSON body)",
        "GET  /autonomy-trigger": "GPT trigger (query params)",
        "GET  /autonomy-backlog-trigger": "GPT backlog + trigger (query params, tasks_b64)",
        "POST /autonomy-backlog": "GPT backlog + trigger (JSON body)"
      }
    }, null, 2), { headers: { "Content-Type": "application/json" } });
  }

  // ─── GET /autonomy-trigger ───────────────────────────────────────────────
  if (method === "GET" && url.pathname === "/autonomy-trigger") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) {
      return new Response(JSON.stringify({ ok: false, error: "Forbidden" }), {
        status: 403, headers: { "Content-Type": "application/json" }
      });
    }
    const mode = url.searchParams.get("mode") || "production_loop";
    const traceId = url.searchParams.get("trace_id") || ("gpt_get_" + Date.now());
    const addInternalTasks = url.searchParams.get("add_internal_tasks") === "true";
    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode, trace_id: traceId, add_internal_tasks: addInternalTasks,
      source: "gpt_get_autonomy_trigger", timestamp: new Date().toISOString()
    });
    const ok = dispatchStatus === 204;
    return new Response(JSON.stringify({
      ok, event_type: "autonomy-engine", mode, trace_id: traceId,
      dispatch_status: dispatchStatus,
      message: ok ? "repository_dispatch triggered" : "dispatch failed"
    }, null, 2), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });
  }

  // ─── GET /autonomy-backlog-trigger ───────────────────────────────────────
  if (method === "GET" && url.pathname === "/autonomy-backlog-trigger") {
    const queryToken = url.searchParams.get("token");
    if (!checkGptToken(gptSecret, queryToken)) {
      return new Response(JSON.stringify({ ok: false, error: "Forbidden" }), {
        status: 403, headers: { "Content-Type": "application/json" }
      });
    }
    const mode = url.searchParams.get("mode") || "production_loop";
    const traceId = url.searchParams.get("trace_id") || ("gpt_backlog_" + Date.now());
    const tasksB64 = url.searchParams.get("tasks_b64");

    if (!tasksB64) {
      return new Response(JSON.stringify({ ok: false, error: "tasks_b64 is required" }), {
        status: 400, headers: { "Content-Type": "application/json" }
      });
    }

    let tasks;
    try {
      const decoded = decodeTasksB64(tasksB64);
      tasks = decoded.tasks;
      if (!Array.isArray(tasks) || tasks.length === 0) throw new Error("tasks must be non-empty array");
    } catch (e) {
      return new Response(JSON.stringify({ ok: false, error: "Invalid tasks_b64: " + e.message }), {
        status: 400, headers: { "Content-Type": "application/json" }
      });
    }

    const { commitStatus, dispatchStatus, addedIds } = await processBacklog(pat, tasks, traceId, mode);
    const ok = (commitStatus === 200 || commitStatus === 201) && dispatchStatus === 204;
    return new Response(JSON.stringify({
      ok, trace_id: traceId, mode,
      roadmap_commit_status: commitStatus,
      dispatch_status: dispatchStatus,
      tasks_added: addedIds,
      tasks_count: addedIds.length,
      message: ok ? "Backlog queued and engine triggered" : "Partial failure"
    }, null, 2), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });
  }

  // ─── POST /autonomy-backlog ──────────────────────────────────────────────
  if (method === "POST" && url.pathname === "/autonomy-backlog") {
    if (gptSecret) {
      const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization");
      if (!authHeader || !authHeader.includes(gptSecret)) {
        return new Response(JSON.stringify({ ok: false, error: "Forbidden" }), {
          status: 403, headers: { "Content-Type": "application/json" }
        });
      }
    }
    let body;
    try { body = await req.json(); } catch {
      return new Response(JSON.stringify({ ok: false, error: "Invalid JSON" }), {
        status: 400, headers: { "Content-Type": "application/json" }
      });
    }
    const mode = body.mode || "production_loop";
    const traceId = body.trace_id || ("gpt_backlog_post_" + Date.now());
    const tasks = body.tasks;
    if (!Array.isArray(tasks) || tasks.length === 0) {
      return new Response(JSON.stringify({ ok: false, error: "tasks must be non-empty array" }), {
        status: 400, headers: { "Content-Type": "application/json" }
      });
    }
    const { commitStatus, dispatchStatus, addedIds } = await processBacklog(pat, tasks, traceId, mode);
    const ok = (commitStatus === 200 || commitStatus === 201) && dispatchStatus === 204;
    return new Response(JSON.stringify({
      ok, trace_id: traceId, mode,
      roadmap_commit_status: commitStatus,
      dispatch_status: dispatchStatus,
      tasks_added: addedIds,
      tasks_count: addedIds.length
    }, null, 2), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });
  }

  // ─── POST /autonomy ──────────────────────────────────────────────────────
  if (method === "POST" && url.pathname === "/autonomy") {
    if (gptSecret) {
      const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization");
      if (!authHeader || !authHeader.includes(gptSecret)) {
        return new Response(JSON.stringify({ ok: false, error: "Forbidden" }), {
          status: 403, headers: { "Content-Type": "application/json" }
        });
      }
    }
    let body;
    try { body = await req.json(); } catch {
      return new Response(JSON.stringify({ ok: false, error: "Invalid JSON" }), {
        status: 400, headers: { "Content-Type": "application/json" }
      });
    }
    const mode = body.mode || "production_loop";
    const traceId = body.trace_id || ("gpt_post_" + Date.now());
    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode, trace_id: traceId, add_internal_tasks: body.add_internal_tasks || false,
      source: "gpt_post_autonomy", timestamp: new Date().toISOString()
    });
    const ok = dispatchStatus === 204;
    return new Response(JSON.stringify({
      ok, mode, trace_id: traceId, dispatch_status: dispatchStatus
    }, null, 2), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });
  }

  // ─── POST / — TELEGRAM WEBHOOK ───────────────────────────────────────────
  if (method === "POST" && url.pathname === "/") {
    if (telegramSecret) {
      const secretHeader = req.headers.get("x-telegram-bot-api-secret-token");
      if (secretHeader !== telegramSecret) return new Response("Forbidden", { status: 403 });
    }
    let body;
    try { body = await req.json(); } catch { return new Response("Bad Request", { status: 400 }); }

    const message = body?.message;
    if (!message) return new Response("OK");

    const chatId = String(message.chat?.id);
    const messageId = String(message.message_id);
    const text = (message.text || "").trim();

    if (chatId !== ALLOWED_CHAT_ID) return new Response("Forbidden", { status: 403 });

    const now = new Date().toLocaleTimeString("uk-UA", {
      timeZone: "Europe/Kiev", hour: "2-digit", minute: "2-digit"
    });
    const dedupeKey = `telegram:${chatId}:${messageId}`;
    const curatorComment = `@curator\n\nTYPE: OPERATOR_TO_CURATOR\nSOURCE: telegram\nDEDUP_KEY: ${dedupeKey}\n\n\`\`\`json\n{\n  "chat_id": "${chatId}",\n  "message_id": "${messageId}",\n  "text": ${JSON.stringify(text)}\n}\n\`\`\``;

    const status = await postGitHubComment(pat, curatorComment);
    if (status === 201) {
      await sendTelegram(token, chatId, `📨 *${now} UA* | Отправлено куратору:\n_${text.slice(0, 100)}_`);
    } else {
      await sendTelegram(token, chatId, `❌ *${now} UA* | Ошибка (HTTP ${status})`);
    }
    return new Response("OK");
  }

  return new Response(JSON.stringify({
    ok: false, error: "Not Found",
    endpoints: ["GET /", "POST /", "POST /autonomy", "GET /autonomy-trigger",
      "GET /autonomy-backlog-trigger", "POST /autonomy-backlog"]
  }), { status: 404, headers: { "Content-Type": "application/json" } });
});
