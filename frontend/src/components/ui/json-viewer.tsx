
import React, { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface JsonViewerProps {
  data: any;
  defaultExpanded?: boolean;
  className?: string;
  maxDepth?: number;
}

export function JsonViewer({ 
  data, 
  defaultExpanded = false, 
  className = '',
  maxDepth = 3 
}: JsonViewerProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const toggleNode = (path: string) => {
    setExpandedNodes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return newSet;
    });
  };

  const renderValue = (value: any, path: string, depth: number = 0): React.ReactNode => {
    if (value === null) {
      return <span className="text-gray-500">null</span>;
    }
    
    if (value === undefined) {
      return <span className="text-gray-500">undefined</span>;
    }
    
    if (typeof value === 'string') {
      return <span className="text-green-600">"{value}"</span>;
    }
    
    if (typeof value === 'number') {
      return <span className="text-blue-600">{value}</span>;
    }
    
    if (typeof value === 'boolean') {
      return <span className="text-purple-600">{value.toString()}</span>;
    }
    
    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <span className="text-gray-500">[]</span>;
      }
      
      const isExpanded = expandedNodes.has(path) || (defaultExpanded && depth < maxDepth);
      
      return (
        <div>
          <button
            onClick={() => toggleNode(path)}
            className="flex items-center gap-1 text-gray-700 hover:text-gray-900"
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            <span className="text-gray-600">[</span>
            {!isExpanded && <span className="text-gray-500">...</span>}
            <span className="text-gray-600">]</span>
          </button>
          
          {isExpanded && (
            <div className="ml-4 mt-1">
              {value.map((item, index) => (
                <div key={index} className="flex">
                  <span className="text-gray-500 mr-2">{index}:</span>
                  {renderValue(item, `${path}[${index}]`, depth + 1)}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
    
    if (typeof value === 'object') {
      const keys = Object.keys(value);
      
      if (keys.length === 0) {
        return <span className="text-gray-500">{'{}'}</span>;
      }
      
      const isExpanded = expandedNodes.has(path) || (defaultExpanded && depth < maxDepth);
      
      return (
        <div>
          <button
            onClick={() => toggleNode(path)}
            className="flex items-center gap-1 text-gray-700 hover:text-gray-900"
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            <span className="text-gray-600">{'{'}</span>
            {!isExpanded && <span className="text-gray-500">...</span>}
            <span className="text-gray-600">{'}'}</span>
          </button>
          
          {isExpanded && (
            <div className="ml-4 mt-1">
              {keys.map(key => (
                <div key={key} className="flex">
                  <span className="text-blue-600 mr-2">"{key}":</span>
                  {renderValue(value[key], `${path}.${key}`, depth + 1)}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
    
    return <span className="text-gray-700">{String(value)}</span>;
  };

  return (
    <div className={cn('font-mono text-sm', className)}>
      {renderValue(data, 'root')}
    </div>
  );
} 