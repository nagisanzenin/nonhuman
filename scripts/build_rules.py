"""Render skills/nonhuman/SKILL.md (single source) into rule files for platforms that use plain instructions.
usage: python3 scripts/build_rules.py   (run after editing SKILL.md; CI-free)"""
import os, re
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(R, "skills", "nonhuman", "SKILL.md")).read()
fm, body = re.match(r"---\n(.*?)\n---\n(.*)", src, re.S).groups()
desc = re.search(r"description: (.*)", fm).group(1)
out = {
    "AGENTS.md": body,                                   # Codex, OpenCode, Amp, Jules, Goose, Cursor, generic
    "GEMINI.md": body,                                   # Gemini CLI (extension contextFileName) / Antigravity
    "cursor/nonhuman.mdc": f"---\ndescription: {desc}\nalwaysApply: true\n---\n{body}",
    "windsurf/nonhuman.md": f"---\ntrigger: always_on\n---\n{body}",
    "cline/nonhuman.md": body,
    "copilot/copilot-instructions.md": body,
    "kiro/nonhuman.md": f"---\ninclusion: always\n---\n{body}",
}
for p, c in out.items():
    f = os.path.join(R, "rules", p); os.makedirs(os.path.dirname(f), exist_ok=True); open(f, "w").write(c)
print("\n".join("rules/" + p for p in out))
