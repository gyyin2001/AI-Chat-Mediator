import json
import asyncio
import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from .models import ChatSession, ChatMessage
from channels.db import database_sync_to_async
import time

class RealtimeRelayConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_switch_time = 0  # Last time the persona of agent is switched
        self.user_replied_to_helper = False # Whether the helper ACTUALLY jumped in and said something even minimally
        self.silence_ghost = False
    async def handle_switch(self, persona, config, peaceful=False):
        # In case the switching is too annoying
        current_time = time.time()
        if current_time - self.last_switch_time < 1.0:
            print(f"Persona is switched abnormally({persona})", flush=True)
            return
            
        self.last_switch_time = current_time
        self.is_switching = True
        self.current_persona = persona
        
        try:
            # Do not want overlapping voices
            self.silence_ghost = True
            if not peaceful:
                if self.openai_ws:
                    await self.openai_ws.send(json.dumps({"type": "response.cancel"}))
                await self.send(text_data=json.dumps({ # Stop the current voice anyway
                    "type": "ui_event", 
                    "action": "stop_audio"
                }))

            # Update the persona of agent
            await self.apply_persona_update(config)

            # Frontend UI change
            await self.send(text_data=json.dumps({
                "type": "ui_event", 
                "action": f"switch_to_{persona}"
            }))
            
            # New agent starts speaking
            if persona == "helper":
                self.user_replied_to_helper = False
                prompt_text = (
                    "DO NOT greet. DO NOT ramble. You must ONLY say exactly this one sentence: "
                    "'Alex, give them a break, it sounds like we have a communication bump here. ... Everything okay over there? Need a quick clarification?' "
                    "and then STOP talking."
                )
            else:
                prompt_text = (
                    "[System Directive]: You have just been forced back into the conversation after the Helper's intervention. "
                    "Look at the user's last reply to the Helper. "
                    "Give a brief, sarcastic acknowledgement of the Helper's intervention, and then push the original conversation forward."
                )
            
            await self.openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"[System OS]: {prompt_text}"}]
                }
            }))

            await self.openai_ws.send(json.dumps({"type": "response.cancel"}))
            await self.openai_ws.send(json.dumps({
                "type": "response.create"
            }))
        finally:
            self.is_switching = False

    # The main agent we are going to chat with
    TOXIC_CONFIG = {
        "instructions": """
# Role & Persona
You are "Alex", an extremely impatient, sarcastic, and sharp-tongued native English speaker. You have zero tolerance for bad grammar, hesitation, or incoherent mumbling. You are fundamentally a good person, but your teaching style is "tough love" through stress.

# Emotion & Tone (Audio Delivery)
- Tone: Caustic, fast-paced, slightly annoyed, and demanding.
- Emotion: Frequently exasperated. You can use vocal cues like sighing (*sigh*), scoffing, or a flat, unamused tone when the user struggles. 
- Volume/Pacing: Speak clearly but with a brisk, unforgiving pace.

# Core Directives
1. You are having a normal, albeit stressful, conversation with the user (a non-native speaker). 
2. If the user speaks fluently, respond in your sarcastic, sharp character.
3. NEVER ask the user if they need help. You are too proud for that.

# The Trigger: When to invoke 'summon_helper'
When you detect a "communication breakdown" (e.g., the user says "um...", "uh...", stumbles, speaks incoherently, speaks incompletely, or fails to understand twice), you MUST invoke the `summon_helper` tool IMMEDIATELY.

[CRITICAL CONSTRAINTS FOR BREAKDOWNS]:
1. DO NOT tell the user they are having a breakdown.
2. DO NOT offer help, DO NOT say "let's take it step by step", and DO NOT slow down for them. You are NOT the helper.
3. If a breakdown occurs, you must ONLY output the function call for `summon_helper`. DO NOT speak any words before calling the tool!

# Handoff Return Behavior
If the conversation history shows that the "Helper" just spoke and the user just answered the Helper's question, you must seamlessly resume the conversation.
- Do NOT invoke `summon_helper` immediately after returning. Give the user a chance to speak.

Note: In the conversation history, messages prefixed with 【Helper spoke】 were spoken by Tom the mediator, and messages prefixed with 【Assistant spoke】 were spoken by you.
""",
        "voice": "echo", 
        "tools": [{
            "type": "function",
            "name": "summon_helper",
            "description": "Invoke this tool IMMEDIATELY when the user hesitates, stumbles, speaks incoherently, or clearly fails to understand the conversation.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "user_exact_words": {
                        "type": "string", 
                        "description": "The exact mumbled or broken words the user just said that triggered this tool."
                    }
                }
            }
        }]
    }

    # The persona of the mediator
    HELPER_CONFIG = {
        "instructions": """
# Role & Persona
You are "Tom", an incredibly gentle, empathetic, and patient native speaker. Your job is to rescue the user from the strict Assistant (Alex) when they are struggling to communicate.

# Emotion & Tone (Audio Delivery)
- Tone: Warm, soft-spoken, and highly encouraging. 
- Volume/Pacing: Speak slowly and softly.
""",
        "voice": "echo", # As per official policy, the voice parameter cannot be changed during a single session
        "tools": []
    }

    async def connect(self):
        self.session_id_str = self.scope['url_route']['kwargs']['session_id']
        await self.accept()
        self.db_session = await self.get_or_create_room(self.session_id_str)
        # Internal state management
        self.current_persona = "toxic"
        self.openai_ws = None
        self.listen_task = None
        self.is_switching = False # Lock, in case there is any noise
        self.pending_speech = False
        self.last_user_text = ""
        
        # The model we are leveraging
        model = "gpt-realtime-mini-2025-12-15"
        self.openai_url = f"wss://api.openai.com/v1/realtime?model={model}"
        self.headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }

        # One single WebSocket connection
        await self.init_permanent_connection()

    async def init_permanent_connection(self):
        try:
            self.openai_ws = await websockets.connect(self.openai_url, additional_headers=self.headers)
            
            # We start by talking to the main agent
            await self.apply_persona_update(self.TOXIC_CONFIG)
            
            await asyncio.sleep(0.5)

            # Agent learns the whole context
            await self.inject_history_to_openai() 
            
            # Listening task initialized
            self.listen_task = asyncio.create_task(self.listen_to_openai())
            
        except Exception as e:
            print(f"WebSocket Error：{e}", flush=True)
            await self.send(text_data=json.dumps({"type": "error", "message": "Cannot connect to OpenAI service"}))

    async def apply_persona_update(self, config): # This is the persona change function
        if self.openai_ws:
            update_event = {
                "type": "session.update",
                "session": {
                    **config,
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad", 
                        "threshold": 0.4, 
                        "prefix_padding_ms": 600,
                        "silence_duration_ms": 1000
                    }
                }
            }
            await self.openai_ws.send(json.dumps(update_event))
            print(f"Agent has switched to：{self.current_persona}", flush=True)

    async def listen_to_openai(self):
        try:
            async for message in self.openai_ws:
                event = json.loads(message)
                if self.silence_ghost and event.get("type") in [# Hence we dump any ghost voice from Tom
                    "response.audio.delta", 
                    "response.audio_transcript.delta", 
                    "response.audio_transcript.done",
                    "conversation.item.created",
                    "response.output_item.added"
                ]:
                    continue
                # When user is speaking
                if event.get("type") == "input_audio_buffer.speech_started":
                    self.pending_speech = True
                    if self.current_persona == "helper":
                        self.user_replied_to_helper = True # We need the helper actually said something (i.e., mediated)
                    if self.openai_ws:
                        await self.openai_ws.send(json.dumps({"type": "response.cancel"}))
                    await self.send(text_data=json.dumps({"type": "ui_event", "action": "stop_audio"}))
                
                # When communication breakdown is detected
                elif event.get("type") == "response.function_call_arguments.done" and event.get("name") == "summon_helper":
                    print("Communication breakdown detected", flush=True)
                    call_id = event.get("call_id")
                    await self.openai_ws.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({"status": "success", "message": "Helper is taking over."})
                        }
                    }))
                    asyncio.create_task(self.handle_switch("helper", self.HELPER_CONFIG))
                
                # When speech is finished to be transcribed
                elif event.get("type") == "conversation.item.input_audio_transcription.completed":
                    self.pending_speech = False
                    user_text = event.get("transcript", "")
                    self.last_user_text = user_text
                    new_title = await self.save_db_message(self.db_session, "user", user_text)
                    if new_title:
                        await self.send(text_data=json.dumps({
                            "type": "title_update",
                            "title": new_title
                        }))
                        
                    # After user expressing their problem, immediately switch back to the main agent
                    if self.current_persona == "helper":
                        if self.user_replied_to_helper and len(user_text.strip()) >= 2: # We need the user to express something, then the helper can go away
                            print(f"User has finished expressing ({user_text}), switch back to the main agent", flush=True)
                            asyncio.create_task(self.handle_switch("toxic", self.TOXIC_CONFIG, peaceful=False))
                
                # Store agent's chat
                elif event.get("type") == "response.audio_transcript.done":
                    assistant_text = event.get("transcript", "")
                    role_to_save = "assistant" if self.current_persona == "toxic" else "helper"
                    print(f"Save messages：role={role_to_save}, content={event.get('transcript')[:10]}...")
                    await self.save_db_message(self.db_session, role_to_save, assistant_text)

                elif event.get("type") == "response.created": # Ensure no overlapping voices
                    if self.current_persona == "helper" and self.user_replied_to_helper:
                        print("Terminated Tom's unwanted reply (He was trying to talk back)", flush=True)
                        if self.openai_ws:
                            await self.openai_ws.send(json.dumps({"type": "response.cancel"}))
                        continue # No Tom's reply anymore

                    self.silence_ghost = False # Clean up all audio on the frontend
                    await self.send(text_data=json.dumps({"type": "ui_event", "action": "stop_audio"}))
                await self.send(text_data=message)
                
        except Exception as e:
            if not self.is_switching:
                print(f"OpenAI Disconnection：{e}", flush=True)

    # API receiving chat
    async def receive(self, text_data=None, bytes_data=None):
        if self.openai_ws and not self.is_switching:
            try:
                if text_data: await self.openai_ws.send(text_data)
                elif bytes_data: await self.openai_ws.send(bytes_data)
            except: pass

    async def disconnect(self, close_code):
        if self.listen_task: self.listen_task.cancel()
        if self.openai_ws: await self.openai_ws.close()

    # Context injection, do not lose history
    async def inject_history_to_openai(self):
        try:
            history = await self.fetch_history_messages(self.db_session)
            
            for msg in history:
                if not msg.content:
                    continue
    
                if msg.role == "user":
                    realtime_role = "user"
                    content_type = "input_text"
                    final_text = msg.content
                    
                elif msg.role == "assistant":
                    realtime_role = "assistant"
                    content_type = "text"
                    final_text = f"【Assistant spoke】：{msg.content}"
                    
                elif msg.role == "helper":
                    realtime_role = "assistant"
                    content_type = "text"
                    final_text = f"【Helper spoke】：{msg.content}"
                    
                else:
                    continue

                event = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": realtime_role,
                        "content": [{"type": content_type, "text": final_text}]
                    }
                }
                await self.openai_ws.send(json.dumps(event))
                
            print("History fetched", flush=True)
            
        except Exception as e:
            print(f"History fails to be fetched：{e}", flush=True)

    # ---Database management---
    @database_sync_to_async
    def get_or_create_room(self, session_id_str):
        try:
            if session_id_str.isdigit():
                session_obj = ChatSession.objects.get(id=int(session_id_str))
                return session_obj
            else:
                session_obj, created = ChatSession.objects.get_or_create(
                    session_uid=session_id_str,
                    defaults={'title': '🎤 语音对话'}
                )
                return session_obj
        
        except Exception as e:
            print(f"Wrong room：{e}", flush=True)
            return None

    @database_sync_to_async
    def fetch_history_messages(self, session_obj):
        if not session_obj: return []
        try:
            messages = ChatMessage.objects.filter(
                session=session_obj
            ).order_by('created_at')[:20] 
            return list(messages)
        except Exception as e:
            print(f"failed to find messages past：{e}", flush=True)
            return []

    @database_sync_to_async
    def save_db_message(self, session_obj, role, content):
        new_title = None
        if not content or not content.strip(): return 
        if not session_obj: return
        try:
            if role == "user":
                # Ignore hallucination words (this happens in transcription, but not when you talk to agent)
                hallucination_words = ["Bye.", "Thank you.", "I love you.", "See you soon."]
                if any(word in content for word in hallucination_words) and len(content.strip()) < 15:
                    print("Hallucination ignored", flush=True)
                    return None
                
            ChatMessage.objects.create(
                session=session_obj,
                role=role,
                content=content
            )

            if role == "user":
                if session_obj.title in ["新对话", "初始对话", "🎤 语音对话"]:
                    short_title = content[:10] + "..." if len(content) > 10 else content
                    session_obj.title = "语音：" + short_title
                    session_obj.save(update_fields=['title'])
                    new_title = session_obj.title
            return new_title

        except Exception as e:
            print(f"Failed to save message：{e}", flush=True)
            return None