/**
 * Extracts the base URL from a full URL for favicon fetching
 * @param url - The full URL
 * @returns The base URL (e.g., "https://github.com" from "https://github.com/api/v1")
 */
export function getBaseUrl(url: string): string | null {
  try {
    const urlObj = new URL(url);
    return `${urlObj.protocol}//${urlObj.hostname}`;
  } catch (error) {
    console.error('Invalid URL:', url, error);
    return null;
  }
}

/**
 * Gets the favicon URL for a given base URL
 * @param baseUrl - The base URL (e.g., "https://github.com")
 * @returns The favicon URL
 */
export function getFaviconUrl(baseUrl: string): string {
  return `${baseUrl}/favicon.ico`;
}
