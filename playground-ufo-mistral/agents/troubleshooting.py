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

def retrieve_sop():
    """ Retrieves the sop list which contains error code, error description, root rause and next action """

    try:
        # Establish the connection to the PostgreSQL database using constant values
        connection = None
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_DATABASE,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        
        # Create a cursor object using the connection
        cursor = connection.cursor()
        result = []
        
        # print("Connection to PostgreSQL database established successfully!")
        
        # Write the SQL query to fetch the order status based on the order_id
        query = "SELECT * FROM ufo_sop;"
        
        # Execute the query with the provided order_id
        cursor.execute(query)
        
        # Fetch the result
        
        result = cursor.fetchall()
        
        # If result is None, it means the order_id was not found
        if not result:
            print(f"No order found with order_id {order_id}.")
            return f"No order found with order_id {order_id}."

        # Get the column name(s) from the cursor description (metadata)
        column_names = [desc[0] for desc in cursor.description]
        
        result_string = "|".join(column_names) + "\n"  # Add column headers

        for row in result:
            result_string += "|".join(map(str, row)) + "\n"


        #print(result_string)
        return result_string
                
    except OperationalError as e:
        print(f"Error: {e}")
        return None
    except Exception as e:
        print(f"Error querying the UFO SOP: {e}")
        return None
    finally:
        # Ensure the cursor and connection are closed
        if connection:
            cursor.close()
            connection.close()
            # print("Connection closed.")

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

def check_order_status(order_id):
    """Check the status of an order by connecting to the PostgreSQL database."""
    try:
        # Establish the connection to the PostgreSQL database using constant values
        connection = None
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_DATABASE,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        
        # Create a cursor object using the connection
        cursor = connection.cursor()
        result = []
        
        print("Connection to PostgreSQL database established successfully!")
        
        # Write the SQL query to fetch the order status based on the order_id
        query = "SELECT * FROM order_resolution WHERE order_id = %s;"
        
        # Execute the query with the provided order_id
        cursor.execute(query, (order_id,))
        
        # Fetch the result
        
        result = cursor.fetchall()
        
        # If result is None, it means the order_id was not found
        if not result:
            print(f"No order found with order_id {order_id}.")
            return f"No order found with order_id {order_id}."

        # Get the column name(s) from the cursor description (metadata)
        column_names = [desc[0] for desc in cursor.description]
        
        # Convert each row to a dictionary with column names as keys
        formatted_result_list = [dict(zip(column_names, row)) for row in result]
        
        # Convert the list of dictionaries to a string representation
        formatted_result_str = ""
        for order in formatted_result_list:
            order_details = "\n".join([f"{key}: {value}" for key, value in order.items()])
            formatted_result_str += f"Order Details:\n{order_details}\n\n"
        
        return formatted_result_str
                
    except OperationalError as e:
        print(f"Error: {e}")
        return None
    except Exception as e:
        print(f"Error querying the order status: {e}")
        return None
    finally:
        # Ensure the cursor and connection are closed
        if connection:
            cursor.close()
            connection.close()
            print("Connection closed.")

# Use this for local only, connect to Mistral Free API
# client = Mistral(
#     api_key = MISTRAL_API_KEY,
# )

# Use this for server
client = OpenAI(
    api_key = MISTRAL_API_KEY,
    base_url = MISTRAL_BASE_URL,
    http_client = httpx.Client(verify=False),
)

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
        time.sleep(5)
        # response = client.chat.complete(
        #     model=MISTRAL_MODEL,
        #     messages=[{"role": "system", "content": current_agent.instructions}]
        #     + messages,
        #     temperature=0.0,
        #     tools = tool_schemas,
        #     tool_choice = "auto",
        # )

        # Use this for server, using OpenAI API
        response = client.chat.completions.create(
            model=MISTRAL_MODEL,
            messages=[{"role": "system", "content": current_agent.instructions}]
            + messages,
            temperature=0.0,
            tools = tool_schemas,
            tool_choice = "auto",
        )

        print(response)
        
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


def execute_tool_call(tool_call, tools, agent_name):
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    print(f"{agent_name}:", "Executing tool:", f"{name}({args})")

    return tools[name](**args)

class Agent(BaseModel):
    name: str = "Agent"
    model: str = MISTRAL_MODEL
    instructions: str = "You are a helpful Agent"
    tools: list = []

class Response(BaseModel):
    agent: Optional[Agent]
    messages: list

order_header = "IH_NUMBER,ORDER_ID,ORDER_TYPE,REASON_CODE,CUSTOMER_ORDER_ID,INTEGRATION_ID,TRANSACTION_ID,ORDER_STATUS,SUBMITTED_DATE,STEP_STATUS,FO_MSG,SRC_SYSTEM,STATUS"

