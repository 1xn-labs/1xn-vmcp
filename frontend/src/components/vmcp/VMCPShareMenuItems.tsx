import React from 'react';

interface VMCPShareMenuItemsProps {
  vmcp: any;
  onShare: (vmcpId: string) => void;
  onTogglePublic: (vmcpId: string, isPublic: boolean) => void;
  sharingStates: Record<string, boolean>;
  isPublic: boolean;
}

// OSS version: Empty placeholder component
export default function VMCPShareMenuItems({
  vmcp,
  onShare,
  onTogglePublic,
  sharingStates,
  isPublic,
}: VMCPShareMenuItemsProps) {
  // Return null - no Share/Public menu items in OSS
  return null;
}

