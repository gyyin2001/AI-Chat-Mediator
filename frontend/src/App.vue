<template>
  <div class="app-wrapper">
    <chatHistory
      :sessions="sessions"
      :activeSessionId="activeSessionId"
      @new-chat="handleNewChat"
      @select-session="handleSelectSession"
      @delete-session="handleDeleteSession"
    />

    <div class="chat-container">
      <gptHeader
        :title="
          isVoiceActive ? '🔴 实时通话中...' : 'Attention Is All You Need'
        "
        @clear="clearMessages"
      />
      <chatView
        :messages="currentSession.messages || []"
        :isLoading="isLoading"
      />
      <userInput
        :isLoading="isLoading"
        :isVoiceActive="isVoiceActive"
        @send="handleSendMessage"
        @toggle-voice="toggleVoice"
      />
    </div>
  </div>
</template>

<script>
import axios from "axios";
import gptHeader from "./components/header.vue";
import chatView from "./components/chatView.vue";
import userInput from "./components/input.vue";
import chatHistory from "./components/chatHistory.vue";

const API_BASE_URL = "http://127.0.0.1:8000/api";
const WS_BASE_URL = "ws://127.0.0.1:8000/ws/realtime"; // WebSocket 地址

// 前端收放音频管理
class RealtimeAudioManager {
  constructor() {
    this.ws = null;
    this.audioCtx = null;
    this.micStream = null;
    this.micNode = null;
    this.nextPlayTime = 0;
    this.isActive = false;
    this.activeSources = [];
    this.onStateChange = null;
    this.onMessage = null;
    this.onLoading = null;
    this.threshold = 0.00001;
  }

  interrupt() {
    console.log("收到后端指令：清空前端音频队列");
    this.activeSources.forEach((source) => {
      try {
        source.stop();
      } catch (e) {
        /* 忽略报错 */
      }
    });
    this.activeSources = [];
    if (this.audioCtx) {
      this.nextPlayTime = this.audioCtx.currentTime;
    }
  }

