
import React from 'react';
import { AuthProvider } from './auth-context';
import { ServersProvider } from './servers-context';
import { VMCPProvider } from './vmcp-context';
import { CommunityVMCPProvider } from './community-vmcps-context';
import { ThemeProvider } from './theme-context';
import { CreateVMCPModalProvider } from './create-vmcp-modal-context';

interface AppProviderProps {
  children: React.ReactNode;
}

/**
 * AppProvider combines all context providers in the correct dependency order:
 * 1. ThemeProvider - No dependencies
 * 2. AuthProvider - No dependencies
 * 3. ServersProvider - Depends on AuthProvider
 * 4. VMCPProvider - Depends on ServersProvider
 * 5. CommunityVMCPProvider - Depends on AuthProvider (handles public VMCP data)
 *
 * ChatProvider is now used locally in the chat page since it depends on both
 * AuthProvider and VMCPProvider, and is only needed for chat functionality.
 * This ensures proper data flow and prevents unnecessary re-renders.
 */
export function AppProvider({ children }: AppProviderProps) {
  return (
    <ServersProvider>
      <VMCPProvider>
        <CommunityVMCPProvider>
          <CreateVMCPModalProvider>
            {children}
          </CreateVMCPModalProvider>
        </CommunityVMCPProvider>
      </VMCPProvider>
    </ServersProvider>
  );
}
