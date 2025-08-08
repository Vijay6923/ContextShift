import streamlit as st

st.set_page_config(page_title="ContextShift", layout="centered")
st.title("ContextShift")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "chat_full" not in st.session_state:
    st.session_state.chat_full = False
    
if "deletion_index" not in st.session_state:
    st.session_state.deletion_index = None

# Function to handle sending a message
def send_message():
    user_input = st.session_state.user_input.strip()
    if user_input:
        # Check if chat is full
        if len(st.session_state.messages) >= 10:
            st.session_state.chat_full = True
            return
            
        # Simulated AI reply
        ai_response = f"Simulated AI reply to: '{user_input}'"
        
        # Add to message history
        st.session_state.messages.append({
            "user": user_input,
            "ai": ai_response
        })
        
        # Check if we've reached the limit
        if len(st.session_state.messages) >= 10:
            st.session_state.chat_full = True
            
        # Clear input safely
        st.session_state.user_input = ""

# Function to delete a message
def delete_message(idx):
    st.session_state.deletion_index = idx

# Process deletions at the top level
if st.session_state.deletion_index is not None:
    idx = st.session_state.deletion_index
    if 0 <= idx < len(st.session_state.messages):
        st.session_state.messages.pop(idx)
        
        # If we're below the limit, re-enable chat
        if len(st.session_state.messages) < 10:
            st.session_state.chat_full = False
    
    # Reset deletion index
    st.session_state.deletion_index = None

# Input box with conditional disabling
user_input = st.text_input(
    " Type your message:", 
    key="user_input", 
    on_change=send_message,
    disabled=st.session_state.chat_full
)

# Send button with conditional disabling
send_button = st.button(
    "Send", 
    on_click=send_message, 
    disabled=st.session_state.chat_full
)

# Show warning if chat is full
if st.session_state.chat_full:
    st.warning("⚠️ Chat history is full! Please delete some messages to continue chatting.")
    
# Scrollable chat container
st.markdown("---")
with st.container():
    st.markdown("<div style='height: 200px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 8px;'>", 
                unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown("<div style='text-align: center; color: #777; padding: 20px;'>No messages yet. Start chatting!</div>", 
                    unsafe_allow_html=True)
    else:
        for idx, msg in enumerate(st.session_state.messages):
            st.markdown(f"**You:** {msg['user']}")
            st.markdown(f"**AI:** {msg['ai']}")
            
            # Delete button for each message
            if st.button("Delete", key=f"delete_{idx}"):
                delete_message(idx)
                
            st.markdown("---")

    st.markdown("</div>", unsafe_allow_html=True)
    
# Show current message count
st.caption(f"Messages: {len(st.session_state.messages)}/10")