"""Legacy conversation compatibility for the former Python Canvas UI tool.

New conversations define ``canvas_ui_control`` through the agent-server's
``client_tools`` JSON API. The distinct name avoids colliding with this
process-global legacy registration. This module remains importable because
persisted conversations store
``tool_module_qualnames = {"canvas_ui": "canvas_ui_tool"}`` and may contain
``CanvasUIAction`` / ``CanvasUIObservation`` events. Agent-server imports the
module before restoring those conversations so the legacy event kinds and tool
registration remain resolvable.

The server-side executor is a no-op that returns an acknowledgment. The actual
UI effect happens client-side: the frontend watches the WebSocket stream for
legacy ``canvas_ui`` and current ``canvas_ui_control`` ActionEvents and dispatches
the command.

The launchers also import this module at agent-server startup
(``--import-modules canvas_ui_tool``) so the builtin ``FinishTool`` registration
at the bottom runs before any conversation is created.
"""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from openhands.sdk import Action, Observation, ToolDefinition
from openhands.sdk.tool import (
    FinishTool,
    ToolAnnotations,
    ToolExecutor,
    list_registered_tools,
    register_tool,
)


CanvasCommand = Literal["navigate_to_file", "open_tab", "show_preview"]
CanvasTab = Literal[
    "files", "browser", "vscode", "terminal", "planner", "tasklist"
]


class CanvasUIAction(Action):
    """Direct the Agent Canvas frontend to perform a UI action."""

    command: CanvasCommand = Field(description="UI command to dispatch.")
    path: str | None = Field(
        default=None,
        description=(
            "Workspace-relative file path. Required for navigate_to_file and "
            "show_preview; ignored otherwise."
        ),
    )
    tab: CanvasTab | None = Field(
        default=None,
        description=(
            "Tab to open. Required for open_tab; ignored otherwise. One of "
            "files, browser, vscode, terminal, planner, tasklist."
        ),
    )


class CanvasUIObservation(Observation):
    """Acknowledgment that the UI command was dispatched to the frontend."""


class CanvasUIExecutor(ToolExecutor[CanvasUIAction, CanvasUIObservation]):
    def __call__(
        self,
        action: CanvasUIAction,
        conversation=None,  # noqa: ARG002
    ) -> CanvasUIObservation:
        return CanvasUIObservation.from_text(
            f"UI command '{action.command}' dispatched to the Agent Canvas frontend."
        )


_CANVAS_UI_DESCRIPTION = """The user is interacting with you inside Agent Canvas — a web UI with a chat panel on the left and a tabbed right-side panel (files, terminal, browser, vscode, planner, tasklist). This tool lets you drive that right-side panel so the user sees what you just produced.

They will NOT see the files you wrote, the terminal output, or the browser
unless you call this tool to switch the right-side panel to the relevant
tab. Call this every time you finish work that produces something the user
should look at — don't rely on them noticing on their own.

When to call (pick the most specific option that matches your last action):

* You wrote or modified a single file (ANY language, ANY size — including
  small scripts like a hello-world bash file) →
    command="navigate_to_file", path=<workspace-relative path of that file>

* You generated an HTML page, image, SVG, PDF, markdown report, or other
  previewable artifact →
    command="show_preview", path=<that file>

* You finished editing multiple files in one logical step →
    command="open_tab", tab="files"
    (The Files tab automatically renders a diff view when the workspace has
    uncommitted git changes, which covers the "highlight changes" case.)

* You ran a long-running terminal command, or one whose output the user
  should inspect →
    command="open_tab", tab="terminal"

* You browsed to a URL the user should see →
    First call browser_get_state(include_screenshot=true) after your final
    browser interaction so Agent Canvas has a screenshot to display, then call
    command="open_tab", tab="browser"
    (browser_navigate alone only updates the URL; without browser_get_state,
    the Browser tab will open without a screenshot.)

Call this BEFORE writing your chat-message summary of the change, so the
artifact is visible while the user reads what you did. One canvas_ui call
per logical step is enough — don't repeat it for the same file or tab in
the same turn."""


