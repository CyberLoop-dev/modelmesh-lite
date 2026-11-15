#!/usr/bin/env python3
"""Route a chat request across OpenAI-compatible endpoints with explicit fallbacks."""
import argparse, json, os, sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from pathlib import Path

def send(provider, prompt, timeout):
    key = os.environ.get(provider.get("api_key_env", ""), "")
    if not key: raise RuntimeError("missing environment variable " + provider.get("api_key_env", ""))
    base = provider["base_url"].rstrip("/")
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    body = {"model": provider["model"], "messages": [{"role":"user","content":prompt}], "stream": False}
    req = Request(url, data=json.dumps(body).encode(), headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    with urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode())
    return data["choices"][0]["message"]["content"]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--task", default="general")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()
    try: config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: ap.error(str(exc))
    order = config.get("routes", {}).get(args.task, config.get("routes", {}).get("general", []))
    providers = {p["name"]: p for p in config.get("providers", [])}
    if not order: ap.error("No provider route configured for task")
    errors = []
    for name in order:
        if name not in providers: errors.append(name + ": not defined"); continue
        try:
            answer = send(providers[name], args.prompt, args.timeout)
            print(json.dumps({"provider":name,"model":providers[name]["model"],"content":answer}, ensure_ascii=False))
            return 0
        except (KeyError, RuntimeError, HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors.append(name + ": " + str(exc))
    print("All providers failed: " + " | ".join(errors), file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main())
