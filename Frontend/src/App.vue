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
        :title="isVoiceActive ? '🔴 Voice Chat Active...' : 'Alex The Tutor'"
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
const WS_BASE_URL = "ws://127.0.0.1:8000/ws/realtime";

// Receive and play audio on the frontend
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
    console.log("This is when you stop the current voice");
    this.activeSources.forEach((source) => {
      try {
        source.stop();
      } catch (e) {
        return;
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
        try {
          const msg = JSON.parse(event.data);
          this.handleMessage(msg);
        } catch (e) {
          console.warn("WebSocket received non-JSON object", event.data);
        }
      };

      this.ws.onerror = (e) => {
        console.error("WebSocket Error:", e);
        this.stop();
      };

      this.ws.onclose = () => {
        this.stop();
      };
    } catch (e) {
      console.error("Failed to start audio engine：", e);
      alert("Please check audio permission!");
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
      if (this.onMessage) this.onMessage("user_temp", "👂 AI is hearing...");
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
        // Overtake the placeholder for voice bubble (to text)
        messages.push({
          role: "user",
          content: content,
          isTemp: true,
        });
      } else if (roleType === "user_replace") {
        // Transcribe
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
        // Agent response
        const finalRole =
          roleType === "ai_response" ? this.currentSpeaker : roleType;
        if (lastMsg && lastMsg.role === finalRole) {
          if (!lastMsg.content.includes(content)) {
            lastMsg.content += " " + content;
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
        console.log("Title has updated：", newTitle);
      }
    };
  },
  beforeUnmount() {
    audioEngine.stop();
  },
  methods: {
    async fetchSessions() {
      // Fetch a list of sessions
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
        console.error("Sessions failed to fetch：", error);
      }
    },

    async handleSelectSession(id) {
      // Select specific session
      this.activeSessionId = id;
      const session = this.sessions.find((s) => s.id === id);
      if (session && session.messages.length === 0 && typeof id === "number") {
        this.isLoading = true;
        try {
          const response = await axios.get(`${API_BASE_URL}/sessions/${id}/`);
          session.messages = response.data.messages;
        } catch (error) {
          console.error("Chat history failed to fetch：", error);
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
            content: "Hi there, what would you like to talk about? 🤭",
          },
        ],
      };
      this.sessions.unshift(newSession);
      this.activeSessionId = tempId;
    },

    async handleDeleteSession(id) {
      if (!confirm("Sure to delete the session? 😰")) return;
      if (typeof id === "number") {
        try {
          await axios.delete(`${API_BASE_URL}/sessions/${id}/`);
        } catch (error) {
          console.error("Failed to delete：", error);
          alert("Try it again. (；′⌒`)");
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
      if (confirm("Sure to clean up history?")) {
        this.currentSession.messages = [
          { role: "assistant", content: "Succeed!" },
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
          session_id: this.activeSessionId,
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
        console.error("API failure：", error);
        this.currentSession.messages.push({
          role: "assistant",
          content: "Sorry, cannot respond for now... 😔",
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
  font-family:
    "Comic Sans MS", "Chalkboard SE", "Comic Neue", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  background-color: #fdf6e3;
}
</style>

<style scoped>
.app-wrapper {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: #fff;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #ffffff;
  border-left: 4px solid #1e1e1e;
  z-index: 10;
}
</style>
