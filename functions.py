import inspect
import json
from inspect import signature

import openai
from openai.types.beta.threads.run import RequiredAction


class Function:
    def __init__(self, function, name: str, description: str = ""):
        self.function = function
        self.name = name
        self.description = description

    def get_parameter_type(self, name):

        if name in self.function.__annotations__:
            typ = self.function.__annotations__[name]
        else:
            return "string"

        if typ == int:
            return "integer"

        if typ == str:
            return "string"

        if typ == float:
            return "float"

        if typ == bool:
            return "boolean"

        return "string"

    def generate_definition(self):
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }

        for parameter in inspect.signature(self.function).parameters:
            parameters["properties"][parameter] = {
                "type": self.get_parameter_type(parameter)
            }

            if inspect.signature(self.function).parameters[parameter].default == inspect.Parameter.empty:
                parameters["required"].append(parameter)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters
            }
        }


class Functions:
    def __init__(self):
        self.list_of_functions: list[Function] = []

    def add_function(self, function, name: str, description: str = ""):
        self.list_of_functions.append(Function(function, name, description))

    def get_list_of_functions(self):
        output = []
        for function in self.list_of_functions:
            output.append(function.generate_definition())

        return output

    def process_required_actions(self, required_action: RequiredAction):
        tool_outputs = []
        for action in required_action.submit_tool_outputs.tool_calls:
            for func in self.list_of_functions:
                if func.name == action.function.name:
                    arguments = json.loads(action.function.arguments)
                    result = str(func.function(**arguments))
                    tool_outputs.append({
                        "tool_call_id": action.id,
                        "output": result
                    })

        return tool_outputs
