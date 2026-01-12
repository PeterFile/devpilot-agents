import React from 'react';
import { AlertTriangle, PauseCircle } from 'lucide-react';
import { clsx } from 'clsx';

interface BannerProps {
  message: string;
  type?: 'warning' | 'error' | 'info';
}

export const Banner: React.FC<BannerProps> = ({ message, type = 'warning' }) => {
  return (
    <div className={clsx(
      "w-full px-4 py-3 flex items-center justify-center gap-2 text-sm font-medium",
      type === 'warning' && "bg-yellow-900/20 text-yellow-500 border-b border-yellow-900/30",
      type === 'error' && "bg-red-900/20 text-red-500 border-b border-red-900/30",
      type === 'info' && "bg-blue-900/20 text-blue-400 border-b border-blue-900/30"
    )}>
      {type === 'warning' && <AlertTriangle className="w-4 h-4" />}
      {type === 'info' && <PauseCircle className="w-4 h-4" />}
      <span>{message}</span>
    </div>
  );
};
