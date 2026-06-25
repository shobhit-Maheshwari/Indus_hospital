export class WebSocketApiService {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.onStreamStart = null;
    this.onStreamChunk = null;
    this.onStreamEnd = null;
    this.onError = null;
  }

  connect() {
    this.socket = new WebSocket(this.url + '/ws/chat');

    this.socket.onopen = () => {
      console.log('Connected to Chat API');
      this.reconnectAttempts = 0;
    };

    this.socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.error) {
        if (this.onError) this.onError(data.error);
        return;
      }

      if (data.streaming === true && this.onStreamStart) {
        this.onStreamStart();
      } else if (data.chunk && this.onStreamChunk) {
        this.onStreamChunk(data.chunk);
      } else if (data.streaming === false && data.response && this.onStreamEnd) {
        this.onStreamEnd(data.response);
      }
    };

    this.socket.onclose = () => {
      console.log('Disconnected from Chat API');
      this.reconnect();
    };

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
      setTimeout(() => this.connect(), 2000 * this.reconnectAttempts);
    }
  }

  sendMessage(message, philosopherId) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        message: message,
        philosopher_id: philosopherId
      }));
    } else {
      if (this.onError) this.onError('Not connected to server');
    }
  }
}
