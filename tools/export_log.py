"""Claude Code session JSONL -> readable Markdown log.

python tools/export_log.py in.jsonl out.md [--redact term1,term2]

Confidential data is redacted from the whole output (see redact()); extra private terms
(e.g. names of other machines) are passed on the command line so they never live in the repo.
"""
import json
import re
import sys

# Public addresses that are part of the work itself (repo remotes, commit co-author) are kept.
KEEP_EMAILS = ("git@github.com", "git@gitlab.com", "noreply@anthropic.com")


def redact(text, extra_terms=()):
    """Replace personal and machine-identifying data with visible [REDACTED: ...] markers."""
    fragments = set()

    def email(m):
        if m.group(0).endswith(KEEP_EMAILS):
            return m.group(0)
        local, domain = m.group(0).split("@")
        fragments.add(re.escape(local))
        # first two domain labels, also when written with escaped dots in commands
        fragments.add(r"(?:\\)*\.".join(map(re.escape, domain.split(".")[:2])))
        return "[REDACTED: email]"

    def uid(m):
        fragments.add(m.group(0)[:8])
        return "[REDACTED: id]"
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email, text)
    text = re.sub(r"(?:ssh-(?:ed25519|rsa|dss)|ecdsa-sha2-nistp\d+)\s+AAAA[0-9A-Za-z+/]+={0,3}",
                  "[REDACTED: SSH public key]", text)
    text = re.sub(r"AAAA[BC]3NzaC1[0-9A-Za-z+/]{20,}={0,3}", "[REDACTED: key material]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED: IP]", text)
    text = re.sub(r"/tmp/claude-\d+/[^/\s\"']+/[0-9a-f-]{36}/scratchpad", "<scratchpad>", text)
    text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", uid, text)
    # Fragments of redacted values that appear on their own (e.g. inside search commands).
    for frag in fragments:
        text = re.sub(frag, "[REDACTED: fragment]", text)
    text = re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text)
    text = re.sub(r"-home-[A-Za-z0-9_.]+-", "-home-~-", text)
    for term in extra_terms:
        text = re.sub(re.escape(term), "[REDACTED: private name]", text)
    return text


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
        text = text_of(d['attachment']['prompt'])
        if "<task-notification>" in text:
            out.append(f"\n_[system: background job event — {ts} UTC]_\n")
        else:
            user(text, ts, " (sent while the agent was working)")
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
        "> **Redaction note.** Confidential data was removed automatically by `tools/export_log.py` "
        "before publishing: e-mail addresses, SSH public keys, IP addresses, session/organisation IDs, "
        "local user paths and names of other machines. Each removal is marked `[REDACTED: …]` "
        "(paths become `~` / `<scratchpad>`). Nothing else was edited.\n",
        "<!-- Redacted at the user's request on 2026-10-12; see redact() in tools/export_log.py. -->\n",
        "User requests are numbered and quoted; assistant replies are shown in full; tool calls and "
        "their outputs are collapsed under each step.\n", "## Index of user requests\n", *user_turns, ""]
out = head + out
extra = []
if "--redact" in sys.argv:
    extra = [t for t in sys.argv[sys.argv.index("--redact") + 1].split(",") if t]
open(sys.argv[2], "w", encoding="utf-8").write(redact("\n".join(out), extra))
print(sys.argv[2], sum(len(x) for x in out), "chars")
