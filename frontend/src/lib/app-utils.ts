
export function getInitials(name: string): string {
  if (!name) return 'U';
  
  const parts = name.trim().split(' ');
  if (parts.length === 1) {
    return parts[0].substring(0, 2).toUpperCase();
  }
  
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

export function parseEnvVars(envVarsString: string): Record<string, string> {
  if (!envVarsString || !envVarsString.trim()) {
    return {};
  }

  const envVars: Record<string, string> = {};
  const lines = envVarsString.split('\n');

  for (const line of lines) {
    const trimmedLine = line.trim();
    if (!trimmedLine || trimmedLine.startsWith('#')) {
      continue;
    }

    const equalIndex = trimmedLine.indexOf('=');
    if (equalIndex > 0) {
      const key = trimmedLine.substring(0, equalIndex).trim();
      const value = trimmedLine.substring(equalIndex + 1).trim();
      envVars[key] = value;
    }
  }

  return envVars;
}

/**
 * Convert env_vars from various formats to a Record<string, string>
 * Handles: string (KEY=value format), object, or null/undefined
 */
export function normalizeEnvVars(envVars: Record<string, string> | string | null | undefined): Record<string, string> {
  if (!envVars) {
    return {};
  }

  // If it's already an object, return it
  if (typeof envVars === 'object' && !Array.isArray(envVars)) {
    return envVars;
  }

  // If it's a string, parse it
  if (typeof envVars === 'string') {
    return parseEnvVars(envVars);
  }

  return {};
}

/**
 * Convert env_vars dict to array format for KeyValueInput component
 */
export function convertEnvVarsToArray(envVars: Record<string, string> | string | null | undefined): Array<{key: string, value: string}> {
  const normalized = normalizeEnvVars(envVars);
  return Object.entries(normalized).map(([key, value]) => ({
    key,
    value: String(value)
  }));
}

/**
 * Convert array format from KeyValueInput back to env dict
 */
export function convertArrayToEnv(pairs: Array<{key: string, value: string}>): Record<string, string> {
  const env: Record<string, string> = {};
  for (const pair of pairs) {
    if (pair.key.trim()) {
      env[pair.key.trim()] = pair.value.trim();
    }
  }
  return env;
} 