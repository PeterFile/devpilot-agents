import React, { useState } from 'react';
import { useAgentState } from '../hooks/useAgentState';
import { ReviewBadge } from '../components/reviews/ReviewBadge';
import { Severity } from '../types';
import { Filter } from 'lucide-react';

export const Reviews: React.FC = () => {
    const { state, isLoading, error } = useAgentState();
    const [severityFilter, setSeverityFilter] = useState<Severity | 'all'>('all');

    if (isLoading) return <div className="p-8 flex justify-center text-gray-500">Loading reviews...</div>;
    if (error) return <div className="p-8 text-red-500 bg-red-50 rounded-lg m-4">Error: {error.message}</div>;
    if (!state) return <div className="p-8">No state available</div>;

    const filteredReviews = state.review_findings.filter(review => 
        severityFilter === 'all' || review.severity === severityFilter
    );

    return (
        <div className="max-w-4xl mx-auto">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold text-gray-900">Review Findings</h1>
                
                <div className="relative">
                    <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
                    <select
                        value={severityFilter}
                        onChange={(e) => setSeverityFilter(e.target.value as Severity | 'all')}
                        className="pl-9 pr-8 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    >
                        <option value="all">All Severities</option>
                        <option value="critical">Critical</option>
                        <option value="major">Major</option>
                        <option value="minor">Minor</option>
                        <option value="none">None</option>
                    </select>
                </div>
            </div>

            <div className="space-y-4">
                {filteredReviews.length > 0 ? (
                    filteredReviews.map((review, idx) => (
                        <div key={`${review.task_id}-${idx}`} className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
                            <div className="flex justify-between items-start mb-2">
                                <div className="flex items-center space-x-2">
                                    <span className="font-mono text-xs text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">
                                        {review.task_id}
                                    </span>
                                    <span className="text-sm font-medium text-gray-700">Reviewer: {review.reviewer}</span>
                                </div>
                                <ReviewBadge severity={review.severity} />
                            </div>
                            <h3 className="text-lg font-medium text-gray-900 mb-1">{review.summary}</h3>
                            <p className="text-gray-600 text-sm whitespace-pre-wrap">{review.details}</p>
                            <div className="mt-3 text-xs text-gray-400">
                                {new Date(review.created_at).toLocaleString()}
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 text-gray-500">
                        No review findings match your filter.
                    </div>
                )}
            </div>
        </div>
    );
};
