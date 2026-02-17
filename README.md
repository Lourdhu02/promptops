# PromptOps

> Git-style version control for LLM prompts — commit, diff, rollback, and deploy prompts like code.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-alpha-orange.svg)

---

## What is PromptOps?

PromptOps is an open-source framework that brings software engineering discipline to LLM prompt management. Track every change, evaluate quality, run A/B tests, and deploy prompts to production — without touching your application code.

---

## Features

- **Version Control** — commit, branch, diff, and rollback prompts like Git
- **Evaluation Engine** — score prompts on accuracy, hallucination rate, and latency
- **A/B Testing** — compare prompt versions against live traffic with statistical confidence
- **Deploy API** — update prompts in production with zero code redeployment
- **Team Collaboration** — PR-style reviews and approval workflows
- **Integrations** — works with LangChain, LlamaIndex, OpenAI, Ollama, and HuggingFace

---

## Quick Start

```bash
pip install promptops

promptops init
promptops add my_prompt.yaml
promptops commit -m "Initial version"
promptops eval run
promptops deploy prod
```

---

## CLI Commands

| Command | Description |
|---|---|
| `promptops init` | Initialize a new project |
| `promptops add <file>` | Stage a prompt file |
| `promptops commit -m <msg>` | Commit staged prompts |
| `promptops log` | View version history |
| `promptops diff <v1> <v2>` | Compare two versions |
| `promptops rollback` | Revert to last stable version |
| `promptops eval run` | Run evaluation pipeline |
| `promptops deploy <env>` | Deploy to dev / staging / prod |
| `promptops abtest start` | Start an A/B test |

---

## Prompt File Format

```yaml
name: customer-support
version: 1.0.0
model: gpt-4
temperature: 0.7
tags: [support, v1]
content: |
  You are a helpful, professional customer support agent.
  Answer clearly and concisely.
```

---

## Tech Stack

- **Backend** — Python, FastAPI, PostgreSQL, Redis
- **Versioning** — pygit2 (libgit2)
- **Evaluation** — RAGAS
- **Integrations** — LangChain, LlamaIndex, OpenAI, Ollama
- **Dashboard** — React, Tailwind CSS

---

## Project Status

| Phase | Status |
|---|---|
| CLI — version control | 🔧 In Progress |
| Evaluation Engine | 📅 Planned |
| Deploy API | 📅 Planned |
| Web Dashboard | 📅 Planned |

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

---

## License

MIT © 2025 PromptOps Contributors