class CanvasUITool(ToolDefinition[CanvasUIAction, CanvasUIObservation]):
    """Tool for controlling the Agent Canvas UI from the agent."""

    @classmethod
    def create(
        cls,
        conv_state=None,  # noqa: ARG003
        **params,  # noqa: ARG003
    ) -> Sequence["CanvasUITool"]:
        return [
            cls(
                description=_CANVAS_UI_DESCRIPTION,
                action_type=CanvasUIAction,
                observation_type=CanvasUIObservation,
                executor=CanvasUIExecutor(),
                annotations=ToolAnnotations(
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


# Persisted pre-client_tools conversations import this module by qualname before
# restoring their agent and events. Keep the registration until those records
# have a server-side migration path.
register_tool("canvas_ui", CanvasUITool)


# openhands-automation >= 1.9.0 preset entrypoints build their agent with
# get_default_agent(finish_tool_response_schema=TaskOutcome). That registers the
# SDK's builtin FinishTool only inside the entrypoint's own process and
# advertises it to the agent-server as `openhands.sdk.tool.builtins.finish` — a
# module that does not self-register — so the remote conversation every Agent
# Canvas automation run dispatches fails with "ToolDefinition 'FinishTool' is
# not registered". Registering the plain builtin here is enough: resolve_tool()
# strips `response_schema` before FinishTool.create() and re-applies it. Drop
# this once the SDK registers its builtins for remote conversations.
if FinishTool.__name__ not in list_registered_tools():
    register_tool(FinishTool.__name__, FinishTool)


# LiteLLM compatibility patch:
# In some LiteLLM versions, PromptTokensDetailsWrapper deletes cache_creation_tokens
# when it is None during __init__, but Pydantic leaves it in model_fields_set.
# When openhands.sdk.llm.utils.telemetry accesses prompt_details.cache_creation_tokens,
# an AttributeError is raised. This fallback ensures attribute access returns None instead of raising.
try:
    from litellm.types.utils import PromptTokensDetailsWrapper

    _orig_prompt_tokens_getattr = getattr(PromptTokensDetailsWrapper, "__getattr__", None)

    def _safe_prompt_tokens_getattr(self, name: str):
        if name in ("cache_creation_tokens", "cache_write_tokens"):
            return None
        if _orig_prompt_tokens_getattr:
            return _orig_prompt_tokens_getattr(self, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    PromptTokensDetailsWrapper.__getattr__ = _safe_prompt_tokens_getattr
except Exception:
    pass


# LiteLLM Ollama thinking compatibility and clean output patch:
# 1. Enforces "nothink" mode by stripping thinking budget params and setting think: False in extra_body.
# 2. Ensures prompt instructions discourage models from wrapping chat replies in raw JSON.
# 3. Unwraps any JSON responses containing thought/summary/message so the user receives clean text output.
try:
    import json
    import re
    import litellm

    _orig_litellm_completion = litellm.completion
    _orig_litellm_acompletion = litellm.acompletion

    def _unwrap_json_content(content):
        if not content or not isinstance(content, str):
            return content, None
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = re.sub(r"^```json\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        elif cleaned.startswith("```"):
            cleaned = re.sub(r"^```\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        if not (cleaned.startswith("{") and cleaned.endswith("}")):
            return content, None

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                thought = data.get("thought") or data.get("thinking") or data.get("reasoning")
                message = data.get("message") or data.get("response") or data.get("text") or data.get("answer") or data.get("content")
                if thought or message:
                    msg_str = str(message).strip() if message else None
                    thought_str = str(thought).strip() if thought else None
                    final_content = msg_str if msg_str else thought_str
                    return final_content, thought_str
        except Exception:
            pass
        return content, None

    def _prepare_ollama_call(kwargs):
        model = kwargs.get("model", "")
        api_base = str(kwargs.get("api_base", "") or "")
        if isinstance(model, str) and ("ollama" in model.lower() or "11434" in api_base):
            for param in ["reasoning_effort", "extended_thinking_budget", "thinking"]:
                kwargs.pop(param, None)
            extra_body = kwargs.get("extra_body")
            if extra_body is None:
                kwargs["extra_body"] = {"think": False}
            elif isinstance(extra_body, dict):
                extra_body["think"] = False
        return kwargs

    def _process_response(resp):
        try:
            if hasattr(resp, "choices") and resp.choices:
                choice = resp.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    unwrapped_content, thought = _unwrap_json_content(choice.message.content)
                    if unwrapped_content != choice.message.content:
                        choice.message.content = unwrapped_content
                        if thought and not getattr(choice.message, "reasoning_content", None):
                            setattr(choice.message, "reasoning_content", thought)
        except Exception:
            pass
        return resp

    def _patched_litellm_completion(*args, **kwargs):
        kwargs = _prepare_ollama_call(kwargs)
        resp = _orig_litellm_completion(*args, **kwargs)
        return _process_response(resp)

    async def _patched_litellm_acompletion(*args, **kwargs):
        kwargs = _prepare_ollama_call(kwargs)
        resp = await _orig_litellm_acompletion(*args, **kwargs)
        return _process_response(resp)

    litellm.completion = _patched_litellm_completion
    litellm.acompletion = _patched_litellm_acompletion
except Exception:
    pass

