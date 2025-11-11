
import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import {
  ChevronRight,
  Plus,
  Container,
  Search,
  X
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useVMCP } from '@/contexts/vmcp-context';
import { useCreateVMCPModal } from '@/contexts/create-vmcp-modal-context';
import {
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
  useSidebar,
  SidebarMenu
} from '@/components/ui/sidebar';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

interface VMCPSidebarProps {
  // No props needed - uses shadcn sidebar context

}
const menuItem = {
    name: 'vMCP',
    href: '/servers',
    icon: Container,
    key: 'servers',
  }

export function VMCPSidebar({ }: VMCPSidebarProps) {
  const router = useRouter();
  const pathname = router.pathname;
  const { vmcps, loading } = useVMCP();
  const { setOpenMobile } = useSidebar();
  const { openModal } = useCreateVMCPModal();

  const [vmcpsExpanded, setVmcpsExpanded] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Combine private and public vMCPs for filtering
  // Ensure vmcps.private and vmcps.public are arrays
  const allVmcps = useMemo(() => {
    const privateList = Array.isArray(vmcps?.private) ? vmcps.private : [];
    const publicList = Array.isArray(vmcps?.public) ? vmcps.public : [];
    return [...privateList, ...publicList];
  }, [vmcps]);

  // Expand vMCPs section when data changes
  useEffect(() => {
    if (allVmcps.length > 0 && !vmcpsExpanded) {
      setVmcpsExpanded(true);
    }
  }, [allVmcps, vmcpsExpanded]);

  // Extract active vMCP id from pathname
  let activeVMCPId: string | null = null;
  const match = pathname.match(/^\/vmcp\/([^\/]+)/);
  if (match) {
    activeVMCPId = match[1];
  }

  // Filter vMCPs based on search query
  const filteredVmcps = useMemo(() => {
    if (!searchQuery.trim()) return allVmcps;
    
    return allVmcps.filter(vmcp => {
      const vmcpName = vmcp.name || '';
      const vmcpDescription = vmcp.description || '';
      
      return vmcpName.toLowerCase().includes(searchQuery.toLowerCase()) ||
             vmcpDescription.toLowerCase().includes(searchQuery.toLowerCase());
    });
  }, [allVmcps, searchQuery]);

  // Show search only when there are more than 8 vMCPs
  const showSearch = allVmcps.length > 8;

  // Handlers
  const handleItemClick = () => {
    if (window.innerWidth < 768) {
      setOpenMobile(false);
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const clearSearch = () => {
    setSearchQuery('');
  };

  // const isActive = pathname.startsWith('/servers') || pathname.startsWith('/vmcp');
  const isActive = pathname.startsWith('/vmcp');
  const isNewVmcpActive = pathname.includes('/vmcp/new');


  return (
    <SidebarMenu>
      <Collapsible
        className="group/collapsible"
        defaultOpen={true}
      >
        <SidebarMenuItem  key={menuItem.name} className='px-2'>
            <Link to="/vmcp" onClick={handleItemClick}>
              <SidebarMenuButton tooltip={menuItem.name} isActive={isActive}>
                {menuItem.icon && <menuItem.icon className='size-4' />}
                <span>{menuItem.name}</span>
                <CollapsibleTrigger asChild>
                  <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90 group-data-[collapsible=icon]:hidden" />
                </CollapsibleTrigger>
              </SidebarMenuButton>
            </Link>

          <CollapsibleContent>
            <SidebarMenuSub>
              {/* New vMCP Button - Always visible */}
              <SidebarMenuSubItem>
            <SidebarMenuSubButton 
              className='h-10 cursor-pointer' 
              onClick={() => {
                console.log('Sidebar New vMCP clicked');
                handleItemClick();
                openModal();
              }}
            >
              <div className="h-6 w-6 rounded-full border-2 border-primary border-dashed flex items-center justify-center shrink-0">
                <Plus className="h-6 w-6 text-primary" />
              </div>
              <span>New vMCP</span>
            </SidebarMenuSubButton>
          </SidebarMenuSubItem>

              {/* Search Input - Only show when there are more than 8 vMCPs */}
              {showSearch && (
                <SidebarMenuSubItem>
                  <div className="relative px-2 py-1">
                    <div className="relative">
                      <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-3 w-3 text-sidebar-foreground/50" />
                      <input
                        type="text"
                        placeholder="Search vMCPs..."
                        value={searchQuery}
                        onChange={handleSearchChange}
                        className="w-full pl-7 pr-8 py-1.5 text-xs bg-sidebar-accent border border-sidebar-border rounded-md focus:outline-none focus:ring-1 focus:ring-sidebar-primary focus:border-sidebar-primary text-sidebar-foreground placeholder-sidebar-foreground/50"
                      />
                      {searchQuery && (
                        <button
                          onClick={clearSearch}
                          className="absolute right-2 top-1/2 transform -translate-y-1/2 h-3 w-3 text-sidebar-foreground/50 hover:text-sidebar-foreground"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  </div>
                </SidebarMenuSubItem>
              )}
              
              {/* Scrollable vMCPs Container */}
              <div className="max-h-[320px] overflow-y-auto scrollbar-thin scrollbar-thumb-sidebar-foreground/20 scrollbar-track-transparent">
                {loading ? (
                  <SidebarMenuSubItem>
                    <div className="text-xs text-sidebar-foreground/70 px-2 py-1">Loading...</div>
                  </SidebarMenuSubItem>
                ) : filteredVmcps.length === 0 && searchQuery ? (
                  <SidebarMenuSubItem>
                    <div className="text-xs text-sidebar-foreground/70 px-2 py-1">No vMCPs found</div>
                  </SidebarMenuSubItem>
                ) : (
                  filteredVmcps.map((vmcp) => {
                    const isVMCPActive = activeVMCPId === vmcp.id;
                    
                    // Safely extract name and description from the registry structure
                    const vmcpName = vmcp.name || 'Unnamed vMCP';
                    const vmcpDescription = vmcp.description;

                    return (
                      <SidebarMenuSubItem key={vmcp.id} >
                        <SidebarMenuSubButton asChild isActive={isVMCPActive} className='h-10'>
                          <Link to={`/vmcp/${vmcp.id}`} onClick={handleItemClick}>
                            <div className="h-6 w-6 rounded-full border border-primary flex items-center justify-center font-bold">
                              {vmcpName.charAt(0).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                              <span className="text-xs truncate block font-bold">
                                {vmcpName.toUpperCase()}
                              </span>
                              {vmcpDescription && (
                                <span className="text-xs text-sidebar-foreground/70 truncate block">
                                  {vmcpDescription}
                                </span>
                              )}
                            </div>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    );
                  })
                )}
              </div>
            </SidebarMenuSub>
          </CollapsibleContent>
        </SidebarMenuItem>
      </Collapsible>
    </SidebarMenu>
  );
} 