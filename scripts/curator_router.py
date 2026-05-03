#!/usr/bin/env python3
"""
curator_router.py — детерминированный роутер куратора
CURATOR_PROVIDER_FAILOVER_V1 | Phase 1
Дата: 2026-05-03
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

GOVERNANCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "governance")
ROUTING_JSON = os.path.join(GOVERNANCE, "state", "routing.json")
PROVIDER_STATUS = os.path.join(GOVERNANCE, "state", "provider_status.json")
ROUTING_DECISIONS = os.path.join(GOVERNANCE, "events", "routing_decisions.jsonl")
PROVIDER_FAILURES = os.path.join(GOVERNANCE, "events", "provider_failures.jsonl")
EXCHANGE = os.path.join(GOVERNANCE, "exchange.jsonl")


# === КЛАССИФИКАТОР ОШИБОК ===

FAILURE_PATTERNS = {
    "provider_limit": [
        "you've hit your limit",
        "rate limit",
        "resets at",
        "quota exceeded",
        "too many requests",
        "429",
        "usage limit",
        "reached the maximum",
    ],
    "api_error": [
        "500", "502", "503", "504",
        "internal server error",
        "service unavailable",
        "bad gateway",
        "api error",
    ],
    "config_error": [
        "missing secret",
        "invalid workflow",
        "yaml syntax",
        "not found",
        "no such file",
        "permission denied",
        "invalid token",
    ],
    "permission_error": [
        "403",
        "forbidden",
        "insufficient permissions",
        "requires admin",
    ],
    "timeout": [
        "timeout",
        "timed out",
        "deadline exceeded",
        "runner offline",
    ],
    "max_turns": [
        "reached maximum number of turns",
        "max turns",
        "max-turns",
    ],
}


def classify_error(error_text: str) -> str:
    """Классифицирует ошибку провайдера по тексту."""
    text = error_text.lower()
    for failure_type, patterns in FAILURE_PATTERNS.items():
        for pattern in patterns:
            if pattern in text:
                return failure_type
    return "unknown"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_jsonl(path, entry):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# === ОСНОВНАЯ ЛОГИКА РОУТЕРА ===

def record_failure(provider: str, failure_type: str, error_excerpt: str = ""):
    """Записывает ошибку провайдера и обновляет статус."""
    ts = now_iso()
    status = load_json(PROVIDER_STATUS)
    p = status["providers"][provider]

    p["last_failure_at"] = ts
    p["last_failure_type"] = failure_type
    p["failure_count"] = p.get("failure_count", 0) + 1
    if error_excerpt:
        p["last_error_excerpt"] = error_excerpt[:200]

    if failure_type in ("provider_limit", "api_error"):
        p["status"] = "limited" if failure_type == "provider_limit" else "error"
        if failure_type == "provider_limit":
            cooldown = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            p["cooldown_until"] = cooldown
    elif failure_type in ("config_error", "permission_error"):
        p["status"] = "config_error"
    elif failure_type == "timeout":
        p["status"] = "timeout"

    status["updated_at"] = ts
    save_json(PROVIDER_STATUS, status)

    append_jsonl(PROVIDER_FAILURES, {
        "timestamp": ts,
        "provider": provider,
        "failure_type": failure_type,
        "failure_count": p["failure_count"],
        "error_excerpt": error_excerpt[:200] if error_excerpt else ""
    })

    print(f"[ROUTER] Failure recorded: {provider} → {failure_type} (count={p['failure_count']})")
    return p["failure_count"]


def record_success(provider: str):
    """Записывает успех провайдера."""
    ts = now_iso()
    status = load_json(PROVIDER_STATUS)
    p = status["providers"][provider]
    p["status"] = "ok"
    p["last_success_at"] = ts
    p["failure_count"] = 0
    p["cooldown_until"] = None
    p["last_error_excerpt"] = None
    status["updated_at"] = ts
    save_json(PROVIDER_STATUS, status)
    print(f"[ROUTER] Success recorded: {provider}")


def should_switch(provider: str) -> bool:
    """Определяет нужно ли переключиться с данного провайдера."""
    try:
        routing = load_json(ROUTING_JSON)
        policy = routing.get("policy", {})
        switch_after = policy.get("switch_after_failures", 2)
        trigger_types = policy.get("failure_types_that_trigger_switch", ["provider_limit", "api_error"])

        status = load_json(PROVIDER_STATUS)
        p = status["providers"].get(provider, {})
        failure_count = p.get("failure_count", 0)
        last_failure_type = p.get("last_failure_type", "unknown")

        if last_failure_type in trigger_types and failure_count >= switch_after:
            return True

        if p.get("status") == "limited":
            cooldown = p.get("cooldown_until")
            if cooldown and now_iso() < cooldown:
                return True

        return False
    except Exception as e:
        print(f"[ROUTER] should_switch error: {e}")
        return False


def switch_provider(role: str, from_provider: str, to_provider: str, reason: str):
    """Переключает активного провайдера для роли."""
    ts = now_iso()
    routing = load_json(ROUTING_JSON)

    if role in routing["roles"]:
        routing["roles"][role]["active"] = to_provider
    routing["updated_at"] = ts

    save_json(ROUTING_JSON, routing)

    decision = {
        "timestamp": ts,
        "event_type": "ROUTING_UPDATE",
        "role": role,
        "from_provider": from_provider,
        "to_provider": to_provider,
        "reason": reason,
        "updated_by": "curator_router"
    }
    append_jsonl(ROUTING_DECISIONS, decision)
    append_jsonl(EXCHANGE, {**decision, "event_id": f"evt_routing_{ts.replace(':', '').replace('-', '')}"})

    print(f"[ROUTER] Switched {role}: {from_provider} → {to_provider} ({reason})")


def get_active_provider(role: str) -> str:
    """Возвращает активного провайдера для роли."""
    try:
        routing = load_json(ROUTING_JSON)
        return routing["roles"].get(role, {}).get("active", "claude")
    except Exception:
        return "claude"


def get_reserve_provider(role: str) -> str:
    """Возвращает резервного провайдера для роли."""
    try:
        routing = load_json(ROUTING_JSON)
        return routing["roles"].get(role, {}).get("reserve", "gpt")
    except Exception:
        return "gpt"


def route_role(role: str, error_text: str = "", success: bool = False) -> dict:
    """
    Главная функция роутера.
    Принимает роль и результат последнего запуска.
    Возвращает: {'provider': str, 'trigger': str, 'switched': bool}
    """
    trigger_map = {
        "analyst": {"claude": "@analyst", "gpt": "@gpt_analyst"},
        "auditor": {"claude": "@auditor", "gpt": "@gpt_auditor"},
        "executor": {"claude": "@executor", "gpt": "@gpt_executor"},
        "curator": {"claude": "@curator", "gpt": "@curator"},
    }

    active = get_active_provider(role)
    switched = False

    if success:
        record_success(active)
    elif error_text:
        failure_type = classify_error(error_text)
        count = record_failure(active, failure_type, error_text)

        if failure_type not in ("config_error", "permission_error", "timeout", "max_turns"):
            if should_switch(active):
                reserve = get_reserve_provider(role)
                switch_provider(role, active, reserve, f"{failure_type} after {count} failures")
                active = reserve
                switched = True

    trigger = trigger_map.get(role, {}).get(active, f"@{role}")

    append_jsonl(ROUTING_DECISIONS, {
        "timestamp": now_iso(),
        "event_type": "ROUTING_DECISION",
        "role": role,
        "active_provider": active,
        "trigger": trigger,
        "switched": switched,
        "reason": "success" if success else (classify_error(error_text) if error_text else "no_error_info")
    })

    return {"provider": active, "trigger": trigger, "switched": switched}


if __name__ == "__main__":
    # CLI: python curator_router.py <role> [--error "текст ошибки"] [--success]
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("role", help="analyst | auditor | executor | curator")
    parser.add_argument("--error", default="", help="Error text from last run")
    parser.add_argument("--success", action="store_true", help="Last run was successful")
    args = parser.parse_args()

    result = route_role(args.role, args.error, args.success)
    print(f"ROUTE_RESULT: provider={result['provider']} trigger={result['trigger']} switched={result['switched']}")
