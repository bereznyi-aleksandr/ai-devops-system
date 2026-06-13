// Cloudflare Worker: Telegram Webhook → GitHub Actions dispatch
// BEM-932: routes operator messages through provider-router when ROUTER_WORKFLOW_ID is set.
// Default target is provider-router.yml; legacy codex-local.yml remains supported.

const ALLOWED_CHAT_ID = "601442777";

async function sendTelegram(env, chatId, text) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

function workflowInputsFor(targetWorkflowId, msg, text, traceId) {
  const task = [
    text,
    "",
    `telegram_chat_id=${String(msg.chat.id)}`,
    `telegram_message_id=${String(msg.message_id)}`,
  ].join("\n");

  const common = {
    role: "curator",
    trace_id: traceId,
    cycle_id: "telegram_operator_message",
    task_type: "telegram_operator_message",
    task,
  };

  if (targetWorkflowId === "provider-router.yml" || targetWorkflowId === "provider-router.yaml") {
    return {
      ...common,
      chat_id: String(msg.chat.id),
      message_id: String(msg.message_id),
    };
  }

  return {
    ...common,
    provider: "gpt_codex",
  };
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("bad json", { status: 400 });
    }

    const msg = update?.message;
    if (!msg) return new Response("no message", { status: 200 });

    if (String(msg.chat?.id) !== ALLOWED_CHAT_ID) {
      return new Response("not allowed", { status: 200 });
    }

    const text = msg.text || "";
    const updateId = String(update.update_id);
    const now = new Date().toISOString().replace(/[-:.]/g, "").slice(0, 15) + "Z";
    const traceId = `tg_${updateId}_${now}`;

    const targetWorkflowId = env.ROUTER_WORKFLOW_ID || "provider-router.yml";
    const dispatchUrl = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/${targetWorkflowId}/dispatches`;
    const dispatchBody = JSON.stringify({
      ref: "main",
      inputs: workflowInputsFor(targetWorkflowId, msg, text, traceId),
    });

    const dispatchResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_PAT}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-devops-system-cloudflare-worker",
      },
      body: dispatchBody,
    });

    if (dispatchResp.ok) {
      await sendTelegram(env, msg.chat.id, `⚡ Получено. Передано в ${targetWorkflowId} (trace: ${traceId})`);
      return new Response("ok", { status: 200 });
    }

    let details = "";
    try {
      details = await dispatchResp.text();
    } catch {}

    const safeDetails = details ? `\n${details.slice(0, 500)}` : "";
    await sendTelegram(env, msg.chat.id, `⚠️ Ошибка dispatch ${targetWorkflowId}: ${dispatchResp.status}${safeDetails}`);
    return new Response(`dispatch failed: ${dispatchResp.status}`, { status: 200 });
  },
};
