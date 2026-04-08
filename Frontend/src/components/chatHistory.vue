<template>
  <div class="history-sidebar">
    <button class="new-chat-btn" @click="$emit('new-chat')">
      + New Session
    </button>

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
  width: 280px;
  background-color: #ffd166;
  color: #1e1e1e;
  display: flex;
  flex-direction: column;
  padding: 16px;
  height: 100vh;
  box-sizing: border-box;
}

.new-chat-btn {
  background-color: #ff9fb2;
  color: #1e1e1e;
  border: 3px solid #1e1e1e;
  padding: 14px;
  border-radius: 16px;
  cursor: pointer;
  text-align: center;
  font-size: 16px;
  font-weight: 900;
  box-shadow: 4px 4px 0px #1e1e1e;
  transition: all 0.1s ease-in-out;
  margin-bottom: 24px;
}

.new-chat-btn:hover {
  transform: translate(-2px, -2px);
  box-shadow: 6px 6px 0px #1e1e1e;
}
.new-chat-btn:active {
  transform: translate(2px, 2px);
  box-shadow: 1px 1px 0px #1e1e1e;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15px;
  font-weight: bold;
  color: #1e1e1e;
  border: 3px solid transparent;
  transition: all 0.2s;
  margin-bottom: 8px;
}

.session-item:hover {
  background-color: rgba(255, 255, 255, 0.6);
  border-color: #1e1e1e;
}

.session-item.active {
  background-color: #ffffff;
  border: 3px solid #1e1e1e;
  box-shadow: 3px 3px 0px #1e1e1e;
}

.session-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.delete-btn {
  background: #ff5e5e;
  border: 2px solid #1e1e1e;
  border-radius: 50%;
  color: white;
  cursor: pointer;
  font-size: 12px;
  width: 24px;
  height: 24px;
  display: none;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  box-shadow: 2px 2px 0px #1e1e1e;
}

.session-item:hover .delete-btn {
  display: flex;
}

.delete-btn:active {
  transform: translate(1px, 1px);
  box-shadow: 0px 0px 0px #1e1e1e;
}
</style>
