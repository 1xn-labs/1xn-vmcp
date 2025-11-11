import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/auth-context';

interface WebSocketMessage {
  type: string;
  conversation_id?: string;
  tool_calls?: any[];
  timestamp?: string;
}

interface UseWebSocketOptions {
  onToolCallUpdate?: (conversationId: string, toolCalls: any[]) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

// Global WebSocket instance to prevent multiple connections
let globalWebSocket: WebSocket | null = null;
let globalConnectionState = {
  isConnected: false,
  error: null as string | null,
  lastMessage: null as WebSocketMessage | null,
};
let isConnecting = false;
let connectionAttempts = 0;
const MAX_RECONNECTION_ATTEMPTS = 5;

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { user } = useAuth();
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // const [isConnected, setIsConnected] = useState(globalConnectionState.isConnected);
  // const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(globalConnectionState.lastMessage);
  // const [error, setError] = useState<string | null>(globalConnectionState.error);
  
  // WebSocket temporarily disabled
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [error, setError] = useState<string | null>('WebSocket disabled');

  const CHAT_SERVICE_URL = import.meta.env.VITE_UNIFIED_BACKEND_URL;
  const WS_URL = CHAT_SERVICE_URL?.replace('http', 'ws') || '<CHAT_SERVICE_URL_UNDEFINED>';

  const connect = useCallback(() => {
    // WebSocket connection temporarily disabled
    console.log('WebSocket connection disabled');
    return;
    
    // if (globalWebSocket?.readyState === WebSocket.OPEN) {
    //   console.log('WebSocket already connected');
    //   return;
    // }

    // if (globalWebSocket?.readyState === WebSocket.CONNECTING) {
    //   console.log('WebSocket connection already in progress');
    //   return;
    // }

    // if (isConnecting) {
    //   console.log('WebSocket connection already in progress (flag)');
    //   return;
    // }

    // if (connectionAttempts >= MAX_RECONNECTION_ATTEMPTS) {
    //   console.log('Max reconnection attempts reached, stopping');
    //   return;
    // }

    // try {
    //   isConnecting = true;
    //   connectionAttempts++;
      
    //   const wsUrl = `${WS_URL}/ws`;
    //   console.log(`Connecting to WebSocket (attempt ${connectionAttempts}):`, wsUrl);
      
    //   globalWebSocket = new WebSocket(wsUrl);

    //   globalWebSocket.onopen = () => {
    //     console.log('WebSocket connected successfully');
    //     isConnecting = false;
    //     connectionAttempts = 0; // Reset attempts on successful connection
    //     globalConnectionState.isConnected = true;
    //     globalConnectionState.error = null;
    //     setIsConnected(true);
    //     setError(null);
    //     options.onConnect?.();

    //     // Start ping interval to keep connection alive
    //     pingIntervalRef.current = setInterval(() => {
    //       if (globalWebSocket?.readyState === WebSocket.OPEN) {
    //         globalWebSocket.send(JSON.stringify({ type: 'ping' }));
    //       }
    //     }, 30000); // Ping every 30 seconds
    //   };

    //   globalWebSocket.onmessage = (event) => {
    //     try {
    //       const message: WebSocketMessage = JSON.parse(event.data);
    //       globalConnectionState.lastMessage = message;
    //       setLastMessage(message);

    //       if (message.type === 'pong') {
    //         // Handle pong response
    //         return;
    //       }

    //       if (message.type === 'tool_call_update' && message.conversation_id && message.tool_calls) {
    //         options.onToolCallUpdate?.(message.conversation_id, message.tool_calls);
    //       }
    //     } catch (err) {
    //       console.error('Error parsing WebSocket message:', err);
    //     }
    //   };

    //   globalWebSocket.onclose = (event) => {
    //     console.log('WebSocket disconnected:', event.code, event.reason);
    //     isConnecting = false;
    //     globalConnectionState.isConnected = false;
    //     setIsConnected(false);
    //     options.onDisconnect?.();

    //     // Clear ping interval
    //     if (pingIntervalRef.current) {
    //       clearInterval(pingIntervalRef.current);
    //       pingIntervalRef.current = null;
    //     }

    //     // Only attempt to reconnect if it wasn't a clean close and we haven't exceeded max attempts
    //     if (event.code !== 1000 && connectionAttempts < MAX_RECONNECTION_ATTEMPTS) {
    //       const delay = Math.min(5000 * connectionAttempts, 30000); // Exponential backoff, max 30s
    //       reconnectTimeoutRef.current = setTimeout(() => {
    //         console.log(`Attempting to reconnect WebSocket (attempt ${connectionAttempts + 1}/${MAX_RECONNECTION_ATTEMPTS})...`);
    //         connect();
    //       }, delay);
    //     } else if (connectionAttempts >= MAX_RECONNECTION_ATTEMPTS) {
    //       console.log('Max reconnection attempts reached, not attempting to reconnect');
    //     }
    //   };

    //   globalWebSocket.onerror = (event) => {
    //     console.error('WebSocket error:', event);
    //     isConnecting = false;
    //     const errorMessage = `WebSocket connection failed to ${WS_URL}/ws - check authentication`;
    //     console.error(errorMessage);
    //     globalConnectionState.error = errorMessage;
    //     setError(errorMessage);
    //     options.onError?.(event);
    //   };

    // } catch (err) {
    //   isConnecting = false;
    //   const errorMessage = `Failed to create WebSocket connection to ${WS_URL}/ws: ${err}`;
    //   console.error(errorMessage);
    //   globalConnectionState.error = errorMessage;
    //   setError(errorMessage);
    // }
  }, [WS_URL, options]);

