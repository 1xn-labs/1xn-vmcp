
import { useAuth } from '@/contexts/auth-context';

import React from 'react';
import { Link } from 'react-router-dom';
import { useRouter } from '@/hooks/useRouter';
import { 
  Server, 
  MessageSquare,
  LogOut,
  Settings,
  Bot,
  Layers,
  Container,
  BotMessageSquare,
  ChartBar,
  Globe,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getInitials } from '@/lib/app-utils';
import { useToast } from '@/hooks/use-toast';
import { VMCPSidebar } from '@/components/ui/vmcp-sidebar';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar
} from '@/components/ui/sidebar';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';




interface AppSidebarProps {
  // No props needed - shadcn sidebar manages its own state
}


const navigationItems = [
  {
    name: 'vMCP',
    href: '/vmcp',
    icon: Container,
    key: 'vmcp',
  },
  {
    name: 'Discover',
    href: '/discover',
    icon: Globe,
    key: 'discover',
  },
  {
    name: 'Stats',
    href: '/stats',
    icon: ChartBar,
    key: 'stats',
  },
  {
    name: 'Connections',
    href: '/servers',
    icon: Server,
    key: 'Connections',
  },
  // {
  //   name: 'Apps',
  //   href: '/napps',
  //   icon: Layers,
  //   key: 'napps',
  // },
  // {
  //   name: 'Chat',
  //   href: '/chat',
  //   icon: BotMessageSquare,
  //   key: 'chat',
  // },
];

export function AppSidebar({}: AppSidebarProps) {
  const router = useRouter();
  const pathname = router.pathname;
  const { error } = useToast();
  const { user, logout } = useAuth();
  const { setOpenMobile } = useSidebar();

  const handleLogout = async () => {
    try {
      await logout();
    } catch (err) {
      error('Failed to logout');
    }
  };

  const displayName = user?.full_name || user?.email || 'User';
  const initials = getInitials(displayName);

  return (
    <Sidebar collapsible="icon" className="border-sidebar-border bg-sidebar">

      <SidebarHeader>
        <div className="flex gap-2 p-2 mb-2 bg-muted min-h-16 items-center">
          <img  
            src={`/app/1xn_logo_noframe.svg`} 
            alt="1xN Logo" 
            className="w-8 h-8 object-contain"
          />
          <span className="flex-1 text-2xl text-center font-bold text-sidebar-foreground group-data-[collapsible=icon]:hidden">
            1xn
          </span>
          <SidebarTrigger/>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarMenu>
          {navigationItems.map((item) => {
            // Special handling for vMCP
            if (item.key === 'vmcp') {
              return (
                <VMCPSidebar key={item.key}/>
              );
            }
            
            // Use exact path matching to prevent overlapping highlights
            const isActive = pathname === item.href || 
              (item.href !== '/vmcp' && item.href !== '/vmcp-dashboard' && pathname.startsWith(item.href));
            const Icon = item.icon;
            
            return (
              <SidebarMenuItem key={item.key} className='px-2'>
                <SidebarMenuButton
                  asChild
                  isActive={isActive}
                  tooltip={item.name}
                >
                  <Link
                    to={item.href}
                    onClick={() => {
                      if (window.innerWidth < 768) {
                        setOpenMobile(false);
                      }
                    }}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.name}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex items-center gap-1 p-2 bg-muted">
              <Avatar className="h-8 w-8">
                {user?.photo_url ? (
                  <AvatarImage 
                    src={user.photo_url} 
                    alt={`${user.full_name}'s profile picture`}
                  />
                ) : null}
                <AvatarFallback className="bg-sidebar-primary text-sidebar-primary-foreground text-sm">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0 group-data-[collapsible=icon]:hidden">
                <p className="text-sm font-medium text-sidebar-foreground truncate">{displayName}</p>
                {user?.email && (
                  <p className="text-xs text-sidebar-foreground/70 truncate">{user.email}</p>
                )}
              </div>
              <div className="flex items-center gap-1 group-data-[collapsible=icon]:hidden">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push('/settings')}
                >
                  <Settings/>
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleLogout}
                  className="h-8 w-8 p-0 hover:text-destructive"
                >
                <LogOut className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </SidebarMenuItem>
          
          {/* Collapsed state buttons */}
          <div className="hidden items-center group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:gap-1">
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip="Settings"
                onClick={() => router.push('/settings')}
              >
                <Settings className="h-4 w-4" />
              </SidebarMenuButton>
            </SidebarMenuItem>  
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip="Logout"
                onClick={handleLogout}
              >
                <LogOut className="h-4 w-4" />
              </SidebarMenuButton>
            </SidebarMenuItem>
          </div>
        </SidebarMenu>
        
        <div className="text-xs text-sidebar-foreground/50 text-center group-data-[collapsible=icon]:hidden">
          1xN web-client v1.1.4
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

export function SidebarToggle({ className }: { className?: string }) {
  return (
    <SidebarTrigger className={cn('md:hidden', className)} />
  );
} 