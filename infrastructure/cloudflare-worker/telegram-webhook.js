// Cloudflare Worker: Telegram Webhook + GPT Dispatch → BEM-932 provider-router / any workflow
// Telegram path: unchanged, dispatches to ROUTER_WORKFLOW_ID (provider-router.yml) as role=curator.
// GPT path (new): authenticated via x-gpt-secret header, dispatches any named
// workflow with arbitrary inputs. Both paths reuse the same proven
// dispatchWorkflow() function (BEM-932, already deployed and receipt-verified).

const DEFAULT_ALLOWED_CHAT_ID = "601442777";
const DEFAULT_REPO = "bereznyi-aleksandr/ai-devops-system";
const DEFAULT_ROUTER_WORKFLOW_ID = "provider-router.yml";

function jsonResponse(body, status = 200) {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function safeString(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  return String(value);
}

function makeTraceId(updateKey) {
  const safeUpdateKey = safeString(updateKey, "unknown").replace(/[^a-zA-Z0-9_-]/g, "_");
  return `tg_${safeUpdateKey}`;
}

function preview(text, limit = 500) {
  const value = safeString(text);
  return value.length > limit ? value.slice(0, limit) : value;
}

async function sendTelegram(env, chatId, text) {
  if (!env.TELEGRAM_BOT_TOKEN || !chatId) return null;
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

function buildProviderRouterPayload(msg, text, traceId) {
  return {
    ref: "main",
    inputs: {
      role: "curator",
      task: text,
      trace_id: traceId,
      chat_id: safeString(msg.chat?.id),
      message_id: safeString(msg.message_id),
      cycle_id: "telegram_operator_message",
      task_type: "telegram_operator_message",
    },
  };
}

async function dispatchWorkflow(env, workflowId, body) {
  const repo = safeString(env.GH_REPO, DEFAULT_REPO);
  const token = env.GH_PAT || env.AI_SYSTEM_GITHUB_PAT;
  if (!token) {
    return {
      ok: false,
      status: 500,
      details: "missing GH_PAT or AI_SYSTEM_GITHUB_PAT",
    };
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflowId}/dispatches`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "ai-devops-system-telegram-provider-router",
    },
    body: JSON.stringify(body),
  });

  let details = "";
  try {
    details = await resp.text();
  } catch (error) {
    details = safeString(error);
  }

  return {
    ok: resp.ok,
    status: resp.status,
    details,
  };
}

// GPT generic dispatch: POST /gpt-dispatch
// Headers: x-gpt-secret: <GPT_WEBHOOK_SECRET>
// Body: { "workflow_id": "claude.yml", "inputs": { "role": "executor", ... } }
async function handleGptDispatch(request, env) {
  const providedSecret = request.headers.get("x-gpt-secret") || "";
  const expectedSecret = env.GPT_WEBHOOK_SECRET || "";
  if (!expectedSecret || providedSecret !== expectedSecret) {
    return jsonResponse({ ok: false, error: "FORBIDDEN" }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return jsonResponse({ ok: false, error: "BAD_JSON" }, 400);
  }

  const workflowId = safeString(body.workflow_id).trim();
  const inputs = body.inputs && typeof body.inputs === "object" ? body.inputs : {};
  if (!workflowId) {
    return jsonResponse({ ok: false, error: "workflow_id is required" }, 400);
  }

  const result = await dispatchWorkflow(env, workflowId, { ref: "main", inputs });

  return jsonResponse(
    {
      ok: result.ok,
      workflow_id: workflowId,
      http_status: result.status,
      details: preview(result.details, 1000),
    },
    result.ok ? 200 : 500
  );
}

async function handleTelegram(request, env) {
  let update;
  try {
    update = await request.json();
  } catch (error) {
    return jsonResponse({ status: "BAD_JSON" }, 400);
  }

  const msg = update?.message;
  if (!msg) return jsonResponse({ status: "NO_MESSAGE" });

  const allowedChatId = safeString(env.ALLOWED_CHAT_ID, DEFAULT_ALLOWED_CHAT_ID);
  const chatId = safeString(msg.chat?.id);
  if (chatId !== allowedChatId) {
    return jsonResponse({ status: "IGNORED_CHAT", chat_id: chatId });
  }

  const text = safeString(msg.text).trim();
  if (!text) {
    await sendTelegram(env, chatId, "⚠️ Пустое сообщение не принято.");
    return jsonResponse({ status: "EMPTY_MESSAGE" });
  }

  const workflowId = safeString(
    env.ROUTER_WORKFLOW_ID,
    DEFAULT_ROUTER_WORKFLOW_ID
  ).trim();

  // Telegram retries the same update_id. The fallback is also deterministic,
  // so every retry reaches the outbox loop with the same trace_id.
  const updateKey =
    update.update_id ?? `${chatId}_${msg.message_id ?? "unknown"}`;
  const traceId = makeTraceId(updateKey);
  const payload = buildProviderRouterPayload(msg, text, traceId);
  const result = await dispatchWorkflow(env, workflowId, payload);

  if (result.ok) {
    await sendTelegram(
      env,
      chatId,
      `⚡ Получено. Передано в provider-router (trace: ${traceId})`
    );
    return jsonResponse({
      status: "DISPATCHED",
      workflow_id: workflowId,
      trace_id: traceId,
    });
  }

  await sendTelegram(
    env,
    chatId,
    `⚠️ Ошибка provider-router dispatch: ${result.status}\nworkflow=${workflowId}\ntrace=${traceId}\n${preview(result.details)}`
  );

  return jsonResponse({
    status: "DISPATCH_FAILED",
    workflow_id: workflowId,
    trace_id: traceId,
    http_status: result.status,
    details: preview(result.details, 1000),
  });
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return jsonResponse({ status: "OK", method: request.method });
    }

    const url = new URL(request.url);
    if (url.pathname === "/gpt-dispatch") {
      return handleGptDispatch(request, env);
    }

    return handleTelegram(request, env);
  },
};
