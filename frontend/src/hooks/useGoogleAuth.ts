import { useState } from 'react';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

export function useGoogleAuth() {
  const [loading, setLoading] = useState(false);

  const signInWithGoogle = async (isRegister: boolean = false, returnUrl?: string, username?: string, oauthParams?: URLSearchParams) => {
    setLoading(true);
    try {
      // Get current web client URL with base path
      // Frontend is served at /app, so login page is at /app/login
      const webClientUrl = returnUrl || `${window.location.origin}/app/login`;
      
      // Determine auth mode based on isRegister parameter
      const authMode = isRegister ? 'signup' : 'signin';
      
      const result = await apiClient.getOAuthUrl('google', webClientUrl, authMode, username, oauthParams);
      if (result.success && result.data) {
        // Store the state parameter for CSRF protection
        localStorage.setItem('oauth_state', result.data.state);
        localStorage.setItem('oauth_mode', isRegister ? 'register' : 'login');
      
        
        // Redirect to Google OAuth
        window.location.href = result.data.auth_url;
      } else {
        throw new Error(result.error || 'Failed to get OAuth URL');
      }
    } catch (error) {
      setLoading(false);
      throw error;
    }
  };

  return {
    signInWithGoogle,
    loading,
  };
} 