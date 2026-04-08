# Multi-Agent Realtime Voice Chat: A Simplified Sequential Handoff Demo

## 📖 Introduction
This project is a real-time, voice-to-voice web application designed to demonstrate a **simplified Sequential Handoff** pattern in a Multi-Agent architecture. 

It is specifically built as a training tool for **non-native English speakers**. The goal is to simulate an immersive, high-pressure conversational environment while providing a built-in "safety net" to prevent total communication breakdowns. Powered by the OpenAI Realtime API, a Django backend (using Channels for WebSockets), and a Vue.js frontend, this system brings language practice to life.

## 🧠 Core Concept: Simplified Sequential Handoff
Instead of a complex, fully autonomous multi-agent swarm, this project uses a streamlined, highly controlled approach. It delegates tasks to two distinct AI personas that take turns controlling the conversation via a sequential handoff mechanism:

1. **Agent 1 (Alex - The Stressor):** An impatient, fast-paced, and slightly toxic native English speaker. Alex is the primary agent, designed to put the non-native user under realistic conversational pressure.
2. **Agent 2 (Tom - The Mediator):** A gentle, empathetic observer acting as the user's safety net.
3. **The Handoff:** When Alex detects a "communication breakdown" (e.g., the user stutters, hesitates, or fails to understand), Alex silently invokes a tool to trigger the handoff. The backend immediately intercepts the audio stream, pauses Alex, and summons Tom. Tom steps in briefly to explain the confusion or calm the user down in a third-party tone, and then seamlessly hands the control back to Alex to resume the main conversation.

This demonstrates how a simplified multi-agent logic can be cleanly separated into distinct, specialized personas that tag in and out based on state machines and function calls.

## 📂 Repository Structure
```text
.
├── Backend/                 # Django project (WebSocket consumer, State Machine, API)
└── Frontend/                # Vue.js assets
    ├── public/              
    └── src/
```

## ⚙️ Setup & Installation
1. **Backend (Django)** <br>

The backend manages the WebSocket connections, database, and the state machine for the multi-agent handoffs.

*a.* Navigate to the backend directory:
```bash
cd Backend
```
*b.* Install the necessary Python dependencies (Django, channels, djangorestframework, openai, websockets, etc.).

*c.* API Key Setup: For security reasons, the `.env` file is NOT included in this repository. You must create your own `.env` file in the root of the Backend directory and add your OpenAI API key (ensure your key has access to the Realtime API models):
```python
OPENAI_API_KEY=sk-your-openai-api-key-here
```

*d.* Initialize the Database: Before running the server, you need to set up the SQLite database:
```bash
python manage.py makemigrations
python manage.py migrate
```

*e.* Run the server:
```bash
python manage.py runserver
```

2. **Frontend (Vue.js)** <br>

To keep the repository clean, only the core `src` and `public` folders are uploaded. You will need to scaffold a standard Vue environment to run them.

*a.* Initialize a new Vue project using Vue CLI or Vite in a directory of your choice:
```bash
vue create my-frontend-app
# OR
npm create vue@latest
```

*b.* Navigate into your new project folder and delete its default `src` and `public` folders.

*c.* Copy/Paste the `src` and `public` folders from this repository's `Frontend/` folder into your newly created Vue project.

*d.* Install necessary dependencies (like `axios`):
```bash
npm install axios
```

*e.* Run the development server:
```bash
npm run serve
# OR npm run dev (if using Vite)
```

## ⚠️ Known Limitations & Contributing
This project is intended as a proof-of-concept and a demonstration of a simplified Multi-Agent design pattern. Because it deals with cutting-edge real-time audio streams, WebSocket latency, and complex VAD (Voice Activity Detection) interruptions, there will inevitably be bugs, edge cases, and areas for code optimization.

If you find a bug, have an idea for reducing latency, or want to improve the agent prompts and UI, your contributions are highly encouraged! Feel free to open an Issue or submit a Pull Request. Let's build better Multi-Agent systems together! 🚀
