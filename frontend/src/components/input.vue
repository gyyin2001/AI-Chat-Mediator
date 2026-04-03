<template>
  <div class="input-area">
    <input
      v-model="text"
      @keyup.enter="submitMessage"
      placeholder="输入文字，或点击右侧开启语音通话..."
      :disabled="isLoading || isVoiceActive"
    />

    <button
      class="voice-btn"
      :class="{ 'is-active': isVoiceActive }"
      @click="$emit('toggle-voice')"
    >
      <span class="icon">{{
        isVoiceActive ? "📞 挂断通话" : "🎙️ 开启通话"
      }}</span>
    </button>

    <button
      class="send-btn"
      @click="submitMessage"
      :disabled="isLoading || !text.trim() || isVoiceActive"
    >
      发送文字
    </button>
  </div>
</template>

<script>
export default {
  name: "userInput",
  props: {
    isLoading: { type: Boolean, default: false },
    isVoiceActive: { type: Boolean, default: false }, // 状态：是否在通话中
  },
  data() {
    return { text: "" };
  },
  methods: {
    submitMessage() {
      const content = this.text.trim();
      if (content) {
        this.$emit("send", content);
        this.text = "";
      }
    },
  },
};
</script>

<style scoped>
.input-area {
  display: flex;
  padding: 20px;
  background-color: #ffffff;
  border-top: 1px solid #e5e7eb;
}
.input-area input {
  flex: 1;
  padding: 14px 18px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  outline: none;
  font-size: 15px;
  transition: border-color 0.2s;
}
.input-area input:disabled {
  background-color: #f3f4f6;
  cursor: not-allowed;
}
.input-area input:focus {
  border-color: #10b981;
}

.voice-btn {
  margin-left: 12px;
  padding: 0 20px;
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s;
}
.voice-btn.is-active {
  background-color: #fee2e2;
  color: #ef4444;
  border-color: #ef4444;
  animation: pulse 2s infinite;
}

.send-btn {
  margin-left: 12px;
  padding: 0 24px;
  background-color: #10b981;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}
.send-btn:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
  }
}
</style>
