# CodePro / OpenHands — Universal Setup Prompt for Antigravity

This file contains the exact master prompt to give to **Antigravity** on a new laptop after cloning this repository from GitHub. It automatically inspects the system, installs all prerequisites and dependencies, sets up the offline LLM configurations (with nothink mode and clean outputs), and launches the complete full-stack environment.

---

## 📋 Copy & Paste This Exact Prompt to Antigravity

```markdown
You are setting up and running CodePro (OpenHands) on this machine from scratch. Please perform the full setup and verification autonomously:

1. System & Prerequisite Diagnostics:
   - Check if Node.js (>= 18), npm, Git, and Python (>= 3.10) are installed.
   - Check if `uv` and `uvx` are installed and on PATH. If missing:
     * Windows (PowerShell): run `irm https://astral.sh/uv/install.ps1 | iex`
     * macOS / Linux: run `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Check if Ollama is installed and running (`http://127.0.0.1:11434/api/tags`).
     * If Ollama is running, check which models are pulled. If `qwen2.5-coder:latest`, `gemma3:4b`, or `qwen3.5:4b` are missing, notify the user or pull `qwen2.5-coder:latest`.

2. Install Project Dependencies:
   - Run `npm ci` (or `npm install`) in the repository root to install all frontend dependencies (including cross-env, react-router, etc.).

3. Configure Offline Models & Nothink Settings:
   - Create/verify `~/.openhands/profiles/` directory and ensure local profiles are configured for Ollama models (e.g. `qwen2.5-coder`, `gemma3-4b`, `qwen3.5-4b`) with:
     * `base_url`: "http://127.0.0.1:11434"
     * `api_key`: a dummy placeholder string (so local models bypass the cloud API key requirement)
     * `litellm_extra_body`: `{"think": false}`
     * `reasoning_effort`: null
     * `extended_thinking_budget`: null
   - Ensure `~/.openhands/settings.json` has `agent_settings.llm` pointing to the default local model with `litellm_extra_body: {"think": false}`, `reasoning_effort: null`, and `extended_thinking_budget: null`.

4. Verify Code Integrity & Patches:
   - Ensure `src/hooks/use-llm-configured.ts` recognizes Ollama models as configured without requiring external cloud API keys.
   - Ensure `tools/canvas_ui_tool.py` includes the LiteLLM patch that:
     * Resolves the `PromptTokensDetailsWrapper.cache_creation_tokens` AttributeError.
     * Enforces `think: false` and strips reasoning budget parameters for all Ollama/port 11434 models.
     * Unwraps any JSON output containing `thought`, `summary`, or `message` into clean text.
   - Ensure `src/components/conversation-events/chat/event-thought-helpers.ts` extracts clean message content and suppresses internal thinking blocks for nothink mode.
   - Run `npx vitest run __tests__/components/conversation-events/chat/event-thought-helpers.test.ts` to verify tests pass.

5. Launch the Development Stack:
   - Start the stack as a background daemon: `node scripts/dev-with-automation.mjs`.
   - Monitor the logs until:
     * Ingress proxy is ready on http://localhost:8000/
     * Agent server is ready on http://127.0.0.1:18000/
     * Automation backend is ready on http://127.0.0.1:18001/
     * Vite frontend is ready on http://localhost:3001/
   - Open http://localhost:8000/ in the browser and confirm the application is up and ready for chatting.
```

---

## 🛠️ Step-by-Step Breakdown (What the Prompt Automates)

| Step | Action | Description |
|---|---|---|
| **1. Toolchains** | `uv`, `node`, `python` | Installs modern Python toolchain (`uv`/`uvx`) and ensures npm packages are installed cleanly. |
| **2. Local LLM Setup** | `Ollama` | Verifies Ollama connectivity on port `11434` and configures offline models. |
| **3. Offline Unblocking** | `use-llm-configured.ts` | Allows users to chat immediately with local models without nagging for OpenAI/Anthropic API keys. |
| **4. Thinking Prevention** | `think: false` | Passes `think: false` to Ollama so models do not generate slow thinking tokens or fail with `"model does not support thinking"`. |
| **5. Clean Output Filter** | `splitInlineThink` | Unwraps raw JSON outputs emitted by local models (`{"thought": ..., "message": ...}`) into pure markdown text with zero thinking box clutter. |
| **6. Full-Stack Runner** | `dev-with-automation.mjs` | Spawns ingress proxy, agent backend, automation service, and frontend in one command. |
