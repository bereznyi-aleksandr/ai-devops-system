// Cloudflare/Deno Worker — Telegram Bot Webhook
// Версия: v2.0 | Дата: 2026-05-03 | E3-002
//
// Деплой на Deno Deploy:
// 1. Зайди на deno.com/deploy → Sign in with GitHub
// 2. New Playground → вставь этот код
// 3. Settings → Environment Variables:
//    TELEGRAM_BOT_TOKEN = твой токен
//    GITHUB_PAT = значение AI_SYSTEM_GITHUB_PAT
//    GITHUB_REPO = bereznyi-aleksandr/ai-devops-system
//    ALLOWED_CHAT_ID = 601442777
//    TELEGRAM_WEBHOOK_SECRET = любая случайная строка
// 4. Скопируй URL деплоя (https://xxx.deno.dev)
// 5. Зарегистрируй webhook:
//    https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://xxx.deno.dev&secret_token=<WEBHOOK_SECRET>

const ALLOWED_CHAT_ID = Deno.env.get("ALLOWED_CHAT_ID") || "601442777";
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "bereznyi-aleksandr/ai-devops-system";
const GITHUB_ISSUE = 31;

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

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("AI DevOps System Webhook v2.0", { status: 200 });
  }

  const token = Deno.env.get("TELEGRAM_BOT_TOKEN");
  const pat = Deno.env.get("GITHUB_PAT");
  const webhookSecret = Deno.env.get("TELEGRAM_WEBHOOK_SECRET");

  // Проверить webhook secret
  if (webhookSecret) {
    const secretHeader = req.headers.get("x-telegram-bot-api-secret-token");
    if (secretHeader !== webhookSecret) {
      return new Response("Forbidden", { status: 403 });
    }
  }

  const body = await req.json();
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