  async start(sessionId) {
    try {
      const AudioContextClass =
        window.AudioContext || window.webkitAudioContext;

      const ctx = new AudioContextClass({ sampleRate: 24000 });

      this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const source = ctx.createMediaStreamSource(this.micStream);

      const workletCode = `
  class PCMProcessor extends AudioWorkletProcessor {
    process(inputs, outputs, parameters) {
      const input = inputs[0];
      if (input && input.length > 0) {
        const channelData = input[0];
        let sum = 0;
        for (let i = 0; i < channelData.length; i++) {
          sum += channelData[i] * channelData[i];
        }
        const rms = Math.sqrt(sum / channelData.length);
        const pcm16Data = new Int16Array(channelData.length);
        for (let i = 0; i < channelData.length; i++) {
          let s = Math.max(-1, Math.min(1, channelData[i]));
          pcm16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        this.port.postMessage({ pcm: pcm16Data, volume: rms });
      }
      return true;
    }
  }
  registerProcessor('pcm-processor', PCMProcessor);
`;

      const blob = new Blob([workletCode], { type: "application/javascript" });
      const workletUrl = URL.createObjectURL(blob);

      await ctx.audioWorklet.addModule(workletUrl);

      const micNode = new AudioWorkletNode(ctx, "pcm-processor");

      micNode.port.onmessage = (event) => {
        if (!this.isActive || !this.ws || this.ws.readyState !== WebSocket.OPEN)
          return;

        const { pcm, volume } = event.data;
        if (volume < this.threshold) {
          return;
        }
        const buffer = new Uint8Array(pcm.buffer);
        let binary = "";
        for (let i = 0; i < buffer.byteLength; i++) {
          binary += String.fromCharCode(buffer[i]);
        }
        const base64Audio = btoa(binary);

        this.ws.send(
          JSON.stringify({
            type: "input_audio_buffer.append",
            audio: base64Audio,
          }),
        );
      };

      source.connect(micNode);

      URL.revokeObjectURL(workletUrl);
      this.audioCtx = ctx;
      this.micNode = micNode;
      this.nextPlayTime = ctx.currentTime;

      this.ws = new WebSocket(`${WS_BASE_URL}/${sessionId}/`);

      this.ws.onopen = () => {
        this.isActive = true;
        if (this.onStateChange) this.onStateChange(true);
      };

      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        this.handleMessage(msg);
      };

      this.ws.onerror = (e) => {
        console.error("WebSocket Error:", e);
        this.stop();
      };

      this.ws.onclose = () => {
        this.stop();
      };
    } catch (e) {
      console.error("音频引擎启动失败：", e);
      alert("启动语音失败，请检查控制台或麦克风权限！");
      this.stop();
    }
  }

  stop() {
    this.isActive = false;
    if (this.onStateChange) this.onStateChange(false);

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    if (this.micNode) {
      this.micNode.disconnect();
      this.micNode = null;
    }
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop());
      this.micStream = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
  }

  handleMessage(msg) {
    if (msg.type === "title_update") {
      if (this.onTitleUpdate) this.onTitleUpdate(msg.title);
      return;
    }
    if (msg.type === "ui_event") {
      if (msg.action === "stop_audio") {
        this.interrupt();
        return;
      }

      if (
        msg.action === "switch_to_helper" ||
        msg.action === "switch_to_toxic"
      ) {
        if (this.audioCtx) this.nextPlayTime = this.audioCtx.currentTime;
      }
      if (this.onAgentSwitch) this.onAgentSwitch(msg.action);
      return;
    }

    if (msg.type === "response.audio.delta" && msg.delta) {
      this.playAudioChunk(msg.delta);
    }
    if (msg.type === "input_audio_buffer.speech_started") {
      if (this.onMessage) this.onMessage("user_temp", "👂 AI正在倾听...");
    }

    if (
      msg.type === "conversation.item.input_audio_transcription.completed" &&
      msg.transcript
    ) {
      if (this.onMessage) this.onMessage("user_replace", msg.transcript);
    }
    if (msg.type === "response.audio_transcript.done" && msg.transcript) {
      if (this.onMessage) this.onMessage("ai_response", msg.transcript);
    }
    if (msg.type === "response.created") {
      if (this.onLoading) this.onLoading(true);
    }
    if (msg.type === "response.done") {
      if (this.onLoading) this.onLoading(false);
    }
  }

  playAudioChunk(base64Audio) {
    if (!this.audioCtx) return;

    const binaryString = atob(base64Audio);
    const pcm16Data = new Int16Array(binaryString.length / 2);
    for (let i = 0; i < pcm16Data.length; i++) {
      pcm16Data[i] =
        (binaryString.charCodeAt(i * 2) & 0xff) |
        (binaryString.charCodeAt(i * 2 + 1) << 8);
    }

    const float32Data = new Float32Array(pcm16Data.length);
    for (let i = 0; i < pcm16Data.length; i++) {
      float32Data[i] = pcm16Data[i] / 0x8000;
    }

    const audioBuffer = this.audioCtx.createBuffer(
      1,
      float32Data.length,
      24000,
    );
    audioBuffer.getChannelData(0).set(float32Data);

    const source = this.audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioCtx.destination);

    source.onended = () => {
      const index = this.activeSources.indexOf(source);
      if (index > -1) this.activeSources.splice(index, 1);
    };

    const currentTime = this.audioCtx.currentTime;
    if (this.nextPlayTime < currentTime) {
      this.nextPlayTime = currentTime;
    }
    source.start(this.nextPlayTime);
    this.activeSources.push(source);
    this.nextPlayTime += audioBuffer.duration;
  }
}
const audioEngine = new RealtimeAudioManager();

