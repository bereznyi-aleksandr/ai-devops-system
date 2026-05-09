// Deno Deploy Webhook — AI DevOps System
// Версия: v3.1 | BM-309
//
// ENDPOINTS:
// GET  /                         — health check
// POST /                         — Telegram webhook
// POST /autonomy                 — GPT autonomy trigger (JSON body)
// GET  /autonomy-trigger         — GPT autonomy trigger (query params, no curl needed)
//
// ENVIRONMENT VARIABLES (Deno Deploy Settings → Environment Variables):
//   TELEGRAM_BOT_TOKEN    = Telegram бот токен
//   GITHUB_PAT            = AI_SYSTEM_GITHUB_PAT (repo write access)
//   GITHUB_REPO           = bereznyi-aleksandr/ai-devops-system
//   ALLOWED_CHAT_ID       = 601442777
//   TELEGRAM_WEBHOOK_SECRET = случайная строка для Telegram
//   GPT_WEBHOOK_SECRET    = случайная строка для GPT endpoints
//
// РЕГИСТРАЦИЯ TELEGRAM WEBHOOK:
//   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://xxx.deno.dev&secret_token=<TELEGRAM_WEBHOOK_SECRET>
//
// GPT TRIGGER URL (открыть в браузере или вызвать GET):
//   https://fine-chicken-23.bereznyi-aleksandr.deno.net/autonomy-trigger?token=<GPT_WEBHOOK_SECRET>&mode=production_loop&trace_id=gpt_001

const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "bereznyi-aleksandr/ai-devops-system";
const GITHUB_ISSUE = 31;
const ALLOWED_CHAT_ID = Deno.env.get("ALLOWED_CHAT_ID") || "601442777";

// ─── GitHub API helpers ────────────────────────────────────────────────────

async function postGitHubComment(pat, body) {
  const resp = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/issues/${GITHUB_ISSUE}/comments`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${pat}`,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ body })
    }
  );
  return resp.status;
}

