import re
import json
import os
import uuid
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
from getpass import getpass

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = getpass("Enter your Google AI API key: ")


try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )
except Exception as e:
    raise RuntimeError(f"Failed to initialize ChatGoogleGenerativeAI: {e}")


system_prompt = """
You are a helpful assistant that answers questions about outlets and their opening times.
Always remember the context of the conversation to provide accurate and relevant answers.
When a user mentions a location but does not specify an outlet, ask them to clarify which outlet they are referring to.
If the user specifies an outlet, provide accurate opening times for that outlet.
Here is an example:
User: 'Is there an outlet in Petaling Jaya?'
Assistant: 'Yes! Which outlet are you referring to?'
User: 'SS 2, whats the opening time?'
Assistant: 'Ah yes, the SS 2 outlet opens at 9.00AM.'
Always respond concisely and accurately.
"""

memory_store = {}


def get_session_memory(session_id: str) -> ChatMessageHistory:
    if session_id not in memory_store:
        memory_store[session_id] = ChatMessageHistory()
    return memory_store[session_id]


def save_conversation_history(conversation):
    try:
        serialized_conversation = []

        for msg in conversation:
            if isinstance(msg, HumanMessage):
                serialized_conversation.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                serialized_conversation.append(
                    {"role": "assistant", "content": msg.content}
                )
            elif isinstance(msg, SystemMessage) and (
                msg.content.startswith("[TOOL]")
                or msg.content.startswith("[CONTROLLER]")
            ):
                serialized_conversation.append(
                    {"role": "system", "content": msg.content}
                )

        with open("conversation_history.json", "w") as f:
            json.dump(serialized_conversation, f, indent=4)

    except Exception as e:
        print(f"Error saving conversation history: {e}")


def calculator_tool(expression: str):
    try:
        # Only allow numbers, operators, parentheses, and spaces
        if not re.match(r"^[\d\s\+\-\*/\(\)\.]+$", expression):
            raise ValueError("Invalid characters in expression.")

        result = eval(expression, {"__builtins__": None}, {})
        return result
    except Exception as e:
        return f"Error: {e}"


def plan_next_action(user_input, memory):
    user_input_lower = user_input.lower()

    if "outlet" in user_input_lower:
        # Check if a specific outlet (e.g., SS 2) has been mentioned in the conversation
        if not "ss 2" in user_input_lower or not "ss2" in user_input_lower:
            return "ask_followup", "Yes! Which outlet are you referring to?"
        else:
            return "answer", "Ah yes, the SS 2 outlet opens at 9.00AM."

    if "ss 2" in user_input_lower or "ss2" in user_input_lower:
        return "answer", "Ah yes, the SS 2 outlet opens at 9.00AM."

    arithmetic_pattern = r"^(what is )?[\d\s\+\-\*/\(\)\.]+\??$"
    if re.match(arithmetic_pattern, user_input_lower):
        expr = re.sub(r"^\s*what is|\?", "", user_input_lower).strip()
        result = calculator_tool(expr)
        if isinstance(result, (int, float)):
            return "calculator", f"The answer is {result}."
        else:
            return "calculator_error", f"Sorry, I couldn't calculate that: {result}"

    return "default", None


def chat_with_bot(session_id: str):
    memory = get_session_memory(session_id)
    if not None in memory:
        memory.add_ai_message(system_prompt)
    print("Welcome to the outlet assistant! Type 'exit' to end the session.")

    while True:
        try:
            user_input = input("User: ").strip()

            if user_input.lower() == "exit":
                save_conversation_history(memory.messages)
                print("Ending session. Goodbye!")
                break

            if not user_input:
                print("Bot: I didn't catch that. Could you please rephrase?")
                continue

            memory.add_user_message(user_input)
            # --- AGENTIC PLANNER/CONTROLLER ---
            action, response = plan_next_action(user_input, memory)
            if action == "ask_followup":
                memory.messages.append(
                    SystemMessage(content="[CONTROLLER] Follow-up Question")
                )
                print(f"Bot: {response}")
                memory.add_ai_message(response)
                continue
            elif action == "answer":
                memory.messages.append(
                    SystemMessage(content="[CONTROLLER] Outlet Answer")
                )
                print(f"Bot: {response}")
                memory.add_ai_message(response)
                continue
            elif action == "calculator":
                memory.messages.append(SystemMessage(content="[TOOL] Tool: Calculator"))
                print(f"Bot: {response}")
                memory.add_ai_message(response)
                continue
            elif action == "calculator_error":
                memory.messages.append(
                    SystemMessage(content="[TOOL] Tool: Calculator (Error)")
                )
                print(f"Bot: {response}")
                memory.add_ai_message(response)
                continue
            # --- END AGENTIC PLANNER/CONTROLLER ---

            # Fallback to LLM
            valid_msgs = [
                m for m in memory.messages if isinstance(m, (HumanMessage, AIMessage))
            ]
            ai_response = llm.invoke(valid_msgs)
            bot_response = ai_response.content
            memory.add_ai_message(bot_response)
            print(f"Bot: {bot_response}")

        except Exception as e:
            print(f"Bot: Sorry, I encountered an error: {e}")
            break


if __name__ == "__main__":
    session_id = str(uuid.uuid4())
    chat_with_bot(session_id=session_id)
