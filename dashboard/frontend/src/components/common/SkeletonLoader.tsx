import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface SkeletonProps {
  className?: string;
  count?: number;
}

export const SkeletonLoader: React.FC<SkeletonProps> = ({ 
  className,
  count = 1 
}) => {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div 
          key={i}
          className={twMerge(
            clsx("bg-gray-800/50 rounded-md h-4 w-full", className)
          )} 
        />
      ))}
    </div>
  );
};
