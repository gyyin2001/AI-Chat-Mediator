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
      <div v-if="msg.role === 'helper'" class="avatar-label">🍑Tom</div>
      <div v-if="msg.role === 'assistant'" class="avatar-label">🍈Alex</div>
      <div class="message-bubble" style="white-space: pre-wrap">
        {{ msg.content }}
      </div>
    </div>

    <div v-if="isLoading" class="message-wrapper left">
      <div class="message-bubble loading">Gathering thoughts... Hold on...</div>
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
  gap: 24px;
  background-color: #f8f9fa;
  background-image: radial-gradient(#d1d5db 2px, transparent 2px);
  background-size: 24px 24px;
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
  font-size: 13px;
  font-weight: 900;
  color: #fff;
  background-color: #1e1e1e;
  border: 2px solid #1e1e1e;
  padding: 2px 10px;
  border-radius: 12px;
  margin-bottom: 6px;
  margin-left: 8px;
  box-shadow: 2px 2px 0px rgba(0, 0, 0, 0.2);
  letter-spacing: 0.5px;
}

.is-helper .avatar-label {
  background-color: #ef476f;
}

.message-bubble {
  max-width: 75%;
  padding: 14px 20px;
  border-radius: 20px;
  line-height: 1.6;
  font-size: 16px;
  font-weight: 600;
  color: #1e1e1e;
  border: 3px solid #1e1e1e;
  box-shadow: 4px 4px 0px #1e1e1e;
}

.right .message-bubble {
  background-color: #06d6a0;
  border-bottom-right-radius: 4px;
}

.left .message-bubble {
  background-color: #ffffff;
  border-bottom-left-radius: 4px;
}

.message-wrapper.is-helper .message-bubble {
  background-color: #fbcfe8;
  border-bottom-left-radius: 4px;
}

.loading {
  font-style: italic;
  font-weight: 900;
  color: #1e1e1e;
  background-color: #fef08a !important;
  border: 3px dashed #1e1e1e !important;
  box-shadow: 4px 4px 0px #1e1e1e !important;
  animation: float 2s ease-in-out infinite;
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5px);
  }
}
</style>
