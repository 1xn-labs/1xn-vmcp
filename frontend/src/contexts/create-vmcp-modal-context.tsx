
import React, { createContext, useContext, useState, ReactNode } from 'react';

interface CreateVMCPModalContextType {
  isOpen: boolean;
  openModal: () => void;
  closeModal: () => void;
}

const CreateVMCPModalContext = createContext<CreateVMCPModalContextType | undefined>(undefined);

export function CreateVMCPModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  const openModal = () => {
    console.log('Opening create vMCP modal via context, current state:', isOpen);
    setIsOpen(true);
    console.log('State set to true');
  };

  const closeModal = () => {
    console.log('Closing create vMCP modal via context, current state:', isOpen);
    setIsOpen(false);
    console.log('State set to false');
  };

  console.log('CreateVMCPModalProvider rendered, isOpen:', isOpen);

  return (
    <CreateVMCPModalContext.Provider value={{ isOpen, openModal, closeModal }}>
      {children}
    </CreateVMCPModalContext.Provider>
  );
}

export function useCreateVMCPModal() {
  const context = useContext(CreateVMCPModalContext);
  if (context === undefined) {
    throw new Error('useCreateVMCPModal must be used within a CreateVMCPModalProvider');
  }
  return context;
}
