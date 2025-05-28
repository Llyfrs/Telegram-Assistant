import os
import uuid
import json
from typing import Literal

from zep_cloud.client import Zep
from zep_cloud.types import Message


class Memory:

    def __init__(self, user_id, api_key=None, first_name=None):
        self.api_key = api_key or os.environ.get('ZEP_API_KEY')

        if not self.api_key:
            raise ValueError("ZEP_API_KEY not provided or not found in environment.")

        self.user_id = user_id
        self.client = Zep(api_key=self.api_key)

        # Create or ensure user exists

        try:
            self.client.user.add(
                user_id=user_id,
                first_name=first_name,
            )
        except Exception as e:
            # If user already exists, we can ignore the error
            if "already exists" not in str(e):
                raise e

        # Initialize a session
        self.session_id = self._create_session()

    def _create_session(self):
        session_id = uuid.uuid4().hex
        self.client.memory.add_session(
            session_id=session_id,
            user_id=self.user_id,
        )
        return session_id

    def reset_session(self):
        """Create a new session ID and reset memory context."""
        self.session_id = self._create_session()

    def add_message(self, role, content, role_type="user"):
        message = Message(
            role=role,
            content=content,
            role_type=role_type
        )

        self.client.memory.add(session_id=self.session_id, messages=[message], ignore_roles=["system", "tool"])

    def get_memory(self):

        memory = self.client.memory.get(session_id=self.session_id, lastn=50)

        return {
            "context": memory.context,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "role_type": msg.role_type
                }
                for msg in memory.messages
            ]
        }

    def clear_memory(self):
        """Resets the memory by starting a new session (keeps same user)."""
        self.reset_session()

    def add_text_to_graph(self, text):
        return self.client.graph.add(
            user_id=self.user_id,
            type="text",
            data=text
        )

    def add_json_to_graph(self, json_obj):
        return self.client.graph.add(
            user_id=self.user_id,
            type="json",
            data=json.dumps(json_obj)
        )


    def search_graph(self, query : str, scope : Literal["edges", "nodes"], limit : int =5):

        results = self.client.graph.search(
            user_id=self.user_id,
            query=query,
            scope=scope,
            limit=limit
        )

        return str(results)
