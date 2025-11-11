
import { useState, useEffect } from 'react';
import { X, Download, Eye, FileText, Image, File, FileVideo, FileAudio } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
// import { newApi } from '@/lib/new-api';
import { apiClient } from '@/api/client';
import { Resource } from '@/types/vmcp';

interface ResourceViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  resource: Resource | null;
}

export default function ResourceViewerModal({ isOpen, onClose, resource }: ResourceViewerModalProps) {
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blobData, setBlobData] = useState<any>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [binaryBlob, setBinaryBlob] = useState<Blob | null>(null);

  useEffect(() => {
    if (isOpen && resource) {
      setLoading(true);
      setDownloading(false);
      setError(null);
      setBlobData(null);
      setBlobUrl(null);
      setBinaryBlob(null);
      
      // Fetch the blob content using the API
      const fetchBlobContent = async () => {
        try {
          // Get the auth token from localStorage or context
          const token = localStorage.getItem('access_token') || '';
          if (!token) {
            setError('Authentication token not found');
            setLoading(false);
            return;
          }

          const response = await apiClient.getBlob(resource.id, token, resource.vmcp_id);
          if (response.success && response.data) {
            // Handle different response types based on content type
            if (resource.content_type && resource.content_type.startsWith('text/')) {
              // For text files, the backend returns the content directly
              if (response.data.content) {
                setBlobData(response.data.content);
                setBlobUrl('text-content');
              } else {
                setError('Text content not available');
              }
            } else if (response.data.binary && response.data.content) {
              // For binary files, the backend now returns base64 encoded content
              try {
                // Convert base64 to blob
                const binaryString = atob(response.data.content);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                  bytes[i] = binaryString.charCodeAt(i);
                }
                const blob = new Blob([bytes], { type: response.data.content_type });
                const objectUrl = URL.createObjectURL(blob);
                setBlobUrl(objectUrl);
                setBinaryBlob(blob); // Store the blob for download functionality
              } catch (err) {
                setError('Failed to process binary data');
              }
            } else {
              // For other types, just indicate we have the data
              setBlobUrl('data-available');
            }
          } else {
            setError(response.error || 'Failed to fetch blob content');
          }
        } catch (err) {
          setError('Failed to fetch blob content');
        } finally {
          setLoading(false);
        }
      };

      fetchBlobContent();
    }
  }, [isOpen, resource]);

  // Cleanup object URLs when component unmounts
  useEffect(() => {
    return () => {
      if (blobUrl && blobUrl.startsWith('blob:')) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [blobUrl]);

  if (!isOpen || !resource) return null;

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  const getContentTypeIcon = (contentType: string) => {
    if (contentType.startsWith('image/')) return <Image className="h-5 w-5" />;
    if (contentType.startsWith('video/')) return <FileVideo className="h-5 w-5" />;
    if (contentType.startsWith('audio/')) return <FileAudio className="h-5 w-5" />;
    if (contentType === 'application/pdf') return <FileText className="h-5 w-5" />;
    if (contentType.startsWith('text/')) return <FileText className="h-5 w-5" />;
    return <File className="h-5 w-5" />;
  };

  const getContentTypeLabel = (contentType: string) => {
    if (contentType.startsWith('image/')) return 'Image';
    if (contentType.startsWith('video/')) return 'Video';
    if (contentType.startsWith('audio/')) return 'Audio';
    if (contentType === 'application/pdf') return 'PDF Document';
    if (contentType.startsWith('text/')) return 'Text File';
    return 'File';
  };

  const handleDownload = async () => {
    try {
      setDownloading(true);
      
      // If we have the binary blob stored, use it directly
      if (binaryBlob) {
        const url = window.URL.createObjectURL(binaryBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = resource.original_filename || 'download';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        setDownloading(false);
        return;
      }
      
      // For text files, we have the content in blobData
      if (blobData && resource.content_type && resource.content_type.startsWith('text/')) {
        const blob = new Blob([blobData], { type: resource.content_type });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = resource.original_filename || 'download';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        setDownloading(false);
        return;
      }
      
      // Fallback: if we don't have the data, fetch it from the API
      const token = localStorage.getItem('access_token') || '';
      if (!token) {
        setError('Authentication token not found');
        setDownloading(false);
        return;
      }

      const response = await apiClient.downloadBlob(resource.id, token, resource.vmcp_id);
      if (response.success && response.data) {
        const blob = response.data;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = resource.original_filename || 'download';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        setError(response.error || 'Failed to download file');
      }
    } catch (err) {
      setError('Failed to download file');
    } finally {
      setDownloading(false);
    }
  };

  const renderContent = () => {
    if (!resource.content_type) {
      return (
        <div className="text-center py-8 text-muted-foreground">
          <File className="h-12 w-12 mx-auto mb-3 text-muted-foreground" />
          <p>Content type not specified</p>
          <p className="text-xs mt-2">Blob ID: {resource.id}</p>
        </div>
      );
    }

    if (!blobData && !blobUrl) {
      return (
        <div className="text-center py-8 text-muted-foreground">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto mb-3"></div>
          <p>Loading blob content...</p>
        </div>
      );
    }

    if (resource.content_type.startsWith('image/') && blobUrl && blobUrl !== 'text-content' && blobUrl !== 'data-available') {
      return (
        <div className="flex justify-center">
          <img
            src={blobUrl}
            alt={resource.original_filename}
            className="max-w-full max-h-96 object-contain rounded-lg border border-border"
            onLoad={() => setLoading(false)}
            onError={() => {
              setLoading(false);
              setError(`Failed to load image`);
            }}
          />
        </div>
      );
    }

    if (resource.content_type === 'application/pdf' && blobUrl && blobUrl !== 'text-content' && blobUrl !== 'data-available') {
      return (
        <div className="w-full h-96">
          <iframe
            src={blobUrl}
            className="w-full h-full border border-border rounded-lg"
            title={resource.original_filename}
            onLoad={() => setLoading(false)}
            onError={() => {
              setLoading(false);
              setError('Failed to load PDF');
            }}
          />
        </div>
      );
    }

    if (resource.content_type.startsWith('text/') && blobData) {
      return (
        <div className="w-full h-96 overflow-auto bg-muted/20 border border-border rounded-lg p-4">
          <pre className="whitespace-pre-wrap text-sm font-mono">
            {blobData}
          </pre>
        </div>
      );
    }

    // For other file types, show a download link
    return (
      <div className="text-center py-8">
        <File className="h-12 w-12 mx-auto mb-3 text-muted-foreground" />
        <p className="text-muted-foreground mb-4">This file type cannot be previewed</p>
        <p className="text-xs text-muted-foreground mb-4">Content Type: {resource.content_type}</p>
        <p className="text-xs text-muted-foreground mb-4">Blob ID: {resource.id}</p>
        <Button onClick={handleDownload}>
          <Download className="h-4 w-4 mr-2" />
          Download File
        </Button>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-background rounded-lg shadow-lg max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            {resource.content_type && getContentTypeIcon(resource.content_type)}
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                {resource.resource_name || resource.original_filename}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="text-xs">
                  {resource.content_type ? getContentTypeLabel(resource.content_type) : 'Unknown Type'}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {formatFileSize(resource.size)}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={downloading}
            >
              <Download className="h-4 w-4 mr-2" />
              {downloading ? 'Downloading...' : 'Download'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="p-4 overflow-auto max-h-[calc(90vh-120px)]">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
              <span className="ml-2 text-muted-foreground">Loading...</span>
            </div>
          )}

          {error && (
            <div className="text-center py-8 text-destructive">
              <p>{error}</p>
            </div>
          )}

          {!loading && !error && renderContent()}
        </div>

        {/* Footer with metadata */}
        <div className="p-4 border-t border-border bg-muted/20">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Original Name:</span>
              <p className="font-medium truncate">{resource.original_filename}</p>
            </div>
            {resource.filename && resource.filename !== resource.original_filename && (
              <div>
                <span className="text-muted-foreground">Filename:</span>
                <p className="font-medium truncate">{resource.filename}</p>
              </div>
            )}
            {resource.created_at && (
              <div>
                <span className="text-muted-foreground">Created:</span>
                <p className="font-medium">{formatDate(resource.created_at)}</p>
              </div>
            )}
            {resource.content_type && (
              <div>
                <span className="text-muted-foreground">MIME Type:</span>
                <p className="font-medium font-mono text-xs">{resource.content_type}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
