
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useAuth } from './auth-context';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import type { CreateVMCPRequest, UpdateVMCPRequest } from '@/api/client';
// import type { VMCPCreateRequest } from '@/lib/new-api';
import type { VmcpConfig } from '@/api/generated/types.gen';
import { VMCPConfig, VMCPRegistryConfig } from '@/types/vmcp';

// Helper function to get the appropriate token for API calls
const getApiToken = (): string => {
  const authDisabled = import.meta.env.VITE_VMCP_OSS_BUILD === 'true';
  const storedToken = localStorage.getItem('access_token');
  
  if (storedToken) {
    return storedToken;
  }
  
  if (authDisabled) {
    return 'local-token'; // Use dummy token for local OSS deployment
  }
  
  throw new Error('No access token available');
};

// Types
interface VMCPAgent {
  id: string;
  name: string;
  description?: string;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
}


interface VMCPState {
  agents: VMCPAgent[];
  activeAgent: VMCPAgent | null;
  servers: any[];
  vmcps: {
    private: VMCPRegistryConfig[];
    public: VMCPRegistryConfig[];
  };
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  initialized: boolean;
}

interface VMCPContextType extends VMCPState {
  loadVMCPData: () => Promise<void>;
  refreshVMCPData: () => Promise<void>;
  forceRefreshVMCPData: () => Promise<void>; // Add force refresh function
  switchActiveAgent: (agentId: string) => Promise<void>;
  getVMCPTools: (vmcpId: string) => Promise<any[]>;
  getVMCPResources: (vmcpId: string) => Promise<any[]>;
  getVMCPPrompts: (vmcpId: string) => Promise<any[]>;
  checkHealth: () => Promise<boolean>;
  createVMCP: (request: CreateVMCPRequest) => Promise<VmcpConfig | null>;
  deleteVMCP: (vmcpId: string) => Promise<boolean>;
  updateVMCP: (vmcpId: string, request: CreateVMCPRequest) => Promise<VmcpConfig | null>;
}


// Create separate contexts for state and actions
const VMCPStateContext = createContext<VMCPState | undefined>(undefined);
const VMCPActionsContext = createContext<Omit<VMCPContextType, keyof VMCPState> | undefined>(undefined);

