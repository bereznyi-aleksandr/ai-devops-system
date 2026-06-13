// Cloudflare Worker: Telegram Webhook → BEM-932 provider-router
// FULL FILE REPLACEMENT. Runtime dispatch goes to ROUTER_WORKFLOW_ID/provider-router.yml,
// not directly to codex-local.yml. Telegram metadata is passed as strict workflow inputs.

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

function traceSuffix() {
  return new Date().toISOString().replace(/[-:.]/g, "").slice(0, 15) + "Z";
}

function makeTraceId(updateId) {
  const safeUpdateId = safeString(updateId, "unknown").replace(/[^a-zA-Z0-9_-]/g, "_");
  return `tg_${safeUpdateId}_${traceSuffix()}`;
}

function preview(text, limit = 500) {
  const s = safeString(text);
  return s.length > limit ? s.slice(0, limit) : s;
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
  } catch (e) {
    details = safeString(e);
  }

  return {
    ok: resp.ok,
    status: resp.status,
    details,
  };
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return jsonResponse({ status: "OK", method: request.method });
    }

    let update;
    try {
      update = await request.json();
    } catch (e) {
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

    const workflowId = safeString(env.ROUTER_WORKFLOW_ID, DEFAULT_ROUTER_WORKFLOW_ID).trim();
    const updateId = update.update_id ?? msg.message_id ?? Date.now();
    const traceId = makeTraceId(updateId);
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
  },
};
