// Cloudflare Worker: Telegram Webhook → GitHub Actions provider-router
// BEM-932: runtime route must dispatch provider-router.yml, not codex-local.yml.

const DEFAULT_ALLOWED_CHAT_ID = "601442777";
const DEFAULT_ROUTER_WORKFLOW_ID = "provider-router.yml";

function jsonResponse(body, status = 200) {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

async function sendTelegram(env, chatId, text) {
  if (!env.TELEGRAM_BOT_TOKEN || !chatId) return null;
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

function makeTraceId(updateId) {
  const now = new Date().toISOString().replace(/[-:.]/g, "").slice(0, 15) + "Z";
  return `tg_${updateId}_${now}`;
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return jsonResponse({ status: "OK", method: request.method });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return jsonResponse({ status: "BAD_JSON" }, 400);
    }

    const msg = update?.message;
    if (!msg) return jsonResponse({ status: "NO_MESSAGE" });

    const allowedChatId = String(env.ALLOWED_CHAT_ID || DEFAULT_ALLOWED_CHAT_ID);
    const chatId = String(msg.chat?.id || "");
    if (chatId !== allowedChatId) {
      return jsonResponse({ status: "IGNORED_CHAT", chat_id: chatId });
    }

    const token = env.GH_PAT || env.AI_SYSTEM_GITHUB_PAT;
    if (!token) {
      await sendTelegram(env, msg.chat.id, "⚠️ GH_PAT отсутствует в runtime. provider-router не запущен.");
      return jsonResponse({ status: "MISSING_GH_PAT" });
    }

    const repo = env.GH_REPO || "bereznyi-aleksandr/ai-devops-system";
    const routerWorkflowId = env.ROUTER_WORKFLOW_ID || DEFAULT_ROUTER_WORKFLOW_ID;
    const updateId = String(update.update_id || msg.message_id || Date.now());
    const traceId = makeTraceId(updateId);
    const text = msg.text || "";

    const dispatchBody = {
      ref: "main",
      inputs: {
        role: "curator",
        trace_id: traceId,
        cycle_id: "telegram_operator_message",
        task_type: "telegram_operator_message",
        task: text,
        chat_id: chatId,
        message_id: String(msg.message_id || ""),
      },
    };

    const dispatchUrl = `https://api.github.com/repos/${repo}/actions/workflows/${routerWorkflowId}/dispatches`;
    const dispatchResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-devops-system-cloudflare-worker",
      },
      body: JSON.stringify(dispatchBody),
    });

    if (dispatchResp.ok) {
      await sendTelegram(env, msg.chat.id, `⚡ Получено. Передано в provider-router (trace: ${traceId})`);
      return jsonResponse({
        status: "DISPATCHED",
        workflow_id: routerWorkflowId,
        trace_id: traceId,
      });
    }

    let details = "";
    try {
      details = await dispatchResp.text();
    } catch {}

    const safeDetails = details ? `\n${details.slice(0, 500)}` : "";
    await sendTelegram(env, msg.chat.id, `⚠️ Ошибка provider-router dispatch: ${dispatchResp.status}${safeDetails}`);
    return jsonResponse({
      status: "DISPATCH_FAILED",
      workflow_id: routerWorkflowId,
      http_status: dispatchResp.status,
      details: details.slice(0, 1000),
    });
  },
};
