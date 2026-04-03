<template>
  <div class="history-sidebar">
    <button class="new-chat-btn" @click="$emit('new-chat')">+ 新开对话</button>

    <div class="session-list">
      <div
        v-for="session in sessions"
        :key="session.id"
        :class="['session-item', { active: session.id === activeSessionId }]"
        @click="$emit('select-session', session.id)"
      >
        <span class="session-title">{{ session.title || "新对话" }}</span>
        <button
          class="delete-btn"
          @click.stop="$emit('delete-session', session.id)"
          title="删除对话"
        >
          ✕
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "chatHistory",
  props: {
    sessions: { type: Array, required: true },
    activeSessionId: { type: [Number, String], required: true },
  },
};
</script>

<style scoped>
.history-sidebar {
  width: 260px;
  background-color: #202123;
  color: white;
  display: flex;
  flex-direction: column;
  padding: 12px;
  height: 100vh;
  box-sizing: border-box;
}
.new-chat-btn {
  background-color: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  padding: 14px;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s;
  margin-bottom: 20px;
}
.new-chat-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
}
.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #ececf1;
  transition: background-color 0.2s;
}
.session-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}
.session-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
}
.session-item.active {
  background-color: rgba(255, 255, 255, 0.1);
}
.delete-btn {
  background: none;
  border: none;
  color: #8e8ea0;
  cursor: pointer;
  font-size: 14px;
  padding: 0 4px;
  display: none;
}
.session-item:hover .delete-btn {
  display: block;
}
.delete-btn:hover {
  color: #ef4444;
}
</style>
