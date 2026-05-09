// Deno Deploy Webhook — AI DevOps System
// Версия: v3.0 | BM-306
//
// НАЗНАЧЕНИЕ:
// 1. Принимает Telegram сообщения → передаёт @curator в issue #31
// 2. Принимает запросы от GPT → триггерит repository_dispatch для autonomous-task-engine
//
// ДЕПЛОЙ:
// 1. deno.com/deploy → New Playground → вставь код → Deploy
// 2. Settings → Environment Variables:
//    TELEGRAM_BOT_TOKEN = токен бота
//    GITHUB_PAT = AI_SYSTEM_GITHUB_PAT
//    GITHUB_REPO = bereznyi-aleksandr/ai-devops-system
//    ALLOWED_CHAT_ID = 601442777
//    TELEGRAM_WEBHOOK_SECRET = случайная строка
//    GPT_WEBHOOK_SECRET = случайная строка для GPT запросов
// 3. Зарегистрировать Telegram webhook:
//    https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://xxx.deno.dev&secret_token=<TELEGRAM_WEBHOOK_SECRET>

const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "bereznyi-aleksandr/ai-devops-system";
const GITHUB_ISSUE = 31;
const ALLOWED_CHAT_ID = Deno.env.get("ALLOWED_CHAT_ID") || "601442777";

async function sendTelegram(token, chatId, text) {
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: "Markdown" })
  });
}

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

Deno.serve(async (req) => {
  const pat = Deno.env.get("GITHUB_PAT");
  const token = Deno.env.get("TELEGRAM_BOT_TOKEN");
  const telegramSecret = Deno.env.get("TELEGRAM_WEBHOOK_SECRET");
  const gptSecret = Deno.env.get("GPT_WEBHOOK_SECRET");

  // Health check
  if (req.method === "GET") {
    return new Response(JSON.stringify({
      ok: true,
      service: "ai-devops-telegram-curator-webhook",
      repo: GITHUB_REPO,
      issue: GITHUB_ISSUE,
      version: "3.0",
      endpoints: {
        "POST /": "Telegram webhook",
        "POST /autonomy": "GPT autonomy trigger (repository_dispatch)"
      }
    }), {
      headers: { "Content-Type": "application/json" }
    });
  }

  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  const url = new URL(req.url);

  // ─── GPT AUTONOMY ENDPOINT ────────────────────────────────────────────────
  // GPT вызывает POST /autonomy с JSON payload
  // Это триггерит repository_dispatch → autonomous-task-engine.yml запускается
  if (url.pathname === "/autonomy") {
    // Проверить GPT secret если настроен
    if (gptSecret) {
      const authHeader = req.headers.get("x-gpt-secret") || req.headers.get("authorization");
      if (!authHeader || !authHeader.includes(gptSecret)) {
        return new Response("Forbidden", { status: 403 });
      }
    }

    let body;
    try {
      body = await req.json();
    } catch {
      return new Response("Bad Request: invalid JSON", { status: 400 });
    }

    const mode = body.mode || "production_loop";
    const traceId = body.trace_id || ("gpt_" + Date.now());
    const addInternalTasks = body.add_internal_tasks || false;

    const status = await triggerRepositoryDispatch(pat, "autonomy-engine", {
      mode: mode,
      trace_id: traceId,
      add_internal_tasks: addInternalTasks,
      source: "gpt_autonomy_webhook",
      timestamp: new Date().toISOString()
    });

    if (status === 204) {
      return new Response(JSON.stringify({
        ok: true,
        event_type: "autonomy-engine",
        mode: mode,
        trace_id: traceId,
        message: "repository_dispatch triggered — autonomous-task-engine.yml will run"
      }), { headers: { "Content-Type": "application/json" } });
    } else {
      return new Response(JSON.stringify({
        ok: false,
        status: status,
        message: "repository_dispatch failed"
      }), { status: 500, headers: { "Content-Type": "application/json" } });
    }
  }

  // ─── TELEGRAM WEBHOOK ────────────────────────────────────────────────────
  // Проверить Telegram webhook secret
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

  // Формируем комментарий для @curator
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
});
