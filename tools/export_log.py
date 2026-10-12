"""Claude Code session JSONL -> readable Markdown log: python export_log.py in.jsonl out.md"""
import json
import sys


def clip(s, n):
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False, indent=1)
    return s if len(s) <= n else s[:n] + f"\n... [{len(s) - n} more chars]"


def text_of(x):
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return "\n".join(text_of(i) for i in x)
    if isinstance(x, dict):
        return x.get("text") or text_of(x.get("content", "")) or ""
    return str(x)


out = []
user_turns = []


def user(text, ts, note=""):
    n = len(user_turns) + 1
    first = text.strip().splitlines()[0][:120]
    user_turns.append(f"{n}. [{ts} UTC{note}](#user-{n}) — {first}")
    quoted = "\n".join("> " + ln for ln in text.splitlines())
    out.append(f'\n---\n\n<a id="user-{n}"></a>\n## 🧑 USER REQUEST #{n} — {ts} UTC{note}\n\n{quoted}\n')

for line in open(sys.argv[1], encoding="utf-8"):
    d = json.loads(line)
    ts = d.get("timestamp", "")[:19].replace("T", " ")
    if d.get("type") == "attachment" and d["attachment"].get("type") == "queued_command":
        user(text_of(d['attachment']['prompt']), ts, " (sent while the agent was working)")
        continue
    msg = d.get("message")
    if d.get("type") not in ("user", "assistant") or not msg:
        continue
    content = msg["content"]
    if isinstance(content, str):
        if d["type"] == "user" and "<task-notification>" in content:
            out.append(f"\n_[system: background job finished — {ts} UTC]_\n")
        elif d["type"] == "user" and not d.get("isMeta") and not content.startswith("<"):
            user(content, ts)
        continue
    for c in content:
        t = c.get("type")
        if t == "text" and d["type"] == "user" and d.get("isMeta"):
            first = c["text"].splitlines()[0]
            out.append(f"\n_[skill instructions loaded into context: {first}]_\n")
        elif t == "text" and d["type"] == "user":
            if not c["text"].startswith("<"):
                user(c["text"], ts)
        elif t == "text":
            out.append(f"\n### 🤖 ASSISTANT — {ts} UTC\n\n{c['text']}\n")
        elif t == "thinking" and c.get("thinking"):
            out.append(f"\n<details><summary>assistant reasoning</summary>\n\n{c['thinking']}\n</details>\n")
        elif t == "tool_use":
            inp = dict(c["input"])
            desc = inp.pop("description", "")
            out.append(f"\n<details><summary>tool call: {c['name']} — {desc}</summary>\n\n```\n{clip(inp, 6000)}\n```\n</details>\n")
        elif t == "tool_result":
            out.append(f"\n<details><summary>tool result</summary>\n\n```\n{clip(text_of(c.get('content', '')), 3000)}\n```\n</details>\n")
        elif t == "advisor_tool_result":
            out.append("\n**[Reviewer model (advisor) consulted — its reply is stored encrypted in the session "
                       "file; the next assistant message states what it changed]**\n")

head = ["# AI interaction log — Claude Code (Opus 5.5)\n",
        "User requests are numbered and quoted; assistant replies are shown in full; tool calls and "
        "their outputs are collapsed under each step.\n", "## Index of user requests\n", *user_turns, ""]
out = head + out
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(out))
print(sys.argv[2], sum(len(x) for x in out), "chars")