export function VMCPProvider({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const initializedRef = useRef(false); // Use ref to track initialization

  const [state, setState] = useState<VMCPState>({
    agents: [],
    activeAgent: null,
    servers: [],
    vmcps: {
      private: [],
      public: []
    },
    loading: false,
    error: null,
    lastUpdated: null,
    initialized: false
  });

  
  const loadVMCPData = useCallback(async () => {
    if (!isAuthenticated || !user) return;
    
    // Only load data if not already initialized
    if (initializedRef.current) {
      console.log('🔄 vMCP data already loaded, skipping...');
      return;
    }

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const accessToken = getApiToken();

      // Load VMCPs with new structure (private and public arrays)
      const vmcpResult = await apiClient.listVMCPS(accessToken);

      if (vmcpResult.success && vmcpResult.data) {
        const vmcpsData = vmcpResult.data as unknown as { private: VMCPRegistryConfig[]; public: VMCPRegistryConfig[] };

        setState(prev => ({
          ...prev,
          vmcps: vmcpsData,
          loading: false,
          lastUpdated: new Date(),
          initialized: true, // Mark as initialized
          error: null
        }));

        // Also update the ref
        initializedRef.current = true;

        console.log('✅ vMCP data loaded successfully:', {
          private: vmcpsData.private?.length || 0,
          public: vmcpsData.public?.length || 0
        });
      } else {
        throw new Error(vmcpResult.error || 'Failed to load vMCPs');
      }
    } catch (error) {
      console.error('❌ Error loading vMCP data:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load vMCP data',
        initialized: false // Reset initialized flag on error
      }));
      
      // Also reset the ref
      initializedRef.current = false;
    }
  }, [isAuthenticated, user]); // Remove state.initialized dependency

  // Load VMCP data when component mounts and user is authenticated
  useEffect(() => {
    if (isAuthenticated && user && !initializedRef.current) {
      loadVMCPData();
    }
  }, [isAuthenticated, user, loadVMCPData]);


  const forceRefreshVMCPData = useCallback(async () => {
    if (!isAuthenticated || !user) return;
    
    // Reset initialized flag to force reload
    initializedRef.current = false;
    
    // Load data again
    await loadVMCPData();
  }, [isAuthenticated, user, loadVMCPData]);

  const getVMCPTools = useCallback(async (vmcpId: string) => {
    try {
      const accessToken = getApiToken();
      const result = await apiClient.listVMCPTools(vmcpId, accessToken);
      return result.success && result.data ? result.data : [];
    } catch (error) {
      console.error(`Error loading tools for vMCP ${vmcpId}:`, error);
      return [];
    }
  }, []);

  const getVMCPResources = useCallback(async (vmcpId: string) => {
    try {
      const accessToken = getApiToken();
      const result = await apiClient.listVMCPResources(vmcpId, accessToken);
      return result.success && result.data ? result.data : [];
    } catch (error) {
      console.error(`Error loading resources for vMCP ${vmcpId}:`, error);
      return [];
    }
  }, []);

  const getVMCPPrompts = useCallback(async (vmcpId: string) => {
    try {
      const accessToken = getApiToken();
      const result = await apiClient.listVMCPPrompts(vmcpId, accessToken);
      return result.success && result.data ? result.data : [];
    } catch (error) {
      console.error(`Error loading prompts for vMCP ${vmcpId}:`, error);
      return [];
    }
  }, []);

  const switchActiveAgent = useCallback(async (agentId: string) => {
    const agent = state.agents.find(a => a.id === agentId);
    if (agent) {
      setState(prev => ({ ...prev, activeAgent: agent }));
    }
  }, [state.agents]);


  const checkHealth = useCallback(async () => {
    // Implementation for health check
    return true;
  }, []);

  const createVMCP = useCallback(async (request: CreateVMCPRequest) => {
    if (!isAuthenticated || !user) return null;

    try {
      const accessToken = getApiToken();
      const result = await apiClient.createVMCP(request, accessToken);
      if (result.success && result.data) {
        // The API returns a VMCPCreateResponse with nested vMCP
        const newVMCP = result.data as unknown as VmcpConfig;

        setState(prev => ({
          ...prev,
          vmcps: {
            ...prev.vmcps,
            private: [...prev.vmcps.private, newVMCP as unknown as VMCPRegistryConfig]
          },
          lastUpdated: new Date()
        }));
        return newVMCP;
      } else {
        throw new Error(result.error || 'Failed to create VMCP');
      }
    } catch (error) {
      console.error('Error creating VMCP:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Unknown error'
      }));
      return null;
    }
  }, [isAuthenticated, user]);

  const deleteVMCP = useCallback(async (vmcpId: string) => {
    if (!isAuthenticated || !user) return false;

    try {
      const accessToken = getApiToken();
      const result = await apiClient.deleteVMCP(vmcpId, accessToken);
      if (result.success) {
        setState(prev => ({
          ...prev,
          vmcps: {
            ...prev.vmcps,
            private: prev.vmcps.private.filter(v => v.id !== vmcpId),
            public: prev.vmcps.public.filter(v => v.id !== vmcpId)
          },
          lastUpdated: new Date()
        }));
        return true;
      } else {
        throw new Error(result.error || 'Failed to delete VMCP');
      }
    } catch (error) {
      console.error('Error deleting VMCP:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Unknown error'
      }));
      return false;
    }
  }, [isAuthenticated, user]);

  const updateVMCP = useCallback(async (vmcpId: string, request: CreateVMCPRequest) => {
    if (!isAuthenticated || !user) return null;

    try {
      const accessToken = getApiToken();
      const result = await apiClient.updateVMCP(vmcpId, request, accessToken);
      if (result.success && result.data) {
        // The API returns a VMCPCreateResponse with nested vMCP
        const updatedVMCP = result.data as unknown as VmcpConfig;

        setState(prev => ({
          ...prev,
          vmcps: {
            ...prev.vmcps,
            private: prev.vmcps.private.map(v => v.id === vmcpId ? updatedVMCP as unknown as VMCPRegistryConfig : v),
            public: prev.vmcps.public.map(v => v.id === vmcpId ? updatedVMCP as unknown as VMCPRegistryConfig : v)
          },
          lastUpdated: new Date()
        }));
        return updatedVMCP;
      } else {
        throw new Error(result.error || 'Failed to update VMCP');
      }
    } catch (error) {
      console.error('Error updating VMCP:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Unknown error'
      }));
      return null;
    }
  }, [isAuthenticated, user]);

  const refreshVMCPData = useCallback(async () => {
    if (!isAuthenticated || !user) return;

    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const accessToken = getApiToken();

      // Load user vMCPs
      const vmcpsResult = await apiClient.listVMCPS(accessToken);

      if (vmcpsResult.success && vmcpsResult.data) {
        setState(prev => ({
          ...prev,
          vmcps: (vmcpsResult.data as unknown as { private: VMCPRegistryConfig[]; public: VMCPRegistryConfig[] }) || { private: [], public: [] },
          loading: false,
          error: null,
          lastUpdated: new Date()
        }));
      }
    } catch (error) {
      console.error('Error refreshing vMCP data:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to refresh vMCP data'
      }));
    }
  }, [isAuthenticated, user]);

  // Memoize actions to prevent unnecessary re-renders
  const actions = useMemo(() => ({
    loadVMCPData,
    refreshVMCPData,
    forceRefreshVMCPData,
    switchActiveAgent,
    getVMCPTools,
    getVMCPResources,
    getVMCPPrompts,
    checkHealth,
    createVMCP,
    deleteVMCP,
    updateVMCP,
  }), [
    loadVMCPData,
    refreshVMCPData,
    forceRefreshVMCPData,
    switchActiveAgent,
    getVMCPTools,
    getVMCPResources,
    getVMCPPrompts,
    checkHealth,
    createVMCP,
    deleteVMCP,
    updateVMCP,
  ]);

  return (
    <VMCPStateContext.Provider value={state}>
      <VMCPActionsContext.Provider value={{
        loadVMCPData,
        refreshVMCPData,
        forceRefreshVMCPData,
        switchActiveAgent,
        getVMCPTools,
        getVMCPResources,
        getVMCPPrompts,
        checkHealth,
        createVMCP,
        deleteVMCP,
        updateVMCP,
      }}>
        {children}
      </VMCPActionsContext.Provider>
    </VMCPStateContext.Provider>
  );
}

