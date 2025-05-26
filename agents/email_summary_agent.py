import logging
import os
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)

MAIN_AGENT_SYSTEM_PROMPT = """
Summarize the email (in its original language) as concisely as possible. The summary should give an overview, not include all details, but any important urls or links should be included.

If the email appears suspicious or is an advertisement, **mark it as spam** and **do not provide a summary**.

If the email contains events with specific dates and times, extract and clearly list the **event details**.

You may use **Markdown** to format your response.
"""


provider = OpenAIProvider(api_key=os.getenv("OPENAI_KEY"), base_url="https://openrouter.ai/api/v1")
model = OpenAIModel('openai/gpt-4o-mini', provider=provider)

class Event(BaseModel):
    title: str
    description: str
    all_day: bool = Field(json_schema_extra={'description': "If start time is not specified, this needs to be set to true. It indicates that the event is full day event."})
    start: Optional[str] = Field(default=None, json_schema_extra={'type': ['string', 'null'], 'description': 'Date and time in ISO format'})
    end: Optional[str] = Field(default=None, json_schema_extra={'type': ['string', 'null'], 'description': 'Date and time in ISO format'})


class EmailResponse(BaseModel):
    spam: bool
    summary: Optional[str] = Field(default=None, json_schema_extra={'type': ['string', 'null']})
    important: bool
    event: Optional[Event] = Field(default=None, json_schema_extra={'type': ['object', 'null']})

def get_email_summary_agent() -> Agent:
    """
    Returns the email summary agent.
    This function is used to get the agent instance for summarizing emails.
    """

    email_summary_agent = Agent(
        model=model,
        name="Email Summary Agent",
        instructions=MAIN_AGENT_SYSTEM_PROMPT,
        output_type=EmailResponse
    )

    return email_summary_agent



