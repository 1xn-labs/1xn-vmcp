
import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './auth-context';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';

// Types
interface CommunityVMCPState {
  publicVMCPS: any[]; // Public community vMCPs
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  initialized: boolean;
}

interface CommunityVMCPContextType extends CommunityVMCPState {
  loadCommunityVMCPs: () => Promise<void>;
  refreshCommunityVMCPs: () => Promise<void>;
  forceRefreshCommunityVMCPs: () => Promise<void>;
  getPublicVMCPDetails: (vmcpId: string) => Promise<any>;
  installVMCP: (vmcpId: string) => Promise<boolean>;
}

const CommunityVMCPContext = createContext<CommunityVMCPContextType | undefined>(undefined);

export function CommunityVMCPProvider({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const initializedRef = useRef(false);

  const [state, setState] = useState<CommunityVMCPState>({
    publicVMCPS: [],
    loading: false,
    error: null,
    lastUpdated: null,
    initialized: false
  });

  const loadCommunityVMCPs = useCallback(async () => {
    if (!isAuthenticated || !user) return;

    // Only load data if not already initialized
    if (initializedRef.current) {
      console.log('🔄 Community vMCP data already loaded, skipping...');
      return;
    }

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const publicVMCPResult = await apiClient.listPublicVMCPS(accessToken);

      if (publicVMCPResult.success && publicVMCPResult.data) {
        setState(prev => ({
          ...prev,
          publicVMCPS: publicVMCPResult.data || [],
          loading: false,
          lastUpdated: new Date(),
          initialized: true,
          error: null
        }));

        // Also update the ref
        initializedRef.current = true;

        console.log('✅ Community vMCP data loaded successfully:', {
          publicVMCPs: publicVMCPResult.data?.length || 0
        });
      } else {
        throw new Error(publicVMCPResult.error || 'Failed to load community vMCPs');
      }
    } catch (error) {
      console.error('❌ Error loading community vMCP data:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load community vMCP data',
        initialized: false
      }));

      // Also reset the ref
      initializedRef.current = false;
    }
  }, [isAuthenticated, user]);

  // Load community VMCP data when component mounts and user is authenticated
  useEffect(() => {
    if (isAuthenticated && user && !initializedRef.current) {
      loadCommunityVMCPs();
    }
  }, [isAuthenticated, user, loadCommunityVMCPs]);

  const forceRefreshCommunityVMCPs = useCallback(async () => {
    if (!isAuthenticated || !user) return;

    // Reset initialized flag to force reload
    initializedRef.current = false;

    // Load data again
    await loadCommunityVMCPs();
  }, [isAuthenticated, user, loadCommunityVMCPs]);

  const refreshCommunityVMCPs = useCallback(async () => {
    if (!isAuthenticated || !user) return;

    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        throw new Error('No access token available');
      }

      const publicVMCPResult = await apiClient.listPublicVMCPS(accessToken);

      if (publicVMCPResult.success && publicVMCPResult.data) {
        setState(prev => ({
          ...prev,
          publicVMCPS: publicVMCPResult.data || [],
          loading: false,
          error: null,
          lastUpdated: new Date()
        }));
      }
    } catch (error) {
      console.error('Error refreshing community vMCP data:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to refresh community vMCP data'
      }));
    }
  }, [isAuthenticated, user]);

  const getPublicVMCPDetails = useCallback(async (vmcpId: string) => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return null;

    try {
      const result = await apiClient.getPublicVMCPDetails(vmcpId, accessToken);
      return result.success && result.data ? result.data : null;
    } catch (error) {
      console.error(`Error loading details for public vMCP ${vmcpId}:`, error);
      return null;
    }
  }, []);

  const installVMCP = useCallback(async (vmcpId: string) => {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return false;

    try {
      const result = await apiClient.installVMCP(vmcpId, accessToken);
      if (result.success) {
        console.log('✅ vMCP installed successfully:', vmcpId);
        return true;
      } else {
        console.error('❌ Failed to install vMCP:', result.error);
        return false;
      }
    } catch (error) {
      console.error(`Error installing vMCP ${vmcpId}:`, error);
      return false;
    }
  }, []);

  const contextValue: CommunityVMCPContextType = {
    ...state,
    loadCommunityVMCPs,
    refreshCommunityVMCPs,
    forceRefreshCommunityVMCPs,
    getPublicVMCPDetails,
    installVMCP
  };

  return (
    <CommunityVMCPContext.Provider value={contextValue}>
      {children}
    </CommunityVMCPContext.Provider>
  );
}

// Custom hooks
export function useCommunityVMCPs() {
  const context = useContext(CommunityVMCPContext);
  if (context === undefined) {
    throw new Error('useCommunityVMCPs must be used within a CommunityVMCPProvider');
  }
  return context;
}

// Selector hooks for specific data
export function useCommunityVMCPList() {
  const { publicVMCPS } = useCommunityVMCPs();
  return publicVMCPS;
}

export function useCommunityVMCPLoading() {
  const { loading } = useCommunityVMCPs();
  return loading;
}

export function useCommunityVMCPError() {
  const { error } = useCommunityVMCPs();
  return error;
}

export function useCommunityVMCPInitialized() {
  const { initialized } = useCommunityVMCPs();
  return initialized;
}