// Custom hooks with selectors to prevent unnecessary re-renders
export function useVMCPState() {
  const context = useContext(VMCPStateContext);
  if (context === undefined) {
    throw new Error('useVMCPState must be used within a VMCPProvider');
  }
  return context;
}

export function useVMCPActions() {
  const context = useContext(VMCPActionsContext);
  if (context === undefined) {
    throw new Error('useVMCPActions must be used within a VMCPProvider');
  }
  return context;
}

// Legacy hook for backward compatibility
export function useVMCP() {
  const state = useVMCPState();
  const actions = useVMCPActions();
  return { ...state, ...actions };
}

// Selector hooks for specific data
export function useVMCPList() {
  const { vmcps } = useVMCPState();
  // Ensure vmcps.private and vmcps.public are arrays
  const privateList = Array.isArray(vmcps?.private) ? vmcps.private : [];
  const publicList = Array.isArray(vmcps?.public) ? vmcps.public : [];
  return [...privateList, ...publicList];
}

export function useVMCPById(vmcpId: string) {
  const { vmcps } = useVMCPState();
  const privateList = Array.isArray(vmcps?.private) ? vmcps.private : [];
  const publicList = Array.isArray(vmcps?.public) ? vmcps.public : [];
  const allVmcps = [...privateList, ...publicList];
  return allVmcps.find(vmcp => vmcp.id === vmcpId);
}


export function useVMCPLoading() {
  const { loading } = useVMCPState();
  return loading;
}

export function useVMCPError() {
  const { error } = useVMCP();
  return error;
}

export function useVMCPInitialized() {
  const { initialized } = useVMCP();
  return initialized;
}

