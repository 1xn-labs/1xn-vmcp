import { useCallback } from 'react';
import { toast } from 'sonner';

export function useToast() {
  const success = useCallback((message: string, options?: { description?: string; duration?: number }) => {
    toast.success(message, options);
  }, []);

  const error = useCallback((message: string, options?: { description?: string; duration?: number }) => {
    toast.error(message, options);
  }, []);

  const info = useCallback((message: string, options?: { description?: string; duration?: number }) => {
    toast.info(message, options);
  }, []);

  const warning = useCallback((message: string, options?: { description?: string; duration?: number }) => {
    toast.warning(message, options);
  }, []);

  const loading = useCallback((message: string, options?: { description?: string }) => {
    return toast.loading(message, options);
  }, []);

  const promise = useCallback(<T>(
    promise: Promise<T>,
    options: {
      loading: string;
      success: string | ((data: T) => string);
      error: string | ((error: any) => string);
    }
  ) => {
    return toast.promise(promise, options);
  }, []);

  const dismiss = useCallback((toastId?: string | number) => {
    toast.dismiss(toastId);
  }, []);

  return {
    success,
    error,
    info,
    warning,
    loading,
    promise,
    dismiss,
    toast, // Export the raw toast function for advanced usage
  };
} 