async function triggerRepositoryDispatch(pat, eventType, payload) {
  // repository_dispatch триггерит GitHub Actions без popup и без owner PAT restriction
  const resp = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${pat}`,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        event_type: eventType,
        client_payload: payload
      })
    }
  );
  return resp.status;
}

// ─── Telegram helpers ──────────────────────────────────────────────────────

async function sendTelegram(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: "Markdown" })
  });
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
      version: "3.1",
      endpoints: {
        "GET  /": "health check",
        "POST /": "Telegram webhook",
        "POST /autonomy": "GPT autonomy trigger (JSON body)",
        "GET  /autonomy-trigger": "GPT autonomy trigger (query params)"
      }
    }, null, 2), {
      headers: { "Content-Type": "application/json" }
    });
  }

  // ─── GET /autonomy-trigger ───────────────────────────────────────────────
  // GPT открывает URL с query params → repository_dispatch запускается
  // Не требует curl, POST или JSON body — работает как обычный GET запрос
  if (method === "GET" && url.pathname === "/autonomy-trigger") {
    // Проверить token
    const queryToken = url.searchParams.get("token");
    if (gptSecret && queryToken !== gptSecret) {
      return new Response(JSON.stringify({ ok: false, error: "Forbidden" }), {
        status: 403,
        headers: { "Content-Type": "application/json" }
      });
    }

    const mode = url.searchParams.get("mode") || "production_loop";
    const traceId = url.searchParams.get("trace_id") || ("gpt_get_" + Date.now());
    const addInternalTasks = url.searchParams.get("add_internal_tasks") === "true";

    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode: mode,
      trace_id: traceId,
      add_internal_tasks: addInternalTasks,
      source: "gpt_get_autonomy_trigger",
      timestamp: new Date().toISOString()
    });

    const ok = dispatchStatus === 204;
    return new Response(JSON.stringify({
      ok: ok,
      event_type: "autonomy-engine",
      mode: mode,
      trace_id: traceId,
      add_internal_tasks: addInternalTasks,
      dispatch_status: dispatchStatus,
      message: ok
        ? "repository_dispatch triggered — autonomous-task-engine.yml will run"
        : "repository_dispatch failed — check GITHUB_PAT permissions"
    }, null, 2), {
      status: ok ? 200 : 500,
      headers: { "Content-Type": "application/json" }
    });
  }

  // ─── POST /autonomy ──────────────────────────────────────────────────────
  // GPT вызывает POST с JSON body
  if (method === "POST" && url.pathname === "/autonomy") {
    if (gptSecret) {
      const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization");
      if (!authHeader || !authHeader.includes(gptSecret)) {
        return new Response(JSON.stringify({ ok: false, error: "Forbidden" }), {
          status: 403,
          headers: { "Content-Type": "application/json" }
        });
      }
    }

    let body;
    try {
      body = await req.json();
    } catch {
      return new Response(JSON.stringify({ ok: false, error: "Bad Request: invalid JSON" }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    const mode = body.mode || "production_loop";
    const traceId = body.trace_id || ("gpt_post_" + Date.now());
    const addInternalTasks = body.add_internal_tasks || false;

    const dispatchStatus = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode: mode,
      trace_id: traceId,
      add_internal_tasks: addInternalTasks,
      source: "gpt_post_autonomy",
      timestamp: new Date().toISOString()
    });

    const ok = dispatchStatus === 204;
    return new Response(JSON.stringify({
      ok: ok,
      event_type: "autonomy-engine",
      mode: mode,
      trace_id: traceId,
      dispatch_status: dispatchStatus,
      message: ok
        ? "repository_dispatch triggered — autonomous-task-engine.yml will run"
        : "repository_dispatch failed"
    }, null, 2), {
      status: ok ? 200 : 500,
      headers: { "Content-Type": "application/json" }
    });
  }

  // ─── POST / — TELEGRAM WEBHOOK ───────────────────────────────────────────
  if (method === "POST" && url.pathname === "/") {
    if (telegramSecret) {
      const secretHeader = req.headers.get("x-telegram-bot-api-secret-token");
      if (secretHeader !== telegramSecret) {
        return new Response("Forbidden", { status: 403 });
      }
    }

    let body;
    try {
      body = await req.json();
    } catch {
      return new Response("Bad Request", { status: 400 });
    }

    const message = body?.message;
    if (!message) return new Response("OK");

    const chatId = String(message.chat?.id);
    const messageId = String(message.message_id);
    const text = (message.text || "").trim();

    if (chatId !== ALLOWED_CHAT_ID) {
      return new Response("Forbidden", { status: 403 });
    }

    const now = new Date().toLocaleTimeString("uk-UA", {
      timeZone: "Europe/Kiev", hour: "2-digit", minute: "2-digit"
    });

    const dedupeKey = `telegram:${chatId}:${messageId}`;

    const curatorComment = `@curator

TYPE: OPERATOR_TO_CURATOR
SOURCE: telegram
DEDUP_KEY: ${dedupeKey}

\`\`\`json
{
  "chat_id": "${chatId}",
  "message_id": "${messageId}",
  "text": ${JSON.stringify(text)}
}
\`\`\``;

    const status = await postGitHubComment(pat, curatorComment);

    if (status === 201) {
      await sendTelegram(token, chatId,
        `📨 *${now} UA* | Получено и передано куратору:\n_${text.slice(0, 100)}_`);
    } else {
      await sendTelegram(token, chatId,
        `❌ *${now} UA* | Ошибка передачи куратору (HTTP ${status})`);
    }

    return new Response("OK");
  }

  // ─── 404 ─────────────────────────────────────────────────────────────────
  return new Response(JSON.stringify({
    ok: false,
    error: "Not Found",
    available_endpoints: ["GET /", "POST /", "POST /autonomy", "GET /autonomy-trigger"]
  }), {
    status: 404,
    headers: { "Content-Type": "application/json" }
  });
});
