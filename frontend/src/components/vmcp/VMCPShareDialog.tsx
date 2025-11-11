
import React, { useState, useEffect } from 'react';
import { X, Copy, Share, ExternalLink, Check, QrCode, Globe, Users, Link2, Container, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Modal } from '@/components/ui/modal';
import { useToast } from '@/hooks/use-toast';

interface VMCPShareDialogProps {
  isOpen: boolean;
  onClose: () => void;
  vmcp: any;
}

export function VMCPShareDialog({ isOpen, onClose, vmcp }: VMCPShareDialogProps) {
  const [copied, setCopied] = useState(false);
  const [qrCodeUrl, setQrCodeUrl] = useState<string>('');
  const { success, error } = useToast();

  // Generate share URL and QR code
  useEffect(() => {
    if (vmcp && isOpen) {
      // Create the new URL format: /<name_of_vmcp>/<vmcp_id>/vmcp
      const vmcpName = vmcp.name?.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'vmcp';
      const shareUrl = `${window.location.origin}/${vmcpName}/${vmcp.id}/vmcp`;
      const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(shareUrl)}`;
      setQrCodeUrl(qrUrl);
    }
  }, [vmcp, isOpen]);

  const handleCopy = async () => {
    if (!vmcp) return;
    
    // Create the new URL format: /<name_of_vmcp>/<vmcp_id>/vmcp
    const vmcpName = vmcp.name?.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'vmcp';
    const shareUrl = `${window.location.origin}/${vmcpName}/${vmcp.id}/vmcp`;
    
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      success('Share link copied to clipboard!');
      
      // Reset copied state after 2 seconds
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      error('Failed to copy link to clipboard');
    }
  };

  const handleOpenLink = () => {
    if (vmcp) {
      // Create the new URL format: /<name_of_vmcp>/<vmcp_id>/vmcp
      const vmcpName = vmcp.name?.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'vmcp';
      const shareUrl = `${window.location.origin}/${vmcpName}/${vmcp.id}/vmcp`;
      window.open(shareUrl, '_blank');
    }
  };

  if (!vmcp) return null;

  // Create the new URL format: /<name_of_vmcp>/<vmcp_id>/vmcp
  const vmcpName = vmcp.name?.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'vmcp';
  const shareUrl = `${window.location.origin}/${vmcpName}/${vmcp.id}/vmcp`;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Share vMCP" size="md">
      <div className="p-6 bg-card text-foreground">
        {/* vMCP Preview */}
        <div className="bg-muted/50 rounded-lg p-4 mb-6 border border-border">
          <div className="flex items-start gap-3">
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center border border-primary/20">
              <Container className="h-6 w-6 text-primary" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-foreground mb-1">{vmcp.name}</h3>
              <p className="text-sm text-muted-foreground mb-3">{vmcp.description || 'No description available'}</p>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Settings className="h-3 w-3" />
                  {vmcp.config?.vmcp_config?.selected_servers?.length || 0} servers
                </span>
                <span className="flex items-center gap-1">
                  <Globe className="h-3 w-3" />
                  {vmcp.config?.total_tools || 0} tools
                </span>
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3" />
                  {vmcp.install_count || 0} installs
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Share Options */}
        <div className="space-y-4">
          {/* Share Link */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Share Link
            </label>
            <div className="flex items-center gap-2">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={shareUrl}
                  readOnly
                  className="w-full px-4 py-3 pr-12 border border-border rounded-lg bg-muted/50 text-sm font-mono text-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <Link2 className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              </div>
              <Button
                onClick={handleCopy}
                variant="outline"
                className="px-4 py-3 flex items-center gap-2"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-green-600" />
                    <span className="text-green-600">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* QR Code */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              QR Code
            </label>
            <div className="bg-muted/50 border border-border rounded-lg p-4 text-center">
              {qrCodeUrl ? (
                <img
                  src={qrCodeUrl}
                  alt="QR Code"
                  className="w-32 h-32 mx-auto rounded-lg"
                  onError={() => setQrCodeUrl('')}
                />
              ) : (
                <div className="w-32 h-32 mx-auto bg-muted rounded-lg flex items-center justify-center">
                  <QrCode className="h-8 w-8 text-muted-foreground" />
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-2">Scan to access</p>
            </div>
          </div>

          {/* Share Stats */}
          {vmcp.is_public && (
            <div className="bg-primary/10 border border-primary/20 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Users className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium text-foreground">Sharing Statistics</span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-2xl font-bold text-foreground">{vmcp.install_count || 0}</div>
                  <div className="text-muted-foreground">Total Installs</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground">
                    {vmcp.created_at ? Math.floor((Date.now() - new Date(vmcp.created_at).getTime()) / (1000 * 60 * 60 * 24)) : 0}
                  </div>
                  <div className="text-muted-foreground">Days Created</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-6 border-t border-border mt-6">
          <p className="text-xs text-muted-foreground">
            Anyone with this link can install your vMCP
          </p>
        </div>
      </div>
    </Modal>
  );
}
