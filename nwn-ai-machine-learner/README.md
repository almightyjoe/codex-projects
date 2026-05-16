# NWN AI Machine Learner

Machine-learning-oriented upgrade of NWN-AI for Higher Grounds / Neverwinter Nights log analysis.

The goal is not to let an LLM guess at raw combat logs. The parser remains deterministic. The learning loop records unknown or ambiguous log lines, clusters them, asks an LLM for reviewable rule suggestions, and turns approved rules into regression cases.

## Core Questions

- What killed me?
- What damage types am I taking most?
- What spell or special attack caused a death?
- What save, skill, or ability check defends against that attack?
- What damage should we use against a specific mob?
- What strategy fits the current area and party?
- Which parser edge cases are still unhandled?

## Run

```bat
start_nwn_ai.bat
```

The launcher creates a virtual environment, installs requirements, starts the server, and opens the dashboard.

## Learning Loop

1. Unparsed lines are saved to `unparsed_lines`.
2. Repeated patterns are grouped by `bucket`.
3. The learning analyzer writes reviewable candidates to `parser_rule_candidates`.
4. Approved rules and regression examples become durable parser knowledge.

