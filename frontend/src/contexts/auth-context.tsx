import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { apiClient } from '@/api/client';
import type { User, LoginRequest } from '@/lib/new-api';

const authDisabled = import.meta.env.VITE_VMCP_OSS_BUILD === 'true'

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  handleOAuthCallback: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  // For OSS build with auth disabled, provide a mock auth context early
  if(authDisabled) {
    console.log("[AuthContext] Auth is disabled for OSS build - skipping all auth logic");

    // Set a mock access token in localStorage for OSS build
    if (!localStorage.getItem('access_token')) {
      localStorage.setItem('access_token', 'local-token');
      console.log("[AuthContext] Set local-token for OSS no-auth mode");
    }

    const mockUser: User = {
      id: 'local-user',
      email: 'user@local.vmcp',
      username: 'local-user',
      first_name: 'Local',
      last_name: 'User',
      full_name: 'Local User',
      is_active: true,
      is_verified: true,
      last_login: new Date().toISOString(),
      created_at: new Date().toISOString(),
    };

    const mockValue: AuthContextType = {
      user: mockUser,
      loading: false,
      error: null,
      isAuthenticated: true,
      login: async () => ({ success: false, error: 'Auth disabled in OSS build' }),
      logout: async () => {},
      refreshUser: async () => {},
      handleOAuthCallback: async () => {},
    };

    return (
      <AuthContext.Provider value={mockValue}>
        {children}
      </AuthContext.Provider>
    );
  }

  const router = useRouter();
  const [searchParams] = useSearchParams();
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
    isAuthenticated: false,
  });
  
  // Use ref to track if OAuth callback has been processed
  const oauthProcessedRef = useRef(false);
  const isRedirectingRef = useRef(false);

  // Handle OAuth callback
  const handleOAuthCallback = useCallback(async () => {
    // Prevent processing OAuth callback multiple times using ref
    if (oauthProcessedRef.current || isRedirectingRef.current) {
      return;
    }

    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    const userId = searchParams.get('user_id');
    const userEmail = searchParams.get('user_email');
    const userName = searchParams.get('user_name');
    const userPhoto = searchParams.get('user_photo');

    if (accessToken && refreshToken && userId && userEmail) {
      try {
        // Mark as processed immediately using ref (not state)
        oauthProcessedRef.current = true;
        isRedirectingRef.current = true;

        console.log('OAuth callback processing - storing tokens and user data');

        // Store tokens
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);

        // Create user object from OAuth data
        const user: User = {
          id: userId,
          email: decodeURIComponent(userEmail),
          username: undefined,
          first_name: userName ? decodeURIComponent(userName).split(' ')[0] : '',
          last_name: userName ? decodeURIComponent(userName).split(' ').slice(1).join(' ') : '',
          full_name: userName ? decodeURIComponent(userName) : '',
          is_active: true,
          is_verified: true,
          last_login: new Date().toISOString(),
          created_at: new Date().toISOString(),
          photo_url: userPhoto ? decodeURIComponent(userPhoto) : undefined,
        };

        // Store user data
        localStorage.setItem('user', JSON.stringify(user));

        // Update state
        setAuthState({
          user,
          loading: false,
          error: null,
          isAuthenticated: true,
        });

        console.log('OAuth callback successful - redirecting to /vmcp');
        
        // Redirect immediately without setTimeout
        router.replace('/vmcp');

      } catch (error) {
        console.error('OAuth callback error:', error);
        oauthProcessedRef.current = false;
        isRedirectingRef.current = false;
        setAuthState({
          user: null,
          loading: false,
          error: 'Failed to process OAuth callback',
          isAuthenticated: false,
        });
      }
    }
  }, [searchParams, router]);

  // Check authentication status
  const checkAuth = useCallback(async () => {
    console.log('🔍 Checking authentication status...');
    const accessToken = localStorage.getItem('access_token');
    const userData = localStorage.getItem('user');

    if (!accessToken) {
      console.log('❌ No access token found, setting unauthenticated');
      setAuthState({
        user: null,
        loading: false,
        error: null,
        isAuthenticated: false,
      });
      return;
    }

    // If we have cached user data, use it temporarily
    if (userData) {
      try {
        const cachedUser = JSON.parse(userData);
        setAuthState({
          user: cachedUser,
          loading: true,
          error: null,
          isAuthenticated: true,
        });
      } catch (error) {
        console.error('Error parsing cached user data:', error);
      }
    }

    try {
      const result = await apiClient.getUserInfo(accessToken);
      
      if (result.success && result.data) {
        setAuthState({
          user: result.data,
          loading: false,
          error: null,
          isAuthenticated: true,
        });
        localStorage.setItem('user', JSON.stringify(result.data));
      } else {
        // Token is invalid, clear everything
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        setAuthState({
          user: null,
          loading: false,
          error: 'Invalid token',
          isAuthenticated: false,
        });
      }
    } catch (error) {
      console.error('Error verifying token:', error);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      setAuthState({
        user: null,
        loading: false,
        error: 'Network error',
        isAuthenticated: false,
      });
    }
  }, []);

  // Login function
  const login = useCallback(async (email: string, password: string) => {
    try {
      setAuthState(prev => ({ ...prev, loading: true, error: null }));
      
      const loginRequest: LoginRequest = {
        username: email,
        password: password
      };
      
      const result = await apiClient.login(loginRequest);
      
      if (result.success && result.data) {
        const responseData = result.data as any;
        const tokens = responseData.tokens || responseData;
        const user = responseData.user || responseData.user;
        
        localStorage.setItem('access_token', tokens.access_token);
        localStorage.setItem('refresh_token', tokens.refresh_token);
        localStorage.setItem('user', JSON.stringify(user));
        
        setAuthState({
          user: user,
          loading: false,
          error: null,
          isAuthenticated: true,
        });
        
        return { success: true };
      } else {
        setAuthState(prev => ({ ...prev, loading: false, error: result.error || 'Login failed' }));
        return { success: false, error: result.error || 'Login failed' };
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Login failed';
      setAuthState(prev => ({ ...prev, loading: false, error: errorMessage }));
      return { success: false, error: errorMessage };
    }
  }, []);

  // Logout function
  const logout = useCallback(async () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    
    setAuthState({
      user: null,
      loading: false,
      error: null,
      isAuthenticated: false,
    });
    
    router.push('/login');
  }, [router]);

  // Refresh user data
  const refreshUser = useCallback(async () => {
    await checkAuth();
  }, [checkAuth]);

  // Handle OAuth callback on mount - ONLY ONCE
  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    const isOAuthCallback = accessToken && refreshToken;
    
    // Only process if:
    // 1. We have OAuth params
    // 2. Haven't processed yet (using ref, not state)
    // 3. Not already redirecting
    if (isOAuthCallback && !oauthProcessedRef.current && !isRedirectingRef.current) {
      handleOAuthCallback();
    } else if (!isOAuthCallback && !oauthProcessedRef.current) {
      // Normal auth check if not OAuth callback
      checkAuth();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty dependency array - run only once on mount

  const value: AuthContextType = {
    ...authState,
    login,
    logout,
    refreshUser,
    handleOAuthCallback,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
