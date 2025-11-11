
import React from 'react';
// import { useWebSocket } from '@/hooks/useWebSocket';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface WebSocketStatusProps {
  className?: string;
  showText?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function WebSocketStatus({ 
  className = '', 
  showText = true, 
  size = 'sm' 
}: WebSocketStatusProps) {
  // WebSocket temporarily disabled
  // const { isConnected, error, reset } = useWebSocket();
  const isConnected = false;
  const error = 'WebSocket disabled';
  const reset = () => console.log('WebSocket reset called but disabled');

  const sizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5'
  };

  const textSizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base'
  };

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      {isConnected ? (
        <>
          <Wifi className={`${sizeClasses[size]} text-green-500`} />
          {showText && (
            <span className={`${textSizeClasses[size]} text-green-500`}>
              Live
            </span>
          )}
        </>
      ) : (
        <>
          <WifiOff className={`${sizeClasses[size]} text-red-500`} />
          {showText && (
            <span className={`${textSizeClasses[size]} text-red-500`}>
              {error ? 'Error' : 'Offline'}
            </span>
          )}
        </>
      )}
      
      {/* Reset button for debugging */}
      {error && (
        <button
          onClick={reset}
          className="ml-2 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
          title="Reset WebSocket connection"
        >
          <RefreshCw className={`${sizeClasses[size]} text-gray-500`} />
        </button>
      )}
    </div>
  );
} 