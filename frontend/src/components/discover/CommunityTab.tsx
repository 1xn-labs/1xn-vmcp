import React from 'react';
import { Card, CardContent, CardDescription, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Container, Globe, Search } from 'lucide-react';

interface CommunityTabProps {
  vmcps: any[];
  searchQuery: string;
  debouncedQuery: string;
  onInstall: (vmcpId: string, vmcpType: string) => void;
}

export default function CommunityTab({
  vmcps,
  searchQuery,
  debouncedQuery,
  onInstall,
}: CommunityTabProps) {
  // OSS version: Show placeholder directing users to 1xn.ai
  return (
    <Card className="text-center py-16 bg-gradient-to-br from-muted/20 to-muted/10 border-2 border-dashed border-muted-foreground/30">
      <CardContent className="space-y-4">
        <div className="h-20 w-20 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
          <Globe className="h-10 w-10 text-muted-foreground" />
        </div>
        <CardTitle className="text-2xl font-semibold mb-2">
          Discover More vMCPs
        </CardTitle>
        <CardDescription className="text-muted-foreground max-w-md mx-auto text-base">
          To discover and access more community vMCPs, visit{' '}
          <a 
            href="https://1xn.ai" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-primary hover:underline font-medium"
          >
            1xn.ai
          </a>
          {' '}for the full enterprise experience with authentication and community features.
        </CardDescription>
        <Button 
          asChild
          className="mt-4"
          variant="default"
        >
          <a 
            href="https://1xn.ai" 
            target="_blank" 
            rel="noopener noreferrer"
          >
            Visit 1xn.ai <Globe className="ml-2 h-4 w-4" />
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}

