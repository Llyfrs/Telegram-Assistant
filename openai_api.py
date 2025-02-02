import logging
import time

import openai

from functions import Functions


class OpenAI_API:
    def __init__(self, key: str, model: str = "gpt-4o-mini"):
        self.key = key
        self.client = openai.OpenAI(api_key=key, default_headers={"OpenAI-Beta": "assistants=v2"})
        self.functions = Functions()
        self.model = model
        self.assistant = None
        self.thread = None
        self.run = None
        self.last_message = None
        self.last_run_cost = None

    def create(self):
        tools = [{"type": "code_interpreter"}]
        tools.extend(self.functions.get_list_of_functions())

        self.assistant = self.client.beta.assistants.update(
            assistant_id="asst_auvIdEBIKEZk6vinvLA1yuUD",
            name="Personal Assistant",
            description="TelegramBot Assistant",
            instructions="You are the users personal telegram bot assistant. User does "
                         "not see what you are putting in to functions or their output.\n"
                         "You are really bad at math so don't try to do any yourself, use the calculate function instead.\n"
                         "Every time you create reminder you have to first either use the convert_to_seconds or seconds_until functions. "
                         "Do not input your own numbers in to it"
                         "Each user message is started with the current time in the format %H:%M:%S %d/%m/%Y \n",
            model=self.model,
            tools=tools
        )

        self.thread = self.client.beta.threads.create(
            timeout=1,
        )

    def clear_thread(self):
        self.client.beta.threads.delete(thread_id=self.thread.id)
        self.thread = self.client.beta.threads.create()

    def set_model(self, model: str):
        self.model = model
        self.assistant = self.client.beta.assistants.update(
            assistant_id=self.assistant.id,
            model=model
        )

    # adds message to the conversation but does not invoke AI to respond for that you need to call run()
    def add_message(self, message: str, photos = None):

        """This is to protect my self from spending to much"""
        if self.model == "gpt-4o":
            self.clear_thread()

        content = [{"type": "text", "value": message}]

        for photo in photos:
            content.append({"type": "image_url", "image_url": {"url": photo}})


        print(str(content))


        message = self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=str(content)
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
            assistant_id=self.assistant.id,
        )

        while self.run.status != "completed":

            self.run = self.client.beta.threads.runs.retrieve(run_id=self.run.id, thread_id=self.thread.id)

            if self.run.status in ["failed", "cancelled", "expired", "incomplete"]:
                logging.error(f"Run failed: {self.run.last_error}")
                return

            if self.run.status == "requires_action":

                if not self.run.required_action:
                    logging.info("Requested action but no action was provided")
                    time.sleep(0.5)

                print(self.run.required_action)
                print(self.functions.process_required_actions(self.run.required_action))

                self.client.beta.threads.runs.submit_tool_outputs(
                    run_id=self.run.id,
                    thread_id=self.thread.id,
                    tool_outputs=self.functions.process_required_actions(self.run.required_action)
                )


        self.last_run_cost = self.run.usage
        logging.info(f"Run completed with cost: {self.last_run_cost}")

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

    def get_usage(self):
        return self.client.organization

    def simple_completion(self, instruction, message, model ="gpt-4o-mini", schema = None):

        completion = None

        if schema is None:
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "developer", "content": instruction},
                    {"role": "user", "content": message}
                ],
            )

        else:
            completion = self.client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "developer", "content": instruction},
                    {"role": "user", "content": message}
                ],
                response_format=schema
            )

        return completion.choices[0].message