  const disconnect = useCallback(() => {
    // WebSocket temporarily disabled
    console.log('WebSocket disconnect called but disabled');
    return;
    
    // if (reconnectTimeoutRef.current) {
    //   clearTimeout(reconnectTimeoutRef.current);
    //   reconnectTimeoutRef.current = null;
    // }

    // if (pingIntervalRef.current) {
    //   clearInterval(pingIntervalRef.current);
    //   pingIntervalRef.current = null;
    // }

    // if (globalWebSocket) {
    //   globalWebSocket.close(1000, 'User initiated disconnect');
    //   globalWebSocket = null;
    // }

    // isConnecting = false;
    // connectionAttempts = 0;
    // globalConnectionState.isConnected = false;
    // setIsConnected(false);
  }, []);

  const subscribeToConversation = useCallback((conversationId: string) => {
    // WebSocket temporarily disabled
    console.log('WebSocket subscribe called but disabled for conversation:', conversationId);
    return;
    
    // if (globalWebSocket?.readyState === WebSocket.OPEN) {
    //   globalWebSocket.send(JSON.stringify({
    //     type: 'subscribe_conversation',
    //     conversation_id: conversationId
    //   }));
    // }
  }, []);

  // Connect when user is available - TEMPORARILY DISABLED
  // useEffect(() => {
  //   let mounted = true;
    
  //   if (user?.id && mounted && !globalWebSocket) {
  //     connect();
  //   }

  //   return () => {
  //     mounted = false;
  //     // Only disconnect if this is the last component using the WebSocket
  //     // We'll let the global instance handle cleanup
  //   };
  // }, [user?.id, connect]);

  // Cleanup on unmount - TEMPORARILY DISABLED
  // useEffect(() => {
  //   return () => {
  //     disconnect();
  //   };
  // }, [disconnect]);

  return {
    isConnected,
    lastMessage,
    error,
    connect,
    disconnect,
    subscribeToConversation,
    sendMessage: (message: any) => {
      // WebSocket temporarily disabled
      console.log('WebSocket sendMessage called but disabled:', message);
      return;
      
      // if (globalWebSocket?.readyState === WebSocket.OPEN) {
      //   globalWebSocket.send(JSON.stringify(message));
      // }
    },
    reset: () => {
      // WebSocket temporarily disabled
      console.log('WebSocket reset called but disabled');
      return;
      
      // isConnecting = false;
      // connectionAttempts = 0;
      // if (reconnectTimeoutRef.current) {
      //   clearTimeout(reconnectTimeoutRef.current);
      //   reconnectTimeoutRef.current = null;
      // }
      // if (pingIntervalRef.current) {
      //   clearInterval(pingIntervalRef.current);
      //   pingIntervalRef.current = null;
      // }
      // if (globalWebSocket) {
      //   globalWebSocket.close(1000, 'Reset requested');
      //   globalWebSocket = null;
      // }
      // globalConnectionState.isConnected = false;
      // globalConnectionState.error = null;
      // globalConnectionState.lastMessage = null;
    }
  };
} 