import React from 'react';
import { Edit, Download, Trash2 } from 'lucide-react';
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import VMCPShareMenuItems from './VMCPShareMenuItems';

interface VMCPCardActionsMenuProps {
  vmcp: any;
  onEdit: (vmcpId: string) => void;
  onDelete: (vmcp: any) => void;
  onExport: (vmcp: any) => void;
  onShare?: (vmcpId: string) => void;
  onTogglePublic?: (vmcpId: string, isPublic: boolean) => void;
  sharingStates: Record<string, boolean>;
  isPublic: boolean;
}

export default function VMCPCardActionsMenu({
  vmcp,
  onEdit,
  onDelete,
  onExport,
  onShare,
  onTogglePublic,
  sharingStates,
  isPublic,
}: VMCPCardActionsMenuProps) {
  return (
    <DropdownMenuContent align="end" className="w-48">
      {/* Enterprise Share/Public menu items (empty in OSS, populated in Enterprise via alias) */}
      <VMCPShareMenuItems
        vmcp={vmcp}
        onShare={onShare || (() => {})}
        onTogglePublic={onTogglePublic || (() => {})}
        sharingStates={sharingStates}
        isPublic={isPublic}
      />

      {/* Edit Action - Separator will be included by VMCPShareMenuItems in Enterprise */}
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          onEdit(vmcp.id);
        }}
        className="flex items-center gap-2"
      >
        <Edit className="h-4 w-4" />
        Edit
      </DropdownMenuItem>

      {/* Export Action */}
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          onExport(vmcp);
        }}
        className="flex items-center gap-2"
      >
        <Download className="h-4 w-4" />
        Export Config
      </DropdownMenuItem>

      <DropdownMenuSeparator />

      {/* Delete Action */}
      <DropdownMenuItem
        onClick={(e) => {
          e.stopPropagation();
          onDelete(vmcp);
        }}
        className="flex items-center gap-2 text-destructive focus:text-destructive"
      >
        <Trash2 className="h-4 w-4" />
        Delete
      </DropdownMenuItem>
    </DropdownMenuContent>
  );
}

