import { useState, useEffect, useRef, useCallback } from 'react';

const WS_BASE_URL = process.env.REACT_APP_API_URL?.replace('http', 'ws') || 'ws://127.0.0.1:8000/api';

/**
 * Custom hook for WebSocket connection
 * Handles real-time chat communication with the backend
 */
export const useWebSocket = (sessionId) => {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnecting = useRef(false); // Prevent duplicate connections
  const isMounted = useRef(true); // Track if component is mounted
  const isConnectedRef = useRef(false); // Mirror isConnected to avoid adding it to deps

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!sessionId) {
      console.warn('No session ID provided for WebSocket');
      return;
    }

    // Prevent multiple simultaneous connection attempts
    if (isConnecting.current || (ws.current && ws.current.readyState === WebSocket.OPEN)) {
      console.log('Already connecting or connected, skipping...');
      return;
    }

    isConnecting.current = true;

    try {
      const wsUrl = `${WS_BASE_URL}/ws/chat/${sessionId}`;
      console.log('Connecting to WebSocket:', wsUrl);
      
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        isConnecting.current = false;
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message received:', data);
          
          setMessages((prev) => [...prev, data]);
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.current.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('WebSocket connection error');
        isConnecting.current = false;
      };

      ws.current.onclose = () => {
        console.log('[WebSocket] onclose fired', { 
          isMounted: isMounted.current,
          wasConnected: isConnectedRef.current 
        });
        setIsConnected(false);
        isConnecting.current = false;
        
        // Disable auto-reconnect to prevent infinite loops
        // User can manually reconnect if needed
        console.log('WebSocket closed. Connection will not auto-reconnect.');
        setError('Connection lost. Please refresh the page to reconnect.');
      };
    } catch (err) {
      console.error('Error creating WebSocket:', err);
      setError('Failed to establish WebSocket connection');
      isConnecting.current = false;
    }
  }, [sessionId]);

  // Send message through WebSocket
  const sendMessage = useCallback((type, data) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      const message = {
        type,
        ...data,
        timestamp: new Date().toISOString(),
      };
      
      console.log('Sending WebSocket message:', message);
      ws.current.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
      setError('Not connected to server');
    }
  }, []);

  // Send candidate answer
  const sendAnswer = useCallback((message) => {
    sendMessage('answer', { message });
  }, [sendMessage]);

  // Send ping (heartbeat)
  const sendPing = useCallback(() => {
    sendMessage('ping', {});
  }, [sendMessage]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    console.log('[WebSocket] disconnect() called');
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
    }
    
    if (ws.current) {
      console.log('[WebSocket] Closing connection...');
      ws.current.close();
      ws.current = null;
    }
    
    setIsConnected(false);
    isMounted.current = false;
  }, []);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    console.log('[WebSocket] useEffect mount', { sessionId, isMounted: isMounted.current });
    isMounted.current = true;
    
    if (sessionId) {
      connect();
    }

    return () => {
      console.log('[WebSocket] useEffect cleanup (unmounting)');
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]); // Only reconnect when sessionId changes

  // Heartbeat to keep connection alive
  useEffect(() => {
    if (!isConnected) return;

    const heartbeatInterval = setInterval(() => {
      sendPing();
    }, 30000); // Send ping every 30 seconds

    return () => {
      clearInterval(heartbeatInterval);
    };
  }, [isConnected, sendPing]);

  // Keep isConnectedRef in sync without forcing connect() to re-create
  useEffect(() => {
    isConnectedRef.current = isConnected;
  }, [isConnected]);

  return {
    isConnected,
    messages,
    error,
    sendAnswer,
    sendMessage,
    disconnect,
    reconnect: connect,
  };
};

export default useWebSocket;
