<template>
  <div class="input-area">
    <input
      v-model="text"
      @keyup.enter="submitMessage"
      placeholder="Input text, or push the button on the right to start voice chat..."
      :disabled="isLoading || isVoiceActive"
    />

    <button
      class="voice-btn"
      :class="{ 'is-active': isVoiceActive }"
      @click="$emit('toggle-voice')"
    >
      <span class="icon">{{
        isVoiceActive ? "📞 End Voice Chat" : "🎙️ Start Voice Chat"
      }}</span>
    </button>

    <button
      class="send-btn"
      @click="submitMessage"
      :disabled="isLoading || !text.trim() || isVoiceActive"
    >
      Send Text
    </button>
  </div>
</template>

<script>
export default {
  name: "userInput",
  props: {
    isLoading: { type: Boolean, default: false },
    isVoiceActive: { type: Boolean, default: false },
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
  border-top: 4px solid #1e1e1e;
  z-index: 2;
}

.input-area input {
  flex: 1;
  padding: 14px 20px;
  background-color: #f4f4f5;
  border: 3px solid #1e1e1e;
  border-radius: 16px;
  outline: none;
  font-size: 16px;
  font-weight: 600;
  color: #1e1e1e;
  box-shadow: inset 3px 3px 0px rgba(0, 0, 0, 0.05);
  transition: all 0.2s;
  font-family: inherit;
}

.input-area input:disabled {
  background-color: #e5e7eb;
  cursor: not-allowed;
}

.input-area input:focus {
  background-color: #fff;
  border-color: #1e1e1e;
  box-shadow: 4px 4px 0px #1e1e1e;
  transform: translateY(-2px);
}

.voice-btn,
.send-btn {
  margin-left: 16px;
  border: 3px solid #1e1e1e;
  border-radius: 16px;
  cursor: pointer;
  font-weight: 900;
  font-size: 15px;
  color: #1e1e1e;
  box-shadow: 4px 4px 0px #1e1e1e;
  transition: all 0.1s ease-in-out;
  font-family: inherit;
}

.voice-btn {
  padding: 0 20px;
  background-color: #bfdbfe;
}

.voice-btn.is-active {
  background-color: #ef476f;
  color: white;
  animation: wiggle 0.5s ease-in-out infinite alternate;
}

.send-btn {
  padding: 0 24px;
  background-color: #06d6a0;
}

.send-btn:disabled {
  background-color: #9ca3af;
  box-shadow: none;
  transform: none;
  cursor: not-allowed;
}

.voice-btn:hover:not(.is-active),
.send-btn:hover:not(:disabled) {
  transform: translate(-2px, -2px);
  box-shadow: 6px 6px 0px #1e1e1e;
}

.voice-btn:active:not(.is-active),
.send-btn:active:not(:disabled) {
  transform: translate(2px, 2px);
  box-shadow: 1px 1px 0px #1e1e1e;
}

@keyframes wiggle {
  0% {
    transform: rotate(-2deg) scale(1.02);
  }
  100% {
    transform: rotate(2deg) scale(1.02);
  }
}
</style>
