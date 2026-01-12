import React from 'react';
import { Severity } from '../../types';

interface ReviewBadgeProps {
    severity: Severity;
}

export const ReviewBadge: React.FC<ReviewBadgeProps> = ({ severity }) => {
    const getColorClasses = (severity: Severity) => {
        switch (severity) {
            case 'critical': return 'bg-red-100 text-red-800 border-red-200';
            case 'major': return 'bg-orange-100 text-orange-800 border-orange-200';
            case 'minor': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
            case 'none': return 'bg-green-100 text-green-800 border-green-200';
            default: return 'bg-gray-100 text-gray-800';
        }
    };

    return (
        <span className={`px-2 py-0.5 rounded text-xs font-medium border capitalize ${getColorClasses(severity)}`}>
            {severity}
        </span>
    );
};
