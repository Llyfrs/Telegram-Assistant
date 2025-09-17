import os
import uuid
import json
from typing import Literal, List, Dict, Any
import datetime

try:
    from mem0 import Memory as Mem0Memory
except ImportError:
    # Fallback for environments where mem0ai is not installed
    class Mem0Memory:
        def __init__(self, config=None):
            self.messages = []
            self.memories = []
            self.context = ""
            
        def add(self, messages, user_id=None, agent_id=None, run_id=None, metadata=None):
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            self.messages.extend(messages)
            # Generate a simple context from recent messages
            self.context = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
                                    for msg in self.messages[-10:]])
            return []
            
        def get_all(self, user_id=None, agent_id=None, run_id=None, limit=None):
            return self.memories
            
        def search(self, query, user_id=None, agent_id=None, run_id=None, limit=10):
            # Simple keyword search fallback
            results = []
            query_lower = query.lower()
            for memory in self.memories:
                if query_lower in memory.get('memory', '').lower():
                    results.append(memory)
            return results[:limit]
            
        def delete_all(self, user_id=None, agent_id=None, run_id=None):
            self.memories.clear()
            self.messages.clear()
            self.context = ""


class Memory:

    def __init__(self, user_id, api_key=None, first_name=None):
        self.user_id = user_id
        self.first_name = first_name or "User"
        self.session_id = self._create_session()
        
        # Initialize mem0 with local SQLite storage
        config = {
            "vector_store": {
                "provider": "sqlite",
                "config": {
                    "path": f"memory_db_{user_id}.db"
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.1
                }
            }
        }
        
        # Only use API key if provided, otherwise mem0 will use environment variables
        if api_key:
            config["llm"]["config"]["api_key"] = api_key
        
        self.client = Mem0Memory(config=config)
        
        # Store messages for session-based context
        self.messages = []

    def _create_session(self):
        """Create a new session ID."""
        return uuid.uuid4().hex

    def reset_session(self):
        """Create a new session ID and reset memory context."""
        self.session_id = self._create_session()
        self.messages = []

    def add_message(self, role, content, role_type="user"):
        """Add a message to the current session and to long-term memory."""
        message = {
            "role": role,
            "content": content,
            "role_type": role_type,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add to session messages
        self.messages.append(message)
        
        # Keep only last 50 messages in session
        if len(self.messages) > 50:
            self.messages = self.messages[-50:]
        
        # Add to long-term memory using mem0
        # Only add meaningful content (not system messages)
        if role_type not in ["system", "tool"] and content.strip():
            try:
                self.client.add(
                    messages=content,
                    user_id=self.user_id,
                    metadata={
                        "role": role,
                        "role_type": role_type,
                        "session_id": self.session_id,
                        "timestamp": message["timestamp"]
                    }
                )
            except Exception as e:
                print(f"Warning: Failed to add message to long-term memory: {e}")

    def get_memory(self):
        """Get current session memory and context."""
        # Generate context from recent messages
        context = ""
        
        try:
            # Get relevant memories from mem0
            memories = self.client.get_all(user_id=self.user_id, limit=20)
            if memories:
                context_parts = []
                for memory in memories:
                    if isinstance(memory, dict) and 'memory' in memory:
                        context_parts.append(memory['memory'])
                    elif hasattr(memory, 'memory'):
                        context_parts.append(memory.memory)
                    else:
                        context_parts.append(str(memory))
                
                context = "Relevant memories:\n" + "\n".join(context_parts[:10])
        except Exception as e:
            print(f"Warning: Failed to get memories from mem0: {e}")
            # Fall back to session context
            context = "Recent conversation:\n" + "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in self.messages[-10:]
            ])

        return {
            "context": context,
            "messages": self.messages
        }

    def clear_memory(self):
        """Resets the memory by starting a new session and clearing long-term memory."""
        try:
            self.client.delete_all(user_id=self.user_id)
        except Exception as e:
            print(f"Warning: Failed to clear long-term memory: {e}")
        
        self.reset_session()

    def add_text_to_graph(self, text):
        """Add text to the knowledge graph (using mem0's memory system)."""
        try:
            result = self.client.add(
                messages=f"Knowledge: {text}",
                user_id=self.user_id,
                metadata={
                    "type": "knowledge",
                    "data_type": "text",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            return result
        except Exception as e:
            print(f"Warning: Failed to add text to graph: {e}")
            return None

    def add_json_to_graph(self, json_obj):
        """Add JSON data to the knowledge graph (using mem0's memory system)."""
        try:
            result = self.client.add(
                messages=f"Structured data: {json.dumps(json_obj, indent=2)}",
                user_id=self.user_id,
                metadata={
                    "type": "knowledge",
                    "data_type": "json",
                    "data": json.dumps(json_obj),
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            return result
        except Exception as e:
            print(f"Warning: Failed to add JSON to graph: {e}")
            return None

    def search_graph(self, query: str, scope: Literal["edges", "nodes"], limit: int = 5):
        """Search the knowledge graph (using mem0's search functionality)."""
        try:
            results = self.client.search(
                query=query,
                user_id=self.user_id,
                limit=limit
            )
            
            # Format results for compatibility
            formatted_results = []
            for result in results:
                if isinstance(result, dict):
                    formatted_results.append(result.get('memory', str(result)))
                elif hasattr(result, 'memory'):
                    formatted_results.append(result.memory)
                else:
                    formatted_results.append(str(result))
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            print(f"Warning: Failed to search graph: {e}")
            return f"Search failed: {str(e)}"
