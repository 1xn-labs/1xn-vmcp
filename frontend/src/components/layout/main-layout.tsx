
import React from 'react';
import { AppSidebar } from '@/components/layout/app-sidebar';
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar';
import { Toaster } from '../ui/sonner';
import CreateVMCPModal from '@/components/vmcp/CreateVMCPModal';
import { useCreateVMCPModal } from '@/contexts/create-vmcp-modal-context';
import { useVMCP } from '@/contexts/vmcp-context';
import { useRouter } from '@/hooks/useRouter';

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const router = useRouter();
  const { isOpen: createModalOpen, closeModal } = useCreateVMCPModal();
  const { forceRefreshVMCPData } = useVMCP();

  // Handle successful vMCP creation
  const handleCreateSuccess = (vmcpId: string) => {
    closeModal();
    // Refresh vMCP data to show the new vMCP in sidebar
    forceRefreshVMCPData();
    // Navigate to the new vMCP
    router.push(`/vmcp/${vmcpId}`);
  };

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <main className="flex-1 overflow-hidden">
          {/* Background Effects */}
          {/* <div className="inset-0">
            <div className="absolute top-0 left-1/12 w-96 h-96 bg-primary/10 rounded-full blur-3xl"></div>
            <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-secondary/5 rounded-full blur-3xl"></div>
          </div> */}
          {/* Default main content padding,*/}
          {/* Simple primary glow */}
          <div className="min-h-screen bg-gradient-to-br from-primary/5 to-background text-foreground overflow-hidden relative">
          <div className='mx-auto text-foreground px-4 sm:px-6 lg:px-12 py-12'>
            {children}
            <Toaster/>
          </div>
          </div>
        </main>
      </SidebarInset>
      
      {/* Global Create vMCP Modal */}
      <CreateVMCPModal
        isOpen={createModalOpen}
        onClose={closeModal}
        onSuccess={handleCreateSuccess}
      />
    </SidebarProvider>
  );
} 