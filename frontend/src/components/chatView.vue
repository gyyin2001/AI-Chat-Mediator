<template>
  <div class="message-list" ref="listRef">
    <div
      v-for="(msg, index) in messages"
      :key="index"
      :class="[
        'message-wrapper',
        msg.role === 'user' ? 'right' : 'left',
        msg.role === 'helper' ? 'is-helper' : '',
      ]"
    >
      <div v-if="msg.role === 'helper'" class="avatar-label">💖Helper</div>
      <div v-if="msg.role === 'assistant'" class="avatar-label">😈Agent</div>
      <div class="message-bubble" style="white-space: pre-wrap">
        {{ msg.content }}
      </div>
    </div>

    <div v-if="isLoading" class="message-wrapper left">
      <div class="message-bubble loading">正在思考，请稍候...</div>
    </div>
  </div>
</template>

<script>
export default {
  name: "chatView",
  props: {
    messages: { type: Array, required: true },
    isLoading: { type: Boolean, default: false },
  },
  watch: {
    messages: {
      deep: true,
      handler() {
        this.scrollToBottom();
      },
    },
    isLoading() {
      this.scrollToBottom();
    },
  },
  methods: {
    async scrollToBottom() {
      await this.$nextTick();
      const list = this.$refs.listRef;
      if (list) list.scrollTop = list.scrollHeight;
    },
  },
};
</script>

<style scoped>
.message-list {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: #f9fafb;
}

.message-bubble {
  max-width: 75%;
  padding: 12px 18px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.left .message-bubble {
  background-color: #ffffff;
  color: #1f2937;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 4px;
}
.right .message-bubble {
  background-color: #10b981;
  color: white;
  border-bottom-right-radius: 4px;
}
.loading {
  font-style: italic;
  color: #6b7280;
  background-color: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
.message-wrapper {
  display: flex;
  flex-direction: column;
}
.message-wrapper.right {
  align-items: flex-end;
}
.message-wrapper.left {
  align-items: flex-start;
}

.avatar-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
  margin-left: 4px;
}

.message-wrapper.is-helper .message-bubble {
  background-color: #fdf2f8;
  color: #db2777;
  border: 1px solid #fbcfe8;
  box-shadow: 0 2px 4px rgba(219, 39, 119, 0.1);
}
</style>
