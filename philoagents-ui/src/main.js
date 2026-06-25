import './style.css';
import { WebSocketApiService } from './chat.js';
import { marked } from 'marked';

document.addEventListener('DOMContentLoaded', () => {
  const fab = document.getElementById('fab');
  const chatPanel = document.getElementById('chat-panel');
  const closeChat = document.getElementById('close-chat');
  const chatMessages = document.getElementById('chat-messages');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-msg');

  // Initialize WebSocket service
  const apiService = new WebSocketApiService('ws://localhost:8000');
  let currentAiMessageElement = null;
  let currentAiMessageRaw = '';

  apiService.connect();

  apiService.onStreamStart = () => {
    currentAiMessageElement = document.createElement('div');
    currentAiMessageElement.className = 'message ai markdown-body';
    chatMessages.appendChild(currentAiMessageElement);
    currentAiMessageRaw = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  apiService.onStreamChunk = (chunk) => {
    if (currentAiMessageElement) {
      currentAiMessageRaw += chunk;
      currentAiMessageElement.innerHTML = marked.parse(currentAiMessageRaw);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  };

  apiService.onStreamEnd = (fullResponse) => {
    if (currentAiMessageElement) {
      currentAiMessageElement.innerHTML = marked.parse(fullResponse);
    }
    currentAiMessageElement = null;
    currentAiMessageRaw = '';
  };

  apiService.onError = (error) => {
    console.error('Chat error:', error);
    const errDiv = document.createElement('div');
    errDiv.className = 'message ai';
    errDiv.style.color = 'red';
    errDiv.textContent = 'Sorry, there was an error communicating with the server.';
    chatMessages.appendChild(errDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  // Toggle chat
  fab.addEventListener('click', () => {
    chatPanel.classList.remove('hidden');
  });

  closeChat.addEventListener('click', () => {
    chatPanel.classList.add('hidden');
  });

  // Send message
  const sendMessage = () => {
    const text = chatInput.value.trim();
    if (!text) return;

    // Add user message
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.textContent = text;
    chatMessages.appendChild(userMsg);
    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Send to backend via Aura agent
    apiService.sendMessage(text, 'aura');
  };

  sendBtn.addEventListener('click', sendMessage);
  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  });
});
