export type ModelProvider = 'anthropic' | 'openai' | 'gemini';

export interface ModelOption {
  id: string;
  name: string;
  provider: ModelProvider;
  description?: string;
  tags?: string[];
}

export const modelCatalog: Record<ModelProvider, ModelOption[]> = {
  anthropic: [
    { id: 'claude-3-7-sonnet-latest', name: 'Claude 3.7 Sonnet (latest)', provider: 'anthropic', tags: ['balanced'] },
    { id: 'claude-3-5-sonnet-latest', name: 'Claude 3.5 Sonnet (latest)', provider: 'anthropic', tags: ['balanced'] },
    { id: 'claude-3-5-haiku-latest', name: 'Claude 3.5 Haiku (latest)', provider: 'anthropic', tags: ['fast', 'low-cost'] },
    { id: 'claude-3-opus-latest', name: 'Claude 3 Opus (latest)', provider: 'anthropic', tags: ['advanced'] },
  ],
  openai: [
    { id: 'gpt-5-mini-2025-08-07', name: 'GPT-5 mini', provider: 'openai', tags: ['latest'] },
    { id: 'gpt-4.1', name: 'GPT-4.1', provider: 'openai', tags: ['vision'] },
    { id: 'gpt-4.1-mini', name: 'GPT-4.1 mini', provider: 'openai', tags: ['fast', 'low-cost'] },
    { id: 'gpt-4.1-nano', name: 'GPT-4.1 nano', provider: 'openai', tags: ['edge'] },
    { id: 'gpt-4.5-preview', name: 'GPT-4.5 (preview)', provider: 'openai', tags: ['preview', 'advanced'] },
    { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai', tags: ['vision', 'audio'] },
    { id: 'gpt-4o-mini', name: 'GPT-4o mini', provider: 'openai', tags: ['fast', 'low-cost'] },
    { id: 'o1', name: 'o1', provider: 'openai', tags: ['reasoning'] },
    { id: 'o1-pro', name: 'o1 pro', provider: 'openai', tags: ['reasoning', 'advanced'] },
    { id: 'o3-pro', name: 'o3 pro', provider: 'openai', tags: ['reasoning', 'advanced'] },
    { id: 'o3', name: 'o3', provider: 'openai', tags: ['reasoning'] },
    { id: 'o4-mini', name: 'o4 mini', provider: 'openai', tags: ['balanced'] },
    { id: 'o3-mini', name: 'o3 mini', provider: 'openai', tags: ['reasoning', 'fast'] },
    { id: 'o1-mini', name: 'o1 mini', provider: 'openai', tags: ['reasoning', 'fast'] },
    { id: 'codex-mini-latest', name: 'Codex mini (latest)', provider: 'openai', tags: ['code'] },
    { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', provider: 'openai', tags: ['legacy'] },
    { id: 'gpt-3.5-turbo-0125', name: 'GPT-3.5 Turbo (0125)', provider: 'openai', tags: ['legacy'] },
    { id: 'gpt-4', name: 'GPT-4', provider: 'openai', tags: ['legacy', 'advanced'] },
    { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', provider: 'openai', tags: ['legacy'] },
  ],
  gemini: [
    { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', provider: 'gemini', tags: ['large', 'advanced'] },
    { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', provider: 'gemini', tags: ['medium', 'fast'] },
    { id: 'gemini-2.5-flash-lite', name: 'Gemini 2.5 Flash Lite', provider: 'gemini', tags: ['fast', 'low-cost'] },
    { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', provider: 'gemini', tags: ['fast', 'vision'] },
    { id: 'gemini-2.0-flash-lite', name: 'Gemini 2.0 Flash Lite', provider: 'gemini', tags: ['fast', 'low-cost'] },
    { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', provider: 'gemini', tags: ['fast', 'low-cost'] },
    { id: 'gemini-1.5-flash-8b', name: 'Gemini 1.5 Flash 8B', provider: 'gemini', tags: ['fast', 'low-cost'] },
    { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'gemini', tags: ['long-context', 'vision'] },
    { id: 'gemma-3', name: 'Gemma 3', provider: 'gemini', tags: ['free'] },
    { id: 'gemma-3n', name: 'Gemma 3n', provider: 'gemini', tags: ['free'] },
  ],
};

export function flattenCatalog(): ModelOption[] {
  return [
    ...modelCatalog.anthropic,
    ...modelCatalog.openai,
    ...modelCatalog.gemini,
  ];
}


