import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
  title?: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ 
  message, 
  onRetry,
  title = "Something went wrong"
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-lg border border-red-900/50 bg-red-950/20">
      <div className="p-3 bg-red-900/20 rounded-full mb-4">
        <AlertCircle className="w-8 h-8 text-red-500" />
      </div>
      <h3 className="text-lg font-medium text-red-400 mb-2">{title}</h3>
      <p className="text-gray-400 max-w-md mb-6">{message}</p>
      
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-red-900/30 hover:bg-red-900/50 text-red-300 rounded-md transition-colors border border-red-900/50 font-medium text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Try Again
        </button>
      )}
    </div>
  );
};
