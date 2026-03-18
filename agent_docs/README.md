# Agent Prompts

Each `.md` file in this directory is the system prompt for the corresponding agent.

If the file exists here, it **overrides** the default inline prompt in the agent's Python file.
Edit these files to tune agent behaviour without touching code.

| File | Agent | Model |
|---|---|---|
| `qual_builder.md` | Qualitative researcher | gpt-4o-mini (deep) / llama-3.3-70b (prelim) |
| `quant_builder.md` | Quantitative analyst | claude-haiku-4-5 (both modes) |
| `reporter.md` | Senior editor / synthesiser | claude-sonnet-4-6 (deep) / llama-3.3-70b (prelim) |
| `qa_editor.md` | Pre-publication QA reviewer | same as verifier |
| `team_planner.md` | Team design planner | claude-sonnet-4-6 |
| `debugger.md` | Inline error recovery | gpt-4o-mini |

## How overrides work

Each agent calls `_load_system_prompt()` at init time. It checks:

```python
prompt_path = config.AGENT_DOCS_DIR / "<agent_name>.md"
if prompt_path.exists():
    return prompt_path.read_text(encoding="utf-8")
# else: use inline default
```

`AGENT_DOCS_DIR` defaults to `agent_docs/` at the repo root.
