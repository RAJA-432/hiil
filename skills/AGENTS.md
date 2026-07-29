# AGENTS.md — Operating Manual

## Conventions

- All monetary values in USD, 2 decimal places.
- Quote line items: quantity × unit_price = line_total. No LLM-guessed math.
- Volume discount thresholds: >$10,000 → 5%; >$50,000 → 10%; >$100,000 → 15%.
- Approval required before: (a) saving a mail draft, (b) adding a new customer.
- Use `/skills/playbooks/<task>.md` for step-by-step workflows.
- Mark steps complete with `mark_step_done(step_number)` after finishing each step.
- Read this file and the relevant playbook at the start of every task.

## Subagents

| Agent | Role | Tools | Memory Files |
|-------|------|-------|-------------|
| **chinook-analyst** | Database analyst — run SQL queries against the Chinook database | `read_query`, `list_tables`, `describe_table` | AGENTS.md, playbooks |
| **inbox-manager** | Mail manager — triage inbox, compose and save drafts | `list_messages`, `get_message`, `send_draft` (gated), `save_draft` (gated) | AGENTS.md, playbooks |
| **quote-reviewer** | Quote sanity checker — verify line-item math, discount %, and grand total | `read_file`, `calculate_quote` (read-only check), `search_files` | AGENTS.md, rfq-quote.md |
| **genre-researcher** | Newsletter researcher — gather and summarize content for one genre | `web_search`, `web_fetch`, `summarize` | AGENTS.md, newsletter.md |

## Orchestration Rules

- The main agent reads the relevant playbook, then spawns subagents as needed.
- **Sequential** subagents: run one after another when order matters (e.g., discovery → pricing → review).
- **Parallel** subagents: fan out when independent (e.g., one genre-researcher per newsletter section). Stitch results after all complete.
- When a subagent returns `status=waiting`, present the pending_interrupt to the user for approval, then call resume() with the decision.
