
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronDown, X, Zap, Code, Type, Settings } from 'lucide-react';

interface SmartTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
  environmentVariables?: Array<{ name: string; value: string; required: boolean }>;
  availableTools?: Array<{ name: string; description?: string; inputSchema?: any; server?: string }>;
  customPrompts?: Array<{ name: string; description?: string }>;
  customVariables?: Array<{ name: string; description?: string }>;
}

interface ToolParameterModalProps {
  tool: { name: string; description?: string; inputSchema?: any; server?: string };
  onClose: () => void;
  onInsert: (toolCall: string) => void;
}

interface ToolSelectionModalProps {
  tools: Array<{ name: string; description?: string; inputSchema?: any; server?: string }>;
  onClose: () => void;
  onSelectTool: (tool: { name: string; description?: string; inputSchema?: any; server?: string }) => void;
}

interface AutocompleteItem {
  type: 'env' | 'tool' | 'prompt' | 'variable';
  name: string;
  description?: string;
  server?: string;
  insertText: string;
  icon: React.ReactNode;
}

// Tool Parameter Modal Component
function ToolParameterModal({ tool, onClose, onInsert }: ToolParameterModalProps) {
  const [parameters, setParameters] = useState<Record<string, string>>({});
  
  const handleParameterChange = (key: string, value: string) => {
    setParameters(prev => ({ ...prev, [key]: value }));
  };
  
  const requiredParams = tool.inputSchema?.required || [];
  const allParams = tool.inputSchema?.properties ? Object.keys(tool.inputSchema.properties) : [];
  
  // Check if all required parameters are filled
  const areAllRequiredParamsFilled = () => {
    return requiredParams.every((param: string) => {
      const value = parameters[param];
      return value && value.trim() !== '';
    });
  };
  
  const handleInsert = () => {
    // Only insert if all required parameters are filled
    if (!areAllRequiredParamsFilled()) {
      return;
    }
    
    const paramString = Object.entries(parameters)
      .filter(([_, value]) => value.trim() !== '')
      .map(([key, value]) => `${key}="${value}"`)
      .join(', ');
    
    const toolCall = paramString 
      ? (tool.server ? `@${tool.server}:${tool.name}(${paramString})` : `@${tool.name}(${paramString})`)
      : (tool.server ? `@${tool.server}:${tool.name}()` : `@${tool.name}()`);
    onInsert(toolCall);
    onClose();
  };
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-md w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-orange-100 flex items-center justify-center">
              <Code className="h-5 w-5 text-orange-600" />
            </div>
            <div>
              <h3 className="font-semibold text-white">{tool.name}</h3>
              {tool.description && (
                <p className="text-sm text-gray-400">{tool.description}</p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <div className="space-y-4">
          {requiredParams.length > 0 && (
            <div className="bg-gray-800/30 rounded-lg p-3 border border-gray-700/50">
              <p className="text-sm text-gray-300">
                Required parameters: {requiredParams.filter((param: string) => parameters[param] && parameters[param].trim() !== '').length}/{requiredParams.length} filled
              </p>
            </div>
          )}
          {allParams.length > 0 ? (
            allParams.map(paramName => {
              const isRequired = requiredParams.includes(paramName);
              const paramSchema = tool.inputSchema.properties[paramName];
              
              return (
                <div key={paramName} className="space-y-2">
                  <label className="text-sm font-medium text-white">
                    {paramName} {isRequired && <span className="text-red-400">*</span>}
                  </label>
                  {paramSchema?.description && (
                    <p className="text-xs text-gray-400">{paramSchema.description}</p>
                  )}
                  <input
                    type="text"
                    value={parameters[paramName] || ''}
                    onChange={(e) => handleParameterChange(paramName, e.target.value)}
                    placeholder={paramSchema?.description || paramName}
                    className={`w-full p-2 bg-gray-800/50 border rounded text-white placeholder-gray-400 focus:ring-orange-500 focus:border-orange-500 ${
                      isRequired && (!parameters[paramName] || parameters[paramName].trim() === '')
                        ? 'border-red-500 focus:ring-red-500 focus:border-red-500'
                        : 'border-gray-700/50'
                    }`}
                  />
                  {isRequired && (!parameters[paramName] || parameters[paramName].trim() === '') && (
                    <p className="text-xs text-red-400">This parameter is required</p>
                  )}
                </div>
              );
            })
          ) : (
            <p className="text-gray-400 text-sm">No parameters required for this tool.</p>
          )}
        </div>
        
        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-gray-800/50 border border-gray-700/50 text-gray-300 rounded-lg hover:bg-gray-700/50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleInsert}
            disabled={!areAllRequiredParamsFilled()}
            className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
              areAllRequiredParamsFilled()
                ? 'bg-orange-600 text-white hover:bg-orange-700'
                : 'bg-gray-600 text-gray-400 cursor-not-allowed'
            }`}
          >
            Insert Tool Call
            {!areAllRequiredParamsFilled() && requiredParams.length > 0 && (
              <span className="text-xs block mt-1">Fill all required parameters</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// Tool Selection Modal Component
function ToolSelectionModal({ tools, onClose, onSelectTool }: ToolSelectionModalProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-md w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-orange-100 flex items-center justify-center">
              <Code className="h-5 w-5 text-orange-600" />
            </div>
            <h3 className="font-semibold text-white">Select Tool</h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <div className="space-y-2">
          {tools.map((tool) => (
            <button
              key={tool.name}
              onClick={() => onSelectTool(tool)}
              className="w-full text-left p-3 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:bg-gray-700/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Code className="h-4 w-4 text-orange-400" />
                <div className="flex-1">
                  <div className="font-medium text-white">{tool.name}</div>
                  {tool.description && (
                    <div className="text-sm text-gray-400">{tool.description}</div>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SmartTextEditor({
  value,
  onChange,
  placeholder = "Enter text...",
  rows = 8,
  className = "",
  environmentVariables = [
    { name: 'USER_ID', value: '12345', required: true },
    { name: 'API_KEY', value: 'secret', required: false },
    { name: 'DATABASE_URL', value: 'postgres://...', required: true }
  ],
  availableTools = [
    { 
      name: 'search', 
      description: 'Search for information',
      inputSchema: {
        properties: {
          query: { type: 'string', description: 'Search query' },
          limit: { type: 'number', description: 'Number of results' }
        },
        required: ['query']
      }
    },
    { 
      name: 'calculate', 
      description: 'Perform calculations',
      inputSchema: {
        properties: {
          expression: { type: 'string', description: 'Mathematical expression' }
        },
        required: ['expression']
      }
    },
    { 
      name: 'notify', 
      description: 'Send notification'
    }
  ],
  customPrompts = [
    { name: 'greeting', description: 'Standard greeting message' },
    { name: 'signature', description: 'Email signature' }
  ],
  customVariables = [
    { name: 'username', description: 'User name' },
    { name: 'email', description: 'User email' }
  ]
}: SmartTextEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const [showAutosuggestion, setShowAutosuggestion] = useState(false);
  const [autosuggestionItems, setAutosuggestionItems] = useState<AutocompleteItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [autosuggestionPosition, setAutosuggestionPosition] = useState({ top: 0, left: 0 });
  const [currentTrigger, setCurrentTrigger] = useState<string>('');
  const [triggerPosition, setTriggerPosition] = useState(0);
  const [showToolModal, setShowToolModal] = useState(false);
  const [showToolSelectionModal, setShowToolSelectionModal] = useState(false);
  const [selectedTool, setSelectedTool] = useState<{ name: string; description?: string; inputSchema?: any } | null>(null);

  // Generate autocomplete items
  const generateAutocompleteItems = useCallback((trigger: string, query: string): AutocompleteItem[] => {
    const items: AutocompleteItem[] = [];
    
    if (trigger === 'env(') {
      environmentVariables.forEach(env => {
        if (env.name.toLowerCase().includes(query.toLowerCase())) {
          items.push({
            type: 'env',
            name: env.name,
            description: env.required ? 'Required' : 'Optional',
            insertText: `env(${env.name})`,
            icon: <Zap className="h-3 w-3 text-yellow-400" />
          });
        }
      });
    } else if (trigger === '@') {
      availableTools.forEach(tool => {
        if (tool.name.toLowerCase().includes(query.toLowerCase())) {
          items.push({
            type: 'tool',
            name: tool.name,
            description: tool.description || 'Tool',
            server: tool.server,
            insertText: tool.server ? `@${tool.server}:${tool.name}()` : `@${tool.name}()`,
            icon: <Code className="h-3 w-3 text-orange-400" />
          });
        }
      });
    } else if (trigger === 'prompt(') {
      customPrompts.forEach(prompt => {
        if (prompt.name.toLowerCase().includes(query.toLowerCase())) {
          items.push({
            type: 'prompt',
            name: prompt.name,
            description: prompt.description || 'Custom prompt',
            insertText: `prompt(${prompt.name})`,
            icon: <Type className="h-3 w-3 text-purple-400" />
          });
        }
      });
    } else if (trigger === 'var(') {
      customVariables.forEach(variable => {
        if (variable.name.toLowerCase().includes(query.toLowerCase())) {
          items.push({
            type: 'variable',
            name: variable.name,
            description: variable.description || 'Variable',
            insertText: `var(${variable.name})`,
            icon: <Type className="h-3 w-3 text-blue-400" />
          });
        }
      });
    }
    
    return items;
  }, [environmentVariables, availableTools, customPrompts, customVariables]);

  // Calculate cursor position for autocomplete
  const calculateCursorPosition = useCallback(() => {
    if (!textareaRef.current) return { top: 0, left: 0 };
    
    const textarea = textareaRef.current;
    const { selectionStart } = textarea;
    const textBeforeCursor = value.slice(0, selectionStart);
    const lines = textBeforeCursor.split('\n');
    const currentLineIndex = lines.length - 1;
    const currentLineText = lines[currentLineIndex];
    
    // Get textarea dimensions and position
    const rect = textarea.getBoundingClientRect();
    const computedStyle = window.getComputedStyle(textarea);
    const paddingLeft = parseInt(computedStyle.paddingLeft) || 12;
    const paddingTop = parseInt(computedStyle.paddingTop) || 12;
    const fontSize = parseInt(computedStyle.fontSize) || 14;
    const lineHeight = parseFloat(computedStyle.lineHeight) || 1.6;
    const actualLineHeight = fontSize * lineHeight;
    
    // Create a temporary canvas to measure text width
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (context) {
      context.font = `${fontSize}px ${computedStyle.fontFamily}`;
      const textWidth = context.measureText(currentLineText).width;
      
      return {
        top: rect.top + paddingTop + (currentLineIndex * actualLineHeight) + actualLineHeight + 5,
        left: rect.left + paddingLeft + textWidth
      };
    }
    
    // Fallback to simple positioning
    return {
      top: rect.top + paddingTop + (currentLineIndex * actualLineHeight) + actualLineHeight + 5,
      left: rect.left + paddingLeft + (currentLineText.length * 8)
    };
  }, [value]);

  // Handle text input and autocomplete
  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    const cursorPos = e.target.selectionStart;
    
    onChange(newValue);
    
    // Check for autocomplete triggers
    const beforeCursor = newValue.substring(0, cursorPos);
    
    // Check for env( trigger (immediately when env( is typed)
    if (beforeCursor.endsWith('env(')) {
      const items = generateAutocompleteItems('env(', '');
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('env(');
        setTriggerPosition(beforeCursor.length - 4);
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    // Check for continued env( typing with query
    const envMatch = beforeCursor.match(/env\(([A-Z_][A-Z0-9_]*?)$/i);
    if (envMatch) {
      const query = envMatch[1] || '';
      const items = generateAutocompleteItems('env(', query);
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('env(');
        setTriggerPosition(beforeCursor.lastIndexOf('env('));
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    // Check for @ trigger (immediately when @ is typed)
    if (beforeCursor.endsWith('@')) {
      const items = generateAutocompleteItems('@', '');
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('@');
        setTriggerPosition(beforeCursor.length - 1);
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    // Check for continued @ typing with query
    const atMatch = beforeCursor.match(/@([a-zA-Z_][a-zA-Z0-9_]*)$/i);
    if (atMatch) {
      const query = atMatch[1] || '';
      const items = generateAutocompleteItems('@', query);
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('@');
        setTriggerPosition(beforeCursor.lastIndexOf('@'));
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    // Check for prompt( trigger (immediately when prompt( is typed)
    if (beforeCursor.endsWith('prompt(')) {
      const items = generateAutocompleteItems('prompt(', '');
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('prompt(');
        setTriggerPosition(beforeCursor.length - 7);
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    // Check for continued prompt( typing with query
    const promptMatch = beforeCursor.match(/prompt\(([a-zA-Z_][a-zA-Z0-9_]*)$/i);
    if (promptMatch) {
      const query = promptMatch[1] || '';
      const items = generateAutocompleteItems('prompt(', query);
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('prompt(');
        setTriggerPosition(beforeCursor.lastIndexOf('prompt('));
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    // Check for var( trigger (immediately when var( is typed)
    if (beforeCursor.endsWith('var(')) {
      const items = generateAutocompleteItems('var(', '');
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('var(');
        setTriggerPosition(beforeCursor.length - 4);
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    // Check for continued var( typing with query
    const varMatch = beforeCursor.match(/var\(([a-zA-Z_][a-zA-Z0-9_]*)$/i);
    if (varMatch) {
      const query = varMatch[1] || '';
      const items = generateAutocompleteItems('var(', query);
      if (items.length > 0) {
        setAutosuggestionItems(items);
        setSelectedIndex(0);
        setCurrentTrigger('var(');
        setTriggerPosition(beforeCursor.lastIndexOf('var('));
        setShowAutosuggestion(true);
        const pos = calculateCursorPosition();
        setAutosuggestionPosition(pos);
        return;
      }
    }
    
    setShowAutosuggestion(false);
  }, [generateAutocompleteItems, onChange, calculateCursorPosition]);

  // Handle tool insertion from modal
  const handleToolInsert = useCallback((toolCall: string) => {
    if (!textareaRef.current) return;
    
    const beforeTrigger = value.substring(0, triggerPosition);
    const afterCursor = value.substring(textareaRef.current.selectionStart);
    
    const newValue = beforeTrigger + toolCall + afterCursor;
    const newCursorPos = beforeTrigger.length + toolCall.length;
    
    onChange(newValue);
    
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
        textareaRef.current.focus();
      }
    }, 0);
  }, [value, triggerPosition, onChange]);

  // Handle autocomplete selection
  const handleAutocompleteSelect = useCallback((item: AutocompleteItem) => {
    if (!textareaRef.current) return;
    
    if (item.type === 'tool') {
      const tool = availableTools.find(t => t.name === item.name);
      if (tool) {
        setSelectedTool(tool);
        setShowToolModal(true);
        setShowAutosuggestion(false);
      }
      return;
    }
    
    const beforeTrigger = value.substring(0, triggerPosition);
    const afterCursor = value.substring(textareaRef.current.selectionStart);
    
    const newValue = beforeTrigger + item.insertText + afterCursor;
    const newCursorPos = beforeTrigger.length + item.insertText.length;
    
    onChange(newValue);
    setShowAutosuggestion(false);
    
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
        textareaRef.current.focus();
      }
    }, 0);
  }, [value, triggerPosition, availableTools, onChange]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (showAutosuggestion && autosuggestionItems.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % autosuggestionItems.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + autosuggestionItems.length) % autosuggestionItems.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        handleAutocompleteSelect(autosuggestionItems[selectedIndex]);
      } else if (e.key === 'Escape') {
        setShowAutosuggestion(false);
      }
    }
  }, [showAutosuggestion, autosuggestionItems, selectedIndex, handleAutocompleteSelect]);

  // Highlight syntax
  const highlightSyntax = useCallback((text: string) => {
    let highlighted = text;
    
    // Environment variables: env(VAR_NAME)
    highlighted = highlighted.replace(/(env\([A-Z_][A-Z0-9_]*?\))/gi, '<span style="color: #fbbf24; font-weight: 600;">$1</span>');
    
    // Tool calls: @server:tool_name(params) or @tool_name(params)
    highlighted = highlighted.replace(/(@[a-zA-Z_][a-zA-Z0-9_]*:[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)|@[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\))/gi, '<span style="color: #fb923c; font-weight: 600;">$1</span>');
    
    // Prompts: prompt(prompt_name)
    highlighted = highlighted.replace(/(prompt\([a-zA-Z_][a-zA-Z0-9_]*?\))/gi, '<span style="color: #c084fc; font-weight: 600;">$1</span>');
    
    // Variables: var(variable_name)
    highlighted = highlighted.replace(/(var\([a-zA-Z_][a-zA-Z0-9_]*?\))/gi, '<span style="color: #60a5fa; font-weight: 600;">$1</span>');
    
    return highlighted;
  }, []);

  // Update overlay scroll position
  useEffect(() => {
    if (overlayRef.current && textareaRef.current) {
      overlayRef.current.scrollTop = textareaRef.current.scrollTop;
      overlayRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, [value]);

  // Refresh autosuggestion when environment variables change
  useEffect(() => {
    if (showAutosuggestion && currentTrigger === 'env(') {
      const beforeCursor = value.substring(0, triggerPosition);
      const query = beforeCursor.substring(triggerPosition + 4); // +4 for 'env('
      const items = generateAutocompleteItems('env(', query);
      setAutosuggestionItems(items);
      setSelectedIndex(0);
    }
  }, [environmentVariables, showAutosuggestion, currentTrigger, triggerPosition, value, generateAutocompleteItems]);

  const handleScroll = () => {
    if (overlayRef.current && textareaRef.current) {
      overlayRef.current.scrollTop = textareaRef.current.scrollTop;
      overlayRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  };

  return (
    <div className={`relative ${className}`}>
      <div className="relative">
        {/* Syntax highlighting overlay */}
        <div 
          ref={overlayRef}
          className="absolute inset-0 pointer-events-none font-mono text-sm whitespace-pre-wrap rounded-lg overflow-hidden border border-transparent"
          style={{ 
            padding: '12px 80px 12px 12px', // Match textarea padding exactly
            lineHeight: '1.6',
            backgroundColor: 'rgba(17, 24, 39, 0.5)',
            color: '#9ca3af',
            zIndex: 1,
            fontSize: '14px',
            fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
            wordWrap: 'break-word',
            overflowWrap: 'break-word',
            whiteSpace: 'pre-wrap'
          }}
          dangerouslySetInnerHTML={{ 
            __html: highlightSyntax(value)
          }}
        />
        
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onScroll={handleScroll}
          onBlur={() => setTimeout(() => setShowAutosuggestion(false), 200)}
          placeholder={placeholder}
          rows={rows}
          className="w-full bg-transparent border border-gray-700/50 placeholder-gray-400 rounded-lg resize-none font-mono text-sm relative"
          style={{ 
            padding: '12px 80px 12px 12px', // Exact same padding as overlay
            lineHeight: '1.6',
            color: 'transparent',
            caretColor: 'white',
            zIndex: 2,
            fontSize: '14px',
            fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
            wordWrap: 'break-word',
            overflowWrap: 'break-word',
            whiteSpace: 'pre-wrap',
            outline: 'none',
            boxShadow: 'none'
          }}
          onFocus={(e) => e.target.style.outline = 'none'}
        />
      </div>
      
      {/* Quick insert buttons */}
      <div className="absolute top-2 right-2 flex gap-1">
        <button
          type="button"
          onClick={() => {
            const newValue = value + 'env(ENV_VAR)';
            onChange(newValue);
            setTimeout(() => {
              if (textareaRef.current) {
                const newPos = newValue.length - 9;
                textareaRef.current.setSelectionRange(newPos, newPos + 7);
                textareaRef.current.focus();
              }
            }, 0);
          }}
          className="h-6 w-6 p-0 text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/20 rounded transition-colors flex items-center justify-center"
          title="Insert environment variable"
        >
          <Zap className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={() => {
            if (availableTools.length > 0) {
              setShowToolSelectionModal(true);
            }
          }}
          className="h-6 w-6 p-0 text-orange-400 hover:text-orange-300 hover:bg-orange-500/20 rounded transition-colors flex items-center justify-center"
          title="Insert tool call"
        >
          <Code className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={() => {
            const newValue = value + 'prompt(prompt_name)';
            onChange(newValue);
            setTimeout(() => {
              if (textareaRef.current) {
                const newPos = newValue.length - 12;
                textareaRef.current.setSelectionRange(newPos, newPos + 10);
                textareaRef.current.focus();
              }
            }, 0);
          }}
          className="h-6 w-6 p-0 text-purple-400 hover:text-purple-300 hover:bg-purple-500/20 rounded transition-colors flex items-center justify-center"
          title="Insert prompt"
        >
          <Type className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={() => {
            const newValue = value + 'var(variable_name)';
            onChange(newValue);
            setTimeout(() => {
              if (textareaRef.current) {
                const newPos = newValue.length - 13;
                textareaRef.current.setSelectionRange(newPos, newPos + 11);
                textareaRef.current.focus();
              }
            }, 0);
          }}
          className="h-6 w-6 p-0 text-blue-400 hover:text-blue-300 hover:bg-blue-500/20 rounded transition-colors flex items-center justify-center"
          title="Insert variable"
        >
          <Type className="h-3 w-3" />
        </button>
      </div>

      {/* Autocomplete dropdown */}
      {showAutosuggestion && autosuggestionItems.length > 0 && (
        <div
          className="absolute z-50 bg-gray-900 border border-gray-700 rounded-lg shadow-xl max-h-60 overflow-y-auto min-w-64 max-w-sm"
          style={{
            bottom: '0',
            right: '0',
            transform: 'translateY(100%)',
            marginBottom: '8px'
          }}
        >
          {autosuggestionItems.map((item, index) => (
            <div
              key={`${item.type}-${item.name}`}
              className={`flex items-center gap-3 p-3 cursor-pointer transition-colors ${
                index === selectedIndex 
                  ? "bg-violet-500/20 text-violet-400" 
                  : "text-gray-300 hover:bg-gray-800/50"
              }`}
              onClick={() => handleAutocompleteSelect(item)}
            >
              {item.icon}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{item.name}</div>
                <div className="flex items-center gap-2">
                  {item.description && (
                    <div className="text-xs text-gray-400 truncate">{item.description}</div>
                  )}
                  {item.server && (
                    <div className="text-xs text-blue-400 bg-blue-500/20 px-1.5 py-0.5 rounded">
                      {item.server}
                    </div>
                  )}
                </div>
              </div>
              <div className="text-xs text-gray-500 font-mono truncate">{item.insertText}</div>
            </div>
          ))}
        </div>
      )}
      
      {/* Tool Parameter Modal */}
      {showToolModal && selectedTool && (
        <ToolParameterModal
          tool={selectedTool}
          onClose={() => {
            setShowToolModal(false);
            setSelectedTool(null);
          }}
          onInsert={handleToolInsert}
        />
      )}
      
      {/* Tool Selection Modal */}
      {showToolSelectionModal && (
        <ToolSelectionModal
          tools={availableTools}
          onClose={() => setShowToolSelectionModal(false)}
          onSelectTool={(tool) => {
            setSelectedTool(tool);
            setShowToolSelectionModal(false);
            setShowToolModal(true);
          }}
        />
      )}
    </div>
  );
}

// Demo component to show usage
export default function Demo() {
  const [editorValue, setEditorValue] = useState('Try typing env(, @, prompt(, or var( to see autosuggestion in action!\n\nExamples:\n- env(USER_ID) (environment variable)\n- @search(query="test") (tool call)\n- prompt(greeting) (custom prompt)\n- var(username) (variable)');

  return (
    <div className="min-h-screen bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-6">Smart Text Editor</h1>
        <SmartTextEditor
          value={editorValue}
          onChange={setEditorValue}
          placeholder="Start typing and use $$, @, or {{ for autosuggestion..."
          rows={12}
          className="mb-4"
        />
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-2">Features:</h3>
          <ul className="text-gray-300 space-y-1">
            <li>• Type <code className="bg-gray-700 px-1 rounded">env(</code> for environment variables</li>
            <li>• Type <code className="bg-gray-700 px-1 rounded">@</code> for tool calls with parameter modals</li>
            <li>• Type <code className="bg-gray-700 px-1 rounded">prompt(</code> for custom prompts</li>
            <li>• Type <code className="bg-gray-700 px-1 rounded">var(</code> for variables</li>
            <li>• Syntax highlighting for all four types</li>
            <li>• Keyboard navigation (arrows, enter, escape)</li>
            <li>• Quick insert buttons on the right</li>
          </ul>
        </div>
      </div>
    </div>
  );
}