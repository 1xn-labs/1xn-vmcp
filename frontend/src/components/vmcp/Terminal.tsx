// components/vmcp/Terminal.tsx

import { useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';

interface TerminalProps {
  vmcpId: string;
  className?: string;
}

export default function Terminal({ vmcpId, className = '' }: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm
    const xterm = new XTerm({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#aeafad',
      },
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    xterm.loadAddon(fitAddon);
    xterm.loadAddon(webLinksAddon);
    xterm.open(terminalRef.current);

    xtermRef.current = xterm;
    fitAddonRef.current = fitAddon;

    // Fit terminal to container
    fitAddon.fit();

    // Connect WebSocket
    const connectWebSocket = () => {
      // Clear any existing reconnect timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        xterm.writeln('\r\n\x1b[31mMax reconnection attempts reached. Please refresh the page.\x1b[0m');
        return;
      }

      const baseUrl = import.meta.env.VITE_BACKEND_URL?.replace(/\/api\/?$/, '') || 'http://localhost:8000';
      const wsUrl = baseUrl.replace('http', 'ws');
      const token = localStorage.getItem('access_token') || (import.meta.env.VITE_VMCP_OSS_BUILD === 'true' ? 'local-token' : undefined);
      
      const url = `${wsUrl}/api/vmcps/${encodeURIComponent(vmcpId)}/sandbox/terminal?token=${encodeURIComponent(token || '')}`;
      
      // Track if this is a reconnection attempt
      const wasReconnecting = reconnectAttemptsRef.current > 0;
      
      try {
        const ws = new WebSocket(url);

        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
          setConnected(true);
          reconnectAttemptsRef.current = 0; // Reset on successful connection
          
          // Show appropriate message based on whether we're reconnecting
          if (wasReconnecting) {
            xterm.writeln('\r\n\x1b[32m✓ Reconnected to existing terminal session\x1b[0m');
            xterm.writeln('\x1b[33m  (Your session state has been preserved)\x1b[0m');
          } else {
            xterm.writeln('\r\n\x1b[32m✓ Terminal connected to sandbox environment\x1b[0m');
          }
          xterm.writeln('');
          setIsReconnecting(false);
        };

        ws.onmessage = (event) => {
          if (event.data instanceof ArrayBuffer) {
            const data = new Uint8Array(event.data);
            xterm.write(data);
          } else if (typeof event.data === 'string') {
            try {
              const message = JSON.parse(event.data);
              if (message.type === 'error') {
                xterm.writeln(`\r\n\x1b[31mError: ${message.message}\x1b[0m`);
              }
            } catch {
              // Not JSON, treat as text
              xterm.write(event.data);
            }
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          if (!connected) {
            xterm.writeln('\r\n\x1b[31mConnection error. Attempting to reconnect...\x1b[0m');
          }
        };

        ws.onclose = (event) => {
          setConnected(false);
          if (event.code !== 1000) {
            // Not a normal closure, attempt to reconnect
            reconnectAttemptsRef.current++;
            if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
              setIsReconnecting(true); // Mark that we're reconnecting
              xterm.writeln(`\r\n\x1b[33mConnection closed. Reconnecting to existing session... (${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})\x1b[0m`);
              reconnectTimeoutRef.current = setTimeout(connectWebSocket, 2000);
            } else {
              xterm.writeln('\r\n\x1b[31mMax reconnection attempts reached. Please refresh the page.\x1b[0m');
            }
          }
        };

        // Handle terminal input
        xterm.onData((data) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(data);
          }
        });

        // Handle terminal resize
        const handleResize = () => {
          if (fitAddonRef.current && ws && ws.readyState === WebSocket.OPEN) {
            fitAddonRef.current.fit();
            const dimensions = fitAddonRef.current.proposeDimensions();
            if (dimensions) {
              ws.send(JSON.stringify({
                type: 'resize',
                rows: dimensions.rows,
                cols: dimensions.cols,
              }));
            }
          }
        };

        window.addEventListener('resize', handleResize);
        wsRef.current = ws;

        // Send initial resize
        setTimeout(() => {
          handleResize();
        }, 100);

        return () => {
          window.removeEventListener('resize', handleResize);
        };
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        xterm.writeln(`\r\n\x1b[31mFailed to connect: ${error}\x1b[0m`);
      }
    };

    const cleanup = connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      xterm.dispose();
      if (cleanup) cleanup();
    };
  }, [vmcpId]);

  // Handle container resize
  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();
        // Notify backend of resize
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const dimensions = fitAddonRef.current.proposeDimensions();
          if (dimensions) {
            wsRef.current.send(JSON.stringify({
              type: 'resize',
              rows: dimensions.rows,
              cols: dimensions.cols,
            }));
          }
        }
      }
    });

    if (terminalRef.current) {
      resizeObserver.observe(terminalRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <div className={`h-full w-full relative ${className}`}>
      <div
        ref={terminalRef}
        className="h-full w-full"
        style={{ padding: '8px' }}
      />
      {!connected && (
        <div className="absolute top-2 right-2 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-yellow-500 animate-pulse"></div>
          {isReconnecting ? 'Reconnecting...' : 'Connecting...'}
        </div>
      )}
      {connected && (
        <div className="absolute top-2 right-2 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500"></div>
          <span>Session active</span>
        </div>
      )}
    </div>
  );
}

