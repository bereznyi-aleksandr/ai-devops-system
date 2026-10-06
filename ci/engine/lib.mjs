// ДОКУМЕНТ: ci/engine/lib.mjs
// ВЕРСИЯ: v1.0
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-06 19:55 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия 4401918c-de88-4db7-841e-b418568ae069)
// НАЗНАЧЕНИЕ: клиент REST Flowable 8.0.0 для пробы движка на PostgreSQL в GitHub Actions.
//   Перенос R47 work/lib.mjs: пути и учётка администратора берутся из окружения задания.
// ОГРАНИЧЕНИЯ: пароль одноразовый (генерируется заданием, скрыт маской), никуда не выводится.
import { appendFileSync } from "node:fs";

export const S = process.env.ENGINE_WORK;
export const BASE = process.env.ENGINE_BASE ?? "http://127.0.0.1:8091/flowable-rest";
const AUTH = "Basic " + Buffer.from(`${process.env.ENGINE_USER}:${process.env.ENGINE_PASS}`).toString("base64");

let LOG = null;
export function setLog(file) { LOG = file; }
export function log(...a) {
  const line = a.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join(" ");
  console.log(line);
  if (LOG) appendFileSync(LOG, line + "\n");
}

export async function api(method, path, body, { raw = false, auth = AUTH } = {}) {
  const headers = { Authorization: auth };
  let payload;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const r = await fetch(BASE + path, { method, headers, body: payload });
  const text = await r.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch { /* not json */ }
  return { status: r.status, json, text: raw ? text : text.slice(0, 400) };
}

export async function deploy(name, xml) {
  const fd = new FormData();
  fd.append("file", new Blob([xml], { type: "text/xml" }), name);
  return api("POST", "/service/repository/deployments", fd);
}

export const vars = (o) => Object.entries(o).map(([name, value]) => ({
  name, value, type: typeof value === "number" ? "integer" : typeof value === "boolean" ? "boolean" : "string",
}));

export async function startByMessage(message, variables, businessKey) {
  return api("POST", "/service/runtime/process-instances", { message, businessKey, variables: vars(variables) });
}

export async function acquire(topic, workerId, lockDuration = "PT30S", n = 10) {
  return api("POST", "/external-job-api/acquire/jobs", { topic, lockDuration, numberOfTasks: n, workerId });
}

export async function completeJob(jobId, workerId, variables = {}) {
  return api("POST", `/external-job-api/acquire/jobs/${jobId}/complete`, { workerId, variables: vars(variables) });
}

export async function executions(q) {
  const qs = new URLSearchParams({ size: "500", ...q }).toString();
  return (await api("GET", `/service/runtime/executions?${qs}`)).json?.data ?? [];
}

export async function procInstances(q = {}) {
  const qs = new URLSearchParams({ size: "500", ...q }).toString();
  return (await api("GET", `/service/runtime/process-instances?${qs}`)).json?.data ?? [];
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
