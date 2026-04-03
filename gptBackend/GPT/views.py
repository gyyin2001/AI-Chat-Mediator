from django.shortcuts import render
from django.conf import settings
from openai import OpenAI
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import ChatSession, ChatMessage
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# 文本聊天
class gptAPIView(APIView):
    def post(self, request):
        history_msg = request.data.get('message', [])
        session_id = request.data.get('session_id') 
        
        if not history_msg:
            return Response({"error": "~攻击拦截~"}, status = 400)

        if session_id and str(session_id).lower() != 'null':
            try:
                session = ChatSession.objects.get(id=int(session_id))
            except (ChatSession.DoesNotExist, ValueError, TypeError):
                return Response({"error": "找不到该对话记录或ID无效"}, status=404)
        else:
            session = ChatSession.objects.create(title="新对话")

        latest_user_msg = history_msg[-1].get('content', '')
        if latest_user_msg:

            ChatMessage.objects.create(session=session, role='user', content=latest_user_msg)
            if session.title == "新对话":
                if len(latest_user_msg) > 9:
                    session.title = "提问：" + latest_user_msg[:9] + "..."
                else:
                    session.title = "提问：" + latest_user_msg[:9]
                session.save()

        try:
            api_messages = [{"role": "system", "content": "你是一个AI助手（母语使用者），请根据上下文语境回复"}]
            for msg in history_msg:
                if msg.get('role') in ['user', 'assistant', 'helper'] and msg.get('content'):
                    mapped_role = 'assistant' if msg.get('role') == 'helper' else msg.get('role')
                    api_messages.append({
                        "role": mapped_role,
                        "content": msg['content']
                    })

            response = client.chat.completions.create(
                model = 'gpt-4o-mini',
                messages = api_messages,
                temperature = 0.666
            )
            bot_reply = response.choices[0].message.content
            
            ChatMessage.objects.create(session=session, role='assistant', content=bot_reply)

            return Response({"reply": bot_reply, "session_id": session.id})
            
        except Exception as e:
            print(f"OpenAI接口报错了：{str(e)}")
            return Response({"reply": "~发生了未知错误~"}, status = 500)

# 拉取对话列表
class SessionListView(APIView):
    def get(self, request):
        sessions = ChatSession.objects.all().order_by('-updated_at')
        data = [{"id": s.id, "title": s.title or "🎤 语音对话"} for s in sessions]
        return Response(data)

# 拉取特定对话详细记录
class SessionHistoryView(APIView):
    def get(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
            messages = session.messages.all().order_by('created_at')
            msg_data = [{"role": m.role, "content": m.content} for m in messages]
            return Response({
                "id": session.id, 
                "title": session.title, 
                "messages": msg_data
            })
        except ChatSession.DoesNotExist:
            return Response({"error": "对话不存在"}, status=404)
    def delete(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
            session.delete()
            return Response({"message": "删除成功"}, status=200)
        except ChatSession.DoesNotExist:
            return Response({"error": "对话不存在"}, status=404)