import streamlit as st
import json
import agents.manager as ag_manager
import time

# App title
st.set_page_config(page_title="UFO Order Manager Agent")

assistant_image_url = "https://upload.wikimedia.org/wikipedia/commons/b/bc/Telkomsel_2021_icon.svg"

# Store LLM generated responses
if "messages" not in st.session_state.keys():
    st.session_state.messages = [{"role": "assistant", "content": "Hello, how may I assist you today with UFO related orders?"}]

if "agent" not in st.session_state:
    st.session_state.agent = ag_manager.manager_agent

# Custom CSS for chat layout
st.markdown(
    """
<style>
    .st-emotion-cache-1c7y2kd {
        flex-direction: row-reverse;
    }
    .st-emotion-cache-1ghhuty {
        background-color: orange !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

hide_streamlit_style = """
                <style>
                div[data-testid="stToolbar"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
                }
                div[data-testid="stDecoration"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
                }
                div[data-testid="stStatusWidget"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
                }
                #MainMenu {
                visibility: hidden;
                height: 0%;
                }
                header {
                visibility: hidden;
                height: 0%;
                }
                footer {
                visibility: hidden;
                height: 0%;
                }
                </style>
                """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'last_user_message' not in st.session_state:
    st.session_state.last_user_message = ''

# Display previous messages

for message in st.session_state.messages:
    #print(message)
    if message["content"]:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message("assistant", avatar=assistant_image_url):
                st.markdown(message["content"], unsafe_allow_html=True)
        elif message["role"] == "json":
            with st.chat_message("assistant", avatar=assistant_image_url):
                st.json(message["content"], expanded=2)
        elif message["role"] == "chart":
            with st.chat_message("assistant", avatar=assistant_image_url):
                st.image(message["content"],use_container_width=True)
                time.sleep(3)


# Get user input
user_message = st.chat_input("Type your message")

if user_message and user_message != st.session_state.last_user_message:

    # Update last_user_message
    st.session_state.last_user_message = user_message

    # Add user message to messages
    st.session_state.messages.append({"role": "user", "content": user_message})
    messages = st.session_state.messages.copy()
    with st.chat_message("user"):
        st.markdown(user_message)

    # Run assistant response
    with st.spinner("Thinking.....", show_time=True):
        print("Executing Agent: " + st.session_state.agent.name)
        response = ag_manager.run_full_turn(st.session_state.agent, messages)
        st.session_state.agent = response.agent
        print(response.agent)
        print(response.messages)
        # Display new messages
        for message in response.messages:
            print(message)
            if isinstance(message, dict):
                continue
            else:
                if message.content:
                    if message.role == "assistant":
                        with st.chat_message("assistant", avatar=assistant_image_url):
                            st.markdown(message.content, unsafe_allow_html=True)
                            st.session_state.messages.append({"role": "assistant", "content": message.content})
                    elif message.role == "json":
                        with st.chat_message("assistant", avatar=assistant_image_url):
                            st.json(message.content, expanded=2)
                    elif message.role == "chart":
                        with st.chat_message("assistant", avatar=assistant_image_url):
                            st.image(message.content,use_container_width=True)
                            time.sleep(3)
