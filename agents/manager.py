import psycopg2
from psycopg2 import OperationalError
from openai import OpenAI
from typing import Optional
import httpx
import inspect
from mistralai import Mistral
from pydantic import BaseModel
import json
import time
import requests
from dotenv import load_dotenv
import os
from psycopg2.extras import RealDictCursor
import httpx

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL")

# Database connection constants
DB_HOST = os.getenv("DB_HOST")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

class Agent(BaseModel):
    name: str = "Agent"
    model: str = MISTRAL_MODEL
    instructions: str = "You are a helpful Agent"
    tools: list = []

class Response(BaseModel):
    agent: Optional[Agent]
    messages: list

# Use this for local only, connect to Mistral Free API
# client = Mistral(
#    api_key = MISTRAL_API_KEY,
# )

# Use this for server
client = OpenAI(
    api_key = MISTRAL_API_KEY,
    base_url = MISTRAL_BASE_URL,
    http_client = httpx.Client(verify=False),
)

def query_order_resolution(id_type: str, id_list: list) -> list:
    """
    Queries the UFO_ORDER_RESOLUTION table for order resolution details based on id_type and id_list.
    """
    # Validate inputs
    if not id_list:
        raise ValueError("id_list cannot be empty")
    
    valid_id_types = ["IH_NUMBER", "CUSTOMER_ORDER_ID"]
    if id_type.upper() not in valid_id_types:
        raise ValueError(f"id_type must be one of {valid_id_types}, got {id_type}")

    # Format the id_list for SQL IN clause, treating all IDs as strings
    formatted_ids = ", ".join(f"'{id}'" for id in id_list)
    if id_type == "IH_NUMBER":
        query = f"SELECT * FROM UFO_ORDER_RESOLUTION WHERE IH_NUMBER IN ({formatted_ids})"
    else:  # id_type == "CUSTOMER_ORDER_ID"
        query = f"SELECT * FROM UFO_ORDER_RESOLUTION WHERE CUSTOMER_ORDER_ID IN ({formatted_ids})"

    # Database connection and execution
    try:
        # Establish connection
        connection = None
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_DATABASE,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            cursor_factory=RealDictCursor
        )
        
        # Create cursor and execute query
        cursor = connection.cursor()
        cursor.execute(query)
        
        # Fetch all results
        results = cursor.fetchall()
        
        # Convert to JSON string
        json_results = json.dumps(results, default=str)
        
        # Close connection
        cursor.close()
        connection.close()
        
        return json_results

    except psycopg2.Error as e:
        # Handle database errors
        raise psycopg2.Error(f"Database error occurred: {e}")

def retry_order(customer_order_id):
    return "Retry order is executed successfully."

def force_complete_order(customer_order_id):
    return "This order has been force completed."



manager_agent = Agent(
    name="UFO Order Manager Agent",
    instructions = f"""
        You are an expert agent specialized in managing UFO orders. 
        Your primary task is to assist users by processing a list of order IDs they provide, either in the form of an IH_NUMBER (Indihome Number) or a CUSTOMER_ORDER_ID, and retrieving the root cause and resolution details for each from the ufo_order_resolution table.
        Your goal is to deliver clear, concise, and accurate information based on the user's input. Always mention the IH_NUMBER in your response as a reference.

        Here's how you operate:
        1. Identify a list of order IDs from the user, which can be IH_NUMBER or CUSTOMER_ORDER_ID type. Take note of the identifier type or id_type.
            - IH_NUMBER: format is number only e.g., 190000000080, 190000000004, 190000000002
            - CUSTOMER_ORDER_ID: format is mixed of letters and numbers in the following pattern e.g., MOk42501300904219745e55a0, MOi12501190613532282c4b90, MOi125012009210093641d5b0).
        2. Query order resolution table to find the associated root cause and resolution using the id_type (either IH_NUMBER or CUSTOMER_ORDER_ID) and id_list which is a list of the order IDs.
        3. If the action taken contains "INFORM:", you can offer to the user some help to write the draft email in bahasa Indonesia. Do not offer to send the email because you are not authorized to do so.
        4. If the action taken contains "RETRY:", ask the user for approval if he wants to execute the retry order. If the user approves, execute the retry ufo order tool.
        5. If the action taken contains "FORCE:", ask the user for approval if he wants to force complete. If the user approves, execute the force complete order tool.
    """,
    tools=[query_order_resolution, retry_order, force_complete_order],
    tool_choice = "any",
)


def function_to_schema(func) -> dict:
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    try:
        signature = inspect.signature(func)
    except ValueError as e:
        raise ValueError(
            f"Failed to get signature for function {func.__name__}: {str(e)}"
        )

    parameters = {}
    for param in signature.parameters.values():
        try:
            param_type = type_map.get(param.annotation, "string")
        except KeyError as e:
            raise KeyError(
                f"Unknown type annotation {param.annotation} for parameter {param.name}: {str(e)}"
            )
        parameters[param.name] = {"type": param_type}

    required = [
        param.name
        for param in signature.parameters.values()
        if param.default == inspect._empty
    ]

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": (func.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required,
            },
        },
    }

def execute_tool_call(tool_call, tools, agent_name):
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    print(f"{agent_name}:", "Executing tool:", f"{name}({args})")

    return tools[name](**args)

def run_full_turn(agent, messages):

    current_agent = agent
    num_init_messages = len(messages)
    messages = messages.copy()
    i = 0
    while True:
        i+=1
        print("Iter: " + str(i))

        # turn python functions into tools and save a reverse map
        tool_schemas = [function_to_schema(tool) for tool in current_agent.tools]
        tools = {tool.__name__: tool for tool in current_agent.tools}

        print("Current agent: " + current_agent.name)
        #print(messages)

        # Use this for local only, connect to Mistral Free API
        # time.sleep(2)
        # response = client.chat.complete(
        #     model=MISTRAL_MODEL,
        #     messages=[{"role": "system", "content": current_agent.instructions}]
        #     + messages,
        #     temperature=0.0,
        #     tools = tool_schemas,
        #     tool_choice = "auto",
        # )

        Use this for server, using OpenAI API
        response = client.chat.completions.create(
            model=MISTRAL_MODEL,
            messages=[{"role": "system", "content": current_agent.instructions}]
            + messages,
            temperature=0.0,
            tools = tool_schemas,
            tool_choice = "auto",
        )
        
        message = response.choices[0].message
        messages.append(message)

        if message.content:  # print agent response
            print(f"{current_agent.name}:", message.content)

        if not message.tool_calls:  # if finished handling tool calls, break
            break

        for tool_call in message.tool_calls:
            result = execute_tool_call(tool_call, tools, current_agent.name)
            print("Tool call completed. Result:")
            if type(result) is Agent:  # if agent transfer, update current agent
                current_agent = result
                result = (
                    f"Transfered to {current_agent.name}. Adopt persona immediately."
                )

            result_message = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.function.name,
                "content": result,
            }
            print(result_message)
            messages.append(result_message)

    return Response(agent=current_agent, messages=messages[num_init_messages:])
