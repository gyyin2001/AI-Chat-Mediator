<template>
  <div class="chat-header">
    <h2>{{ title }}</h2>
    <button class="clear-btn" @click="$emit('clear')" title="清空聊天记录">
      清空
    </button>
  </div>
</template>

<script>
export default {
  name: "gptHeader",
  props: {
    title: { type: String, default: "fake ChatGPT" },
  },
};
</script>

<style scoped>
.chat-header {
  padding: 16px 24px;
  background-color: #ffffff;
  color: #1f2937;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e5e7eb;
}
.chat-header h2 {
  margin: 0;
  flex: 1;
  text-align: center;
  font-size: 1.25rem;
  font-weight: 600;
  padding-left: 50px;
}
.clear-btn {
  background-color: transparent;
  color: #ef4444;
  border: 1px solid #ef4444;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}
.clear-btn:hover {
  background-color: #fef2f2;
}
</style>
