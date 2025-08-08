# ContextShift 🧠💬  
*A prototype for user-controlled memory trimming in LLM-based chat interfaces*

## 🔍 Overview

**ContextShift** is a Streamlit-based prototype demonstrating a key feature proposed for future LLM chat interfaces:

> **Manual context management** – Let users delete older chat messages to free up space within a fixed token window, instead of forcing them to start a new conversation.

This feature mimics how long-context autoregressive LLMs (like ChatGPT or Claude) struggle with efficiency and cost as history grows. ContextShift gives users lightweight control over this by letting them manually trim the conversation.

---

## 🚀 Features

- ✅ Simulated LLM chat interface with user and AI messages  
- 🚫 Message cap at 10 exchanges to simulate token window limit  
- ⚠️ Warning when context is full  
- 🗑️ Delete button for any previous message to free space  
- 🔄 Dynamic UI update after deletion  
- 📜 Scrollable message view for better UX  

---

## 🛠️ How It Works

- Each user+AI message pair counts as 1 message
  
- After 10 messages, input is disabled until the user deletes one or more

- Deleting messages drops the message count and re-enables input
  
- This simulates context trimming without retraining the model or restarting the session

---

## 📂 File Structure

📦contextshift

    ┣ 📄 app.py              # Main Streamlit app (your script)
    
    ┣ 📄 README.md


---

---

## 🧪 Demo Logic

The system is built on top of `st.session_state` to simulate persistent memory across interactions.

python

    if len(st.session_state.messages) >= 10:

    st.session_state.chat_full = True 

Users can click a Delete button next to each message to:

 Trim the message history manually
 
 Free up the token budget (simulated via a message limit)
 
 Keep the chat thread alive without starting over



📦 Setup Instructions

1. Clone this repo
   
       git clone https://github.com/Vijay6923/ContextShift.git
       
       cd contextshift
   
2. Create a virtual environment (optional but recommended)
   
       python -m venv venv
   
       source venv/bin/activate  # or venv\Scripts\activate on Windows
   
3. Install requirements

       pip install streamlit

4. Run the app

       streamlit run app.py


🎯 Why This Matters

In real LLM systems, long-term chats hit token limits, leading to:

 Lost context

 Slower response time
 
 Higher inference costs
 
 Frustrated users

ContextShift is a step toward user-facing memory management — where power users can manually prune irrelevant past interactions, improving efficiency without architectural changes.

This is part of a broader proposal to make LLM interfaces:

   More transparent
  
   More efficient
  
   More usable for real work (coding, research, tutoring, etc.)

🧠 Next Steps (Ideas to Extend)

   Track actual token count per message using tiktoken
   
   Add “Collapse” instead of “Delete” (to simulate summarization)
  
   Add AI-suggested trimming (model recommends irrelevant messages to delete)
  
   Add save/bookmark for important messages

🤝 Contributing & Discussion

This is part of a larger set of UX ideas I’m building for LLM products.

If you’re interested in collaborating or brainstorming more:

  📧 Email: vk29082023@gmail.com

