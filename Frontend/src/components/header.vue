<template>
  <div class="chat-header">
    <h2>{{ title }}</h2>
    <button class="clear-btn" @click="$emit('clear')" title="清空聊天记录">
      Clean Up
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
  color: #1e1e1e;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 4px solid #1e1e1e;
  z-index: 2;
}

.chat-header h2 {
  margin: 0;
  flex: 1;
  text-align: center;
  font-size: 1.4rem;
  font-weight: 900;
  padding-left: 50px;
  letter-spacing: 1px;
}

.clear-btn {
  background-color: #118ab2;
  color: #ffffff;
  border: 3px solid #1e1e1e;
  padding: 8px 16px;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
  box-shadow: 3px 3px 0px #1e1e1e;
  transition: all 0.1s;
}

.clear-btn:hover {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0px #1e1e1e;
}

.clear-btn:active {
  transform: translate(2px, 2px);
  box-shadow: 1px 1px 0px #1e1e1e;
}
</style>
