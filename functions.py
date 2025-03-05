import inspect
import json
from inspect import signature

import openai
from openai.types.beta.threads.run import RequiredAction
from pydantic import BaseModel


class Function:
    def __init__(self, function, name: str, description: str = ""):
        self.function = function
        self.name = name
        self.description = description

    def get_parameter_type(self, name):

        if name in self.function.__annotations__:
            typ = self.function.__annotations__[name]
        else:
            return {"type": "string"}

        if typ == int:
            return {"type": "integer"}

        if typ == str:
            return {"type": "string"}

        if typ == float:
            return {"type": "number"}

        if typ == bool:
            return {"type": "boolean"}

        if typ == list[int]:
            return {"type": "array", "items": {"type": "integer"}}

        if isinstance(typ, type) and issubclass(typ, BaseModel):
            return typ.model_json_schema()  # Vygeneruje JSON schema pro Pydantic model

        return {"type": "string"}

    def generate_definition(self):
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }

        for parameter in inspect.signature(self.function).parameters:
            parameters["properties"][parameter] = self.get_parameter_type(parameter)

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

                    if action.function.arguments is None:
                        action.function.arguments = "{}"

                    result = ""
                    try:
                        # Load the arguments from JSON.
                        arguments = json.loads(action.function.arguments)
                        # Convert arguments using our helper function.
                        arguments = self.convert_arguments(arguments, func.function)
                        # Call the function with the converted arguments.
                        result = str(func.function(**arguments))
                    except Exception as exc:
                        result = "Function call failed: " + str(exc)

                    tool_outputs.append({
                        "tool_call_id": action.id,
                        "output": result
                    })

        return tool_outputs

    def convert_arguments(self, arguments: dict, function):
        """
        Inspects the function's parameters and converts any dict
        corresponding to a BaseModel annotation into an instance of that model.
        """
        signature = inspect.signature(function)
        converted = {}
        for name, param in signature.parameters.items():
            if name in arguments:
                arg_value = arguments[name]
                annotation = param.annotation
                # If the annotation is a subclass of BaseModel and the argument is a dict, convert it.
                if isinstance(annotation, type) and issubclass(annotation, BaseModel) and isinstance(arg_value, dict):
                    try:
                        converted[name] = annotation(**arg_value)
                    except Exception as exc:
                        # If conversion fails, fallback to the original dict.
                        converted[name] = arg_value
                else:
                    converted[name] = arg_value
        return converted