export default {
  name: "App",
  components: {
    gptHeader,
    chatView,
    userInput,
    chatHistory,
  },
  data() {
    return {
      sessions: [],
      activeSessionId: null,
      isLoading: false,

      isVoiceActive: false,
      currentSpeaker: "assistant",
    };
  },
  computed: {
    currentSession() {
      return (
        this.sessions.find((s) => s.id === this.activeSessionId) || {
          messages: [],
        }
      );
    },
  },
  async created() {
    await this.fetchSessions();
    audioEngine.onStateChange = (isActive) => {
      this.isVoiceActive = isActive;
    };
    audioEngine.onAgentSwitch = (action) => {
      if (action === "switch_to_helper") this.currentSpeaker = "helper";
      if (action === "switch_to_toxic") this.currentSpeaker = "assistant";
    };

    audioEngine.onMessage = (roleType, content) => {
      const messages = this.currentSession.messages;
      const lastMsg =
        messages.length > 0 ? messages[messages.length - 1] : null;

      if (roleType === "user_temp") {
        // 1. 处理“正在倾听”占位符
        messages.push({
          role: "user",
          content: content,
          isTemp: true,
        });
      } else if (roleType === "user_replace") {
        // 2. 处理用户语音转文字的替换
        let tempMsg = null;
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].isTemp) {
            tempMsg = messages[i];
            break;
          }
        }

        if (tempMsg) {
          tempMsg.content = "🎤 " + content;
          tempMsg.isTemp = false;
        } else {
          if (lastMsg && lastMsg.role === "user") {
            lastMsg.content += " " + content;
          } else {
            messages.push({ role: "user", content: "🎤 " + content });
          }
        }
      } else {
        // 3. 处理AI响应
        const finalRole =
          roleType === "ai_response" ? this.currentSpeaker : roleType;
        if (lastMsg && lastMsg.role === finalRole) {
          if (!lastMsg.content.includes(content)) {
            lastMsg.content += content;
          }
        } else {
          messages.push({ role: finalRole, content: content });
        }
      }
    };

    audioEngine.onLoading = (isLoading) => {
      this.isLoading = isLoading;
    };
    audioEngine.onTitleUpdate = (newTitle) => {
      if (this.currentSession) {
        this.currentSession.title = newTitle;
        console.log("标题已实时同步：", newTitle);
      }
    };
  },
  beforeUnmount() {
    audioEngine.stop();
  },
  methods: {
    async fetchSessions() {
      // 获取对话列表
      try {
        const response = await axios.get(`${API_BASE_URL}/sessions/`);
        this.sessions = response.data.map((session) => ({
          ...session,
          messages: [],
        }));

        if (this.sessions.length > 0) {
          this.handleSelectSession(this.sessions[0].id);
        } else {
          this.handleNewChat();
        }
      } catch (error) {
        console.error("获取对话列表失败：", error);
      }
    },

    async handleSelectSession(id) {
      // 选择特定会话
      this.activeSessionId = id;
      const session = this.sessions.find((s) => s.id === id);
      if (session && session.messages.length === 0 && typeof id === "number") {
        this.isLoading = true;
        try {
          const response = await axios.get(`${API_BASE_URL}/sessions/${id}/`);
          session.messages = response.data.messages;
        } catch (error) {
          console.error("获取聊天记录失败：", error);
        } finally {
          this.isLoading = false;
        }
      }
    },

    handleNewChat() {
      const tempId = "temp-" + Date.now();
      const newSession = {
        id: tempId,
        title: "新对话",
        messages: [
          {
            role: "assistant",
            content: "你开启了一段新对话，想聊点什么？🤭",
          },
        ],
      };
      this.sessions.unshift(newSession);
      this.activeSessionId = tempId;
    },

    async handleDeleteSession(id) {
      if (!confirm("确定要删除这个对话吗？😰")) return;
      if (typeof id === "number") {
        try {
          await axios.delete(`${API_BASE_URL}/sessions/${id}/`);
        } catch (error) {
          console.error("删除对话失败：", error);
          alert("删除失败，请稍后重试。(；′⌒`)");
          return;
        }
      }

      this.sessions = this.sessions.filter((session) => session.id !== id);

      if (this.activeSessionId === id) {
        if (this.sessions.length > 0) {
          this.handleSelectSession(this.sessions[0].id);
        } else {
          this.handleNewChat();
        }
      }
    },

    clearMessages() {
      if (confirm("确定要清空当前页面的聊天记录吗？")) {
        this.currentSession.messages = [
          { role: "assistant", content: "聊天记录已清空！" },
        ];
      }
    },

    async handleSendMessage(text) {
      this.currentSession.messages.push({ role: "user", content: text });
      this.isLoading = true;

      try {
        const contextMsg = this.currentSession.messages.slice(-10);
        const payload = {
          message: contextMsg,
          session_id:
            typeof this.activeSessionId === "number"
              ? this.activeSessionId
              : null,
        };

        const response = await axios.post(`${API_BASE_URL}/gptchat/`, payload);

        if (response.data && response.data.reply) {
          this.currentSession.messages.push({
            role: "assistant",
            content: response.data.reply,
          });

          if (
            typeof this.activeSessionId === "string" &&
            response.data.session_id
          ) {
            const realId = response.data.session_id;
            this.currentSession.id = realId;
            this.activeSessionId = realId;

            const defaultTitles = ["新对话", "初始对话", "🎤 语音对话"];
            if (defaultTitles.includes(this.currentSession.title)) {
              this.currentSession.title =
                text.length > 9
                  ? "提问：" + text.substring(0, 9) + "..."
                  : "提问：" + text;
            }
          }
        }
      } catch (error) {
        console.error("API请求出错：", error);
        this.currentSession.messages.push({
          role: "assistant",
          content: "抱歉，我暂时不能回答你的问题... 😔",
        });
      } finally {
        this.isLoading = false;
      }
    },
    async toggleVoice() {
      if (audioEngine.isActive) {
        audioEngine.stop();
      } else {
        const sessionId = this.activeSessionId || "new";
        await audioEngine.start(sessionId);
      }
    },
  },
};
</script>

<style>
body,
html {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica,
    Arial, sans-serif;
}
</style>

<style scoped>
.app-wrapper {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: #ffffff;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #ffffff;
  border-left: 1px solid #e5e5e5;
}
</style>
