from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic_ai import Agent


@dataclass
class QueuedMessage:
    """Represents a message the agent wants to send to the user."""

    chat_id: int
    text: str
    markdown: bool = True
    clean: bool = False


class AgentRuntime:
    """Coordinates interactions between the main agent and external channels."""

    def __init__(self, default_chat_id: Optional[int] = None):
        self._agent: Optional[Agent] = None
        self._history: List[Dict[str, Any]] = []
        self._outgoing: List[QueuedMessage] = []
        self._default_chat_id: Optional[int] = default_chat_id

    def attach_agent(self, agent: Agent) -> None:
        """Attaches the instantiated agent to this runtime."""

        self._agent = agent

    def reset_history(self) -> None:
        """Clears the conversation history tracked for the agent."""

        self._history = []

    def set_default_chat(self, chat_id: int) -> None:
        """Updates the default chat used when the agent sends a message."""

        self._default_chat_id = chat_id

    def queue_outgoing_message(
        self,
        text: str,
        chat_id: Optional[int] = None,
        markdown: bool = True,
        clean: bool = False,
    ) -> str:
        """Queues an outgoing message for later delivery via the bot."""

        target_chat = chat_id or self._default_chat_id
        if target_chat is None:
            raise ValueError("No chat_id provided and no default chat configured.")

        self._outgoing.append(
            QueuedMessage(
                chat_id=target_chat,
                text=text,
                markdown=markdown,
                clean=clean,
            )
        )

        return "Message queued for delivery"

    def drain_outgoing(self) -> List[QueuedMessage]:
        """Returns and clears all queued outgoing messages."""

        queued = list(self._outgoing)
        self._outgoing.clear()
        return queued

    async def run(self, message: Any) -> Any:
        """Executes the agent with the provided message and managed history."""

        if self._agent is None:
            raise RuntimeError("Agent has not been attached to the runtime.")

        response = await self._agent.run(message, message_history=self._history)
        self._history = response.all_messages()
        return response

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns the currently tracked conversation history."""

        return list(self._history)
