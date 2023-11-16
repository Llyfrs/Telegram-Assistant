import openai
from functions import Functions


class OpenAI_API:
    def __init__(self, key: str, model: str = "gpt-3.5-turbo-1106"):
        self.key = key
        self.client = openai.Client(api_key=key)
        self.functions = Functions()
        self.model = model
        self.assistant = None
        self.thread = None
        self.run = None
        self.last_message = None

    def create(self):
        tools = [{"type": "code_interpreter"}]
        tools.extend(self.functions.get_list_of_functions())

        self.assistant = self.client.beta.assistants.update(
            assistant_id="asst_Y58Ryfj8tiaOr4KS2easHueW",
            name="Personal Assistant Prototype",
            description="TelegramBot Assistant",
            instructions="You are the users personal assistant. Don't use mathjax formatting. You are bad at math so make sure to use code interpreter for it.",
            model=self.model,
            tools=tools
        )

        self.thread = self.client.beta.threads.create(
            timeout=1,
        )

    def clear_thread(self):
        self.client.beta.threads.delete(thread_id=self.thread.id)
        self.thread = self.client.beta.threads.create()

    # adds message to the conversation but does not invoke AI to respond for that you need to call run()
    def add_message(self, message: str):
        message = self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=message
        )

        self.last_message = message.id

    def get_last_message(self):
        messages = self.client.beta.threads.messages.list(
            thread_id=self.thread.id,
        )

        return messages.data[0].content[0].text.value

    def get_new_messages(self):

        messages = self.client.beta.threads.messages.list(
            thread_id=self.thread.id,
            after=self.last_message,
            order="asc"
        )

        self.last_message = (messages.data[0].id if len(messages.data) > 0 else self.last_message)

        return messages

    def run_assistant(self):

        self.run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id
        )

        while self.run.status != "completed":
            self.run = self.client.beta.threads.runs.retrieve(run_id=self.run.id, thread_id=self.thread.id)

            if self.run.status in ["failed", "cancelled", "expired"]:
                return

            if self.run.status == "requires_action":

                self.client.beta.threads.runs.submit_tool_outputs(
                    run_id=self.run.id,
                    thread_id=self.thread.id,
                    tool_outputs=self.functions.process_required_actions(self.run.required_action)
                )

        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id=self.thread.id,
            run_id=self.run.id
        )

        return run_steps

    def delete_assistant(self, id: str = None):
        if id == None:
            id = self.assistant.id
        self.client.beta.assistants.delete(assistant_id=id)

    def list_assistants(self):
        return self.client.beta.assistants.list()

    def add_function(self, function, name: str, description: str = ""):
        self.functions.add_function(function, name, description)
