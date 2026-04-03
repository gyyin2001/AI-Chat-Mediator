import json
import asyncio
import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from .models import ChatSession, ChatMessage
from channels.db import database_sync_to_async
from openai import AsyncOpenAI
import time

class RealtimeRelayConsumer(AsyncWebsocketConsumer):# 后台中继转接器
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_switch_time = 0  # 记录上次切换时间

    async def handle_switch(self, persona, config, peaceful=False):
        """热更新代替冷启动：切换角色"""
        # 防止3秒内连续切换
        current_time = time.time()
        if current_time - self.last_switch_time < 2:
            print(f"拦截异常循环：切换过于频繁({persona})", flush=True)
            return 
            
        self.last_switch_time = current_time
        self.is_switching = True
        self.current_persona = persona
        
        try:
            # 1. 强行掐断当前正在说话的人
            if not peaceful:
                if self.openai_ws:
                    await self.openai_ws.send(json.dumps({"type": "response.cancel"}))
                await self.send(text_data=json.dumps({# 通知前端Vue立刻清空本地音频播放队列，避免声音重叠
                    "type": "ui_event", 
                    "action": "stop_audio"
                }))

            # 2. 发送热更新指令
            await self.apply_persona_update(config)

            # 3. 通知前端UI换肤
            await self.send(text_data=json.dumps({
                "type": "ui_event", 
                "action": f"switch_to_{persona}"
            }))
            # 4. 新角色根据剧本主动开口
            if persona == "helper":
                prompt_text = "[System Directive]: You have just switched in.\n" \
                "Immediately incorporate the recent conversation history and, staying strictly in character, ONLY ask the user: 'Were you having some trouble with the communication just now?'"
            else:
                prompt_text = "[System Directive]: You have just switched back in after the Helper explained things.\n " \
                "Acknowledge that the Helper just explained something, and continue the conversation in your caustic tone. Do NOT ask if they need help."
            
            
            await self.openai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions": prompt_text
                }
            }))
        finally:
            self.is_switching = False

    #初始助手人设
    TOXIC_CONFIG = {
        "instructions": "You are a caustic and sharp-tongued assistant and a native speaker.\n "
        "When the user cannot speak a complete sentence, or it appears that they cannot continue the current discussion, please immediately invoke summon_helper tool.\n "
        "When you feel that the user (a non-native speaker) fails to understand, freezes, appears incoherent/hesitant, or fails to produce meaningful speech — essentially, whenever a 'communication breakdown' occurs — you must remain silent and immediately invoke the summon_helper tool.\n "
        "It is strictly forbidden to invoke the tool at the very beginning of the interaction. Once their communication flows smoothly again based on the context, say: 'Let's get back to it.'\n "
        "Under no circumstances are you to ask the user about their struggles or difficulties! You are prohibited from reacting to the Helper's exit dialogue.\n "
        "If the user has just finished interacting with the Helper and stated 'I get it' or 'I understand,' you must speak normally. It is strictly forbidden to re-invoke summon_helper immediately in this scenario.\n "
        "You are only permitted to call the tool if the user displays confusion twice in a row (back-to-back).\n "
        "Note: In the conversation history, messages prefixed with 【Helper说】 were spoken by the teaching assistant, and messages prefixed with 【Assistant说】 were spoken by you.",
        "voice": "echo",
        "tools": [{
            "type": "function",
            "name": "summon_helper",
            "description": "Whenever the user is hesitating or saying something uncertain/meaningless, or it appears that they cannot continue the conversation smoothly, or they cannot speak well, please immediately use the tool!",
            "parameters": {"type": "object", "properties": {"user_exact_words": {
                        "type": "string", 
                        "description": "请原封不动地复述用户刚刚促使你调用此工具的原话（也就是用户真正说出口的文字）"
                    }}}
        }]
    }
    #干预助手人设
    HELPER_CONFIG = {
        "instructions": "You are a gentle and patient native speaker. Your opening line is: 'It seems you are having some trouble communicating; is there anything I can help you with?'\n "
            "Infer where the user did not quite understand, and point it out. \n "
            "When the user understands, just give a short encouraging remark (like 'Great!' or '太好了！') and stop talking.",
        "voice": "shimmer"
    }

    async def connect(self):
        self.session_id_str = self.scope['url_route']['kwargs']['session_id']
        await self.accept()
        self.db_session = await self.get_or_create_room(self.session_id_str)
        # 内部状态管理
        self.current_persona = "toxic"
        self.openai_ws = None
        self.listen_task = None
        self.is_switching = False # 状态锁：防止转换期间的干扰
        self.pending_speech = False
        self.text_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.last_user_text = ""
        # 保存连接参数
        model = "gpt-realtime-mini-2025-12-15"
        self.openai_url = f"wss://api.openai.com/v1/realtime?model={model}"
        self.headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }

        # 首次启动
        await self.init_permanent_connection()

    async def init_permanent_connection(self):
        """唯一WebSocket连接"""
        try:
            self.openai_ws = await websockets.connect(self.openai_url, additional_headers=self.headers)
            
            # 1. 初始化为普通AI
            await self.apply_persona_update(self.TOXIC_CONFIG)
            
            # 2. 注入历史记忆
            await self.inject_history_to_openai() 
            
            # 3. 启动监听任务
            self.listen_task = asyncio.create_task(self.listen_to_openai())
            
        except Exception as e:
            print(f"WebSocket初始化失败：{e}", flush=True)
            await self.send(text_data=json.dumps({"type": "error", "message": "无法连接至大模型服务"}))

    async def apply_persona_update(self, config):
        """不切断连接，只换人"""
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
            print(f"角色已热切换为：{self.current_persona}", flush=True)

    async def listen_to_openai(self):
        
        try:
            async for message in self.openai_ws:
                event = json.loads(message)
                if event.get("type") == "input_audio_buffer.speech_started":
                    self.pending_speech = True
                    if self.openai_ws:
                        await self.openai_ws.send(json.dumps({"type": "response.cancel"}))
                    await self.send(text_data=json.dumps({"type": "ui_event", "action": "stop_audio"}))
                # 拦截工具调用：召唤助手；该工具是由初始助手自动识别并调用
                elif event.get("type") == "response.function_call_arguments.done" and event.get("name") == "summon_helper":
                    print("触发：召唤助手", flush=True)
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
                # 用户对话存库
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
                # Agent对话存库
                elif event.get("type") == "response.audio_transcript.done":
                    assistant_text = event.get("transcript", "")
                    role_to_save = "assistant" if self.current_persona == "toxic" else "helper"
                    print(f"准备保存消息：角色={role_to_save}, 内容={event.get('transcript')[:10]}...")
                    await self.save_db_message(self.db_session, role_to_save, assistant_text)
                    if self.current_persona == "helper" and len(assistant_text) > 0:
                        asyncio.create_task(self.ai_judge_helper_exit(assistant_text, self.last_user_text))
                await self.send(text_data=message)
                
        except Exception as e:
            if not self.is_switching:
                print(f"OpenAI链路异常中断：{e}", flush=True)

    async def ai_judge_helper_exit(self, helper_text, user_text=""):
        """裁判AI（纯文本，低延迟，强逻辑）：结合用户上下文，严格区分'过程鼓励'和'最终收尾'"""
        prompt = f"""
        Context of the conversation:
        - The User just said: "{user_text}"
        - The Helper (a gentle explainer) replied: "{helper_text}"
        
        Task: Evaluate if the Helper's reply is a FINAL CLOSING REMARK meant to end the current explanation session.
        
        CRITICAL DISTINCTIONS (Read carefully):
        1. MID-EXPLANATION ENCOURAGEMENT (Output FALSE): If the Helper says "Great question!", "Let me explain", or "You are right, and..." before continuing to explain something. 
        2. FINAL CLOSING REMARK (Output TRUE): If the Helper is strictly acknowledging that the user has fully understood the concept, and the Helper is signing off, wrapping up, or encouraging the user to continue the main conversation (e.g., "Great, you got it! Keep going", "You're welcome, let's continue").
        
        Output instruction:
        - Reply ONLY with the word "TRUE" if it is a definitive wrap-up/closing remark or it seems that the user has understood and can continue their conversation, or when the helper says 'Great / Perfect'.
        - Reply ONLY with the word "FALSE" if she is starting an explanation, in the middle of teaching, or just giving mid-sentence encouragement.
        """
        try:
            response = await self.text_client.chat.completions.create(
                model="gpt-5.4-mini-2026-03-17",
                messages=[{"role": "system", "content": prompt}],
                max_completion_tokens=50,
                temperature=0
            )
            decision = response.choices[0].message.content.strip()
            
            if "TRUE" in decision:
                print(f"AI判定Helper完成任务---('{helper_text}')", flush=True)
                await asyncio.sleep(5)
                asyncio.create_task(self.handle_switch("toxic", self.TOXIC_CONFIG, peaceful=True))
            else:
                print(f"AI判定：这是正常对话流，不予干涉---('{helper_text}')", flush=True)
                
        except Exception as e:
            print(f"AI请求失败：{e}")
    

    # 对话传输至接口
    async def receive(self, text_data=None, bytes_data=None):
        if self.openai_ws and not self.is_switching:
            try:
                if text_data: await self.openai_ws.send(text_data)
                elif bytes_data: await self.openai_ws.send(bytes_data)
            except: pass

    async def disconnect(self, close_code):
        if self.listen_task: self.listen_task.cancel()
        if self.openai_ws: await self.openai_ws.close()

    # 历史记录的注入（上下文）
    async def inject_history_to_openai(self):
        try:
            # 获取历史记录
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
                    final_text = f"【Assistant说】：{msg.content}"
                    
                elif msg.role == "helper":
                    realtime_role = "assistant"
                    content_type = "text"
                    final_text = f"【Helper说】：{msg.content}"
                    
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
                
            print("记忆注入完成！", flush=True)
            
        except Exception as e:
            print(f"注入历史记忆时出错：{e}", flush=True)



    # ---数据库方法---
    @database_sync_to_async
    def get_or_create_room(self, session_id_str):
        try:
            session_obj, created = ChatSession.objects.get_or_create(
                session_uid=session_id_str,
                defaults={'title': '🎤 语音对话'}
            )
            print(f"[查库]成功拿到房间对象！", flush=True)
            return session_obj
        
        except Exception as e:
            print(f"[查库]致命错误：{e}", flush=True)
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
            print(f"读取历史记录失败：{e}", flush=True)
            return []

    @database_sync_to_async
    def save_db_message(self, session_obj, role, content):
        new_title = None
        if not content or not content.strip(): return 
        if not session_obj: return
        try:
            if role == "user":
                # 忽略掉常见幻听词
                hallucination_words = ["Bye.", "Thank you.", "I love you.", "See you soon."]
                if any(word in content for word in hallucination_words) and len(content.strip()) < 15:
                    print("拦截到Whisper幻听内容", flush=True)
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
            print(f"保存消息失败：{e}", flush=True)
            return None