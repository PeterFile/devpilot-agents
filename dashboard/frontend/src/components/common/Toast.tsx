import React, { useEffect } from 'react';
import { X, CheckCircle, AlertTriangle, Info, AlertOctagon } from 'lucide-react';
import { clsx } from 'clsx';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastProps {
  id: string;
  type: ToastType;
  message: string;
  onDismiss: (id: string) => void;
  duration?: number;
}

const ICONS = {
  success: CheckCircle,
  error: AlertOctagon,
  warning: AlertTriangle,
  info: Info,
};

const STYLES = {
  success: "bg-green-950/90 border-green-900 text-green-200",
  error: "bg-red-950/90 border-red-900 text-red-200",
  warning: "bg-yellow-950/90 border-yellow-900 text-yellow-200",
  info: "bg-blue-950/90 border-blue-900 text-blue-200",
};

export const Toast: React.FC<ToastProps> = ({ 
  id, 
  type, 
  message, 
  onDismiss, 
  duration = 5000 
}) => {
  const Icon = ICONS[type];

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => onDismiss(id), duration);
      return () => clearTimeout(timer);
    }
  }, [id, duration, onDismiss]);

  return (
    <div className={clsx(
      "flex items-start gap-3 p-4 rounded-lg border shadow-lg backdrop-blur-sm max-w-sm w-full animate-in slide-in-from-right-full transition-all duration-300 pointer-events-auto",
      STYLES[type]
    )}>
      <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
      <div className="flex-1 text-sm font-medium">{message}</div>
      <button 
        onClick={() => onDismiss(id)}
        className="text-current opacity-60 hover:opacity-100 transition-opacity"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
