from django.db import models

class ChatSession(models.Model):
    title = models.CharField(max_length=255, default="初始对话")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    session_uid = models.CharField(max_length=100, default="default-room")
    def __str__(self):
        return self.title

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=20)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.session.title} - {self.role}"