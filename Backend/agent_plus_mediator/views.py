from django.shortcuts import render
from django.conf import settings
from openai import OpenAI
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import ChatSession, ChatMessage
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Normal text chat
class gptAPIView(APIView):
    def post(self, request):
        history_msg = request.data.get('message', [])
        session_id = request.data.get('session_id') 
        
        if not history_msg:
            return Response({"error": "attack detected"}, status = 400)

        if session_id and str(session_id).lower() != 'null':
            try:
                if str(session_id).isdigit():
                    session = ChatSession.objects.get(id=int(session_id))
                else:
                    session, _ = ChatSession.objects.get_or_create(session_uid=str(session_id), defaults={'title': '新对话'})
            except (ChatSession.DoesNotExist, ValueError, TypeError):
                return Response({"error": "No log found"}, status=404)
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
            api_messages = [{"role": "system", "content": "You are a native speaker (speak English)"}]
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
                temperature = 0.5
            )
            bot_reply = response.choices[0].message.content
            
            ChatMessage.objects.create(session=session, role='assistant', content=bot_reply)

            return Response({"reply": bot_reply, "session_id": session.id})
            
        except Exception as e:
            print(f"OpenAI API error：{str(e)}")
            return Response({"reply": "Unknown error"}, status = 500)

# Session list fetch
class SessionListView(APIView):
    def get(self, request):
        sessions = ChatSession.objects.all().order_by('-updated_at')
        data = [{"id": s.id, "title": s.title or "🎤 语音对话"} for s in sessions]
        return Response(data)

# Chat history fetch within a specific session
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
            return Response({"error": "No chat found"}, status=404)
    def delete(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
            session.delete()
            return Response({"message": "Deleted"}, status=200)
        except ChatSession.DoesNotExist:
            return Response({"error": "No chat found"}, status=404)