order_list = [
    "190000000084,12192911,MO,REPLACE,MOk4250122101016354922640,0V168ZENE6FB5IL5K9385QEXD,k41948e9068ee18451000886482b4f6Icu60000G000,Failed,1/22/2025 22:13,Failed,Internal Server Error,NBP,OPEN",
    "190000000040,9559589,AO,CREQ,AOi42501070329122268949f0,0Y4NODJ3VCUNDGOFNY6RYP14V,i41943fe35e5d12252000769112b696Iar70000G000,Failed,1/7/2025 15:30,Failed,FAILED - NONRETRY,NBP,OPEN",
    "190000000080,12803690,MO,REPLACE,MOk42501300904219745e55a0,R0HUEMVC1IY0ZUM7XMS0ALMAP,k4194b4f3c42411461000952002c969Icr00000G000,Failed,1/30/2025 9:35,Failed,FAILED - RETRY,NBP,OPEN",
    "190000000001,9900736,MO,CREQ,MOi12501201000339579db630,A301250120220033785071030,s018737aa0048071030007859900000Iaub00001000,Failed,1/20/2025 22:00,Failed,FAILED - NONRETRY,NBP,OPEN",
    "190000000002,9883174,MO,CREQ,MOi12501200146366456a97c0,A301250120134636702270570,s0184d5bb55fc270570007859900000Iaub00001000,Failed,1/20/2025 13:46,Failed,FAILED - NONRETRY,NBP,OPEN",
    "190000000003,9872457,MO,CREQ,MOi125012009210093641d5b0,A301250120092059545006690,s018737e27342006690007859900000Iaub00001000,Failed,1/20/2025 9:21,Failed,FAILED - NONRETRY,NBP,OPEN",
    "190000000004,9865636,MO,CREQ,MOi12501190613532282c4b90,A301250119181352662014260,s018737a769a0014260007859900000Iaub00001000,Failed,1/19/2025 18:13,Failed,FAILED - NONRETRY,NBP,OPEN",
    "190000000005,9861185,MO,CREQ,MOi1250119032647578919690,A301250119152647423560490,s0187379a1ace560490007859900000Iaub00001000,Failed,1/19/2025 15:26,Failed,FAILED - NONRETRY,NBP,OPEN",
]


def find_nbp_log(integration_id):
    """
    Searches for an NBP log by calling the splunk query API based on the provided integration_id.
    """

    nbp_log = "Cannot find the corresponding NBP log bassed on INTEGRATION_ID " + integration_id

    url = 'https://splunk-query-accenture-poc-application.apps.cluster-gdm2g.gdm2g.sandbox1647.opentlc.com/search'
    headers = {
        'Content-Type': 'application/json',
        'Cookie': 'cd67134e12541f7d6958784e76a83787=32723587ad3d005624226c556d17f279'
    }
    data = {
        "search_term": f" {integration_id} ",
        "index": "main"
    }

    # Send POST request
    response = requests.post(url, headers=headers, data=json.dumps(data))

    # Check for successful response
    if response.status_code == 200:
        nbp_log = "Found NBP log: " + response.json()["results"][0]["_raw"]
        # print(nbp_log)
    else:
        nbp_log += f". Error: {response.status_code}, {response.text}"


    return nbp_log

# def update_order_resolution(order_id, root_cause, next_action):
#     """ Updates the root cause and next action field in the order_resolution table"""

#     return "Successfully updated order resolution for order ID: " + order_id

def update_order_resolution(ih_number: str, order_id: str, customer_order_id: str, integration_id: str, transaction_id: str, 
    submitted_date: str, system: str, root_cause_analysis: str, action_taken: str):
    """
    Insert a record into the UFO_ORDER_RESOLUTION table.
    
    Args:
        ih_number (str): Indihome number
        order_id (str): Order identifier
        customer_order_id (str): Customer's order identifier
        integration_id (str): Integration identifier
        transaction_id (str): Transaction identifier
        submitted_date (datetime): Date and time of submission
        system (str): System name
        root_cause_analysis (str): Analysis of root cause (max 255 chars)
        action_taken (str): Next action taken (max 255 chars)
    
    Returns:
        bool: True if insertion successful, False otherwise
    """

    print(ih_number)
    print(order_id)
    print(customer_order_id)
    print(integration_id)
    print(transaction_id)
    print(submitted_date)
    print(system)
    print(root_cause_analysis)
    print(action_taken)

    try:
        # Establish database connection
        connection = None
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_DATABASE,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        
        # Create cursor
        cursor = connection.cursor()
        
        # SQL insert query
        insert_query = """
            INSERT INTO UFO_ORDER_RESOLUTION (
                ih_number,
                order_id,
                customer_order_id,
                integration_id,
                transaction_id,
                submitted_date,
                system,
                root_cause_analysis,
                action_taken
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # Execute the insert
        cursor.execute(insert_query, (
            ih_number,
            order_id,
            customer_order_id,
            integration_id,
            transaction_id,
            submitted_date,
            system,
            root_cause_analysis,
            action_taken
        ))
        
        # Commit the transaction
        connection.commit()
        return "Success: updated resolution table for this order."
        
    except psycopg2.Error as e:
        print(f"Database error occurred: {e}")
        if 'connection' in locals():
            connection.rollback()
        return "Error: unable to update resolution for this order."
        
    finally:
        # Clean up
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

troubleshooting_agent = Agent(
    name="Troubleshooting Agent",
    instructions = f"""
        You are an expert in troubleshooting order related issues.

        Take note of important order information: IH_NUMBER, ORDER_ID, CUSTOMER_ORDER_ID, INTEGRATION_ID, TRANSACTION_ID, SUBMITTED_DATE, SRC_SYSTEM

        Based on the provided order given by the user, find the corresponding nbp log based on order.INTEGRATION_ID

        if NBP log is not found, inform the user that you are unable to troubleshoot the issue since there is no NBP log is found.

        if the NBP log is found,:
            1. return the NBP error which is in the 35th position of the nbp log, separated by '|'
            2. retrieve sop
            3. find which sop is applicable based on the NBP error and return the SOP with the header
            4. update the order resolution table based with the following details, follow the sequence order: ih_number, order_id, customer_order_id, integration_id, transaction_id, submitted_date, system, root_cause_analysis, action_taken,
            5. Once completed summarize the list of actions performed. Remember to always generate the summary!
    """,
    tools=[retrieve_sop, find_nbp_log, update_order_resolution],
    tool_choice = "any",
)

agent = troubleshooting_agent

for order in order_list:
    messages = []
    order_details = order_header + '\n' + order
    print(order_details)
    messages.append({"role": "user", "content": order_details})
    response = run_full_turn(agent, messages)

    print ("*************************************************")


