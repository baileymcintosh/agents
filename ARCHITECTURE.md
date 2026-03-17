# Architecture

## Workflow

```mermaid
flowchart TD
    U([Bailey]) -->|project brief| CC[Claude Code\nOrchestrator]
    CC -->|proposes team| U
    U -->|approves| CC
    CC -->|triggers| P[prelim.yml\nGitHub Actions]

    subgraph Prelim Run - cheap models, <10 min
        P --> QB1[qual_builder\nGroq Llama 3.3 70B\nweb search]
        P --> QT1[quant_builder\nClaude Sonnet\nPython + data]
        QB1 & QT1 --> R1[reporter\nClaude Sonnet]
    end

    R1 -->|pushes outputs| PR[(project repo\nbaileymcintosh/project-name)]
    CC -->|notifies + link| U
    U -->|feedback| CC
    CC -->|triggers| D[deep.yml\nGitHub Actions]

    subgraph Deep Run - full models
        D --> QB2[qual_builder\nGPT-4o]
        D --> QT2[quant_builder\nClaude Sonnet]
        QB2 & QT2 --> V[verifier\nClaude Sonnet]
        V --> R2[reporter\nClaude Sonnet]
    end

    R2 -->|pushes outputs| PR
    CC -->|notifies + link| U
```

## Agent roles

| Agent | Model (prelim) | Model (deep) | Purpose |
|---|---|---|---|
| team_planner | Claude Opus | Claude Opus | Reads brief, proposes custom team |
| qual_builder | Groq Llama 3.3 70B | GPT-4o | Web search, news, policy, narrative |
| quant_builder | Claude Sonnet | Claude Sonnet | Python execution, live data, charts |
| verifier | Groq Llama | Claude Sonnet | QA and fact-checking |
| reporter | Claude Sonnet | Claude Sonnet | Synthesis → report + notebook |
| debugger | Claude Opus | Claude Opus | Failure recovery |

## Data sources

| Source | Access | Used by |
|---|---|---|
| Tavily | API | qual_builder — web search |
| yfinance | pip | quant_builder — equity/commodity prices |
| FRED | API | quant_builder — macro data |
| EIA | API | quant_builder — energy data |
| Kalshi | API | quant_builder — prediction markets |

## Project repo structure

Each project gets its own GitHub repo:
```
baileymcintosh/<project-name>/
  BRIEF.md          original task brief
  PLAN.md           proposed team + research goals
  FEEDBACK.md       feedback between runs
  reports/          agent outputs (Markdown + .ipynb)
  data/             raw data files
  notebooks/        interactive notebooks
```
