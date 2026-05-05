# GPT Action Ingress Bridge

`ingress_bridge.py` moves a pasted `GPT_REPO_ACTION_V1` JSON block into the relay inbox.

Flow:

1. Paste raw JSON or fenced `GPT_REPO_ACTION_V1` block into:
   `governance/state/gpt_relay_pastebox.txt`
2. Run:
   `python3 tools/gpt-autonomy-relay/ingress_bridge.py --once`
3. The bridge writes:
   `governance/state/gpt_relay_inbox/<trace_id>.json`
4. `relay_watch.py --loop` processes it automatically.
