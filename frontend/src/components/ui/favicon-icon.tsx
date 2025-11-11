
import React, { useState } from 'react';
import { getBaseUrl, getFaviconUrl } from '@/lib/favicon';
import { ServerIcon } from 'lucide-react';

interface FaviconIconProps {
  url?: string;
  faviconUrl?: string;
  className?: string;
  size?: number;
}

export function FaviconIcon({ 
  url, 
  faviconUrl,
  className = "h-8 w-8", 
  size = 32 
}: FaviconIconProps) {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  // If faviconUrl is provided, use it directly
  const shouldShowFavicon = faviconUrl && !imageError;

  const handleImageError = () => {
    setImageError(true);
  };

  const handleImageLoad = () => {
    setImageLoaded(true);
    setImageError(false);
  };

  return (
    <div className={`${className} rounded-lg flex items-center justify-center shrink-0 overflow-hidden`}>
      {!imageLoaded && (
        <ServerIcon className="h-4 w-4 text-muted-foreground" />
      )}
      {shouldShowFavicon && (
        <img
          src={faviconUrl}
          alt={`${faviconUrl} favicon`}
          className={`w-full h-full object-contain ${imageLoaded ? 'block' : 'hidden'}`}
          onLoad={handleImageLoad}
          onError={handleImageError}
          style={{ width: size, height: size }}
        />
      )}
    </div>
  );
}
