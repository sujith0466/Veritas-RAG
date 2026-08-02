import React, { useState, useEffect } from 'react';
import { apiClient } from '../../api/client';
import { useParams } from 'react-router-dom';

export const WorkspaceDomainsPage: React.FC = () => {
  const [domains, setDomains] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { workspaceId } = useParams<{ workspaceId: string }>();

  const fetchDomains = async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const response = await apiClient.get(`/workspaces/${workspaceId}/domains`);
      setDomains(response.data);
    } catch (err: any) {
      setError(err.message || "Failed to load domains");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDomains();
  }, [workspaceId]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Domain Verification</h1>
      {error && <div className="text-red-500 mb-4">{error}</div>}
      
      {loading ? (
        <div className="text-gray-500">Loading...</div>
      ) : domains.length === 0 ? (
        <div className="text-gray-500">No domains verified yet.</div>
      ) : (
        <ul className="space-y-2">
          {domains.map(d => (
            <li key={d.id} className="p-4 bg-white dark:bg-gray-800 rounded shadow flex justify-between items-center">
              <div>
                <span className="font-semibold text-gray-900 dark:text-white">{d.domain_name}</span>
                <span className={`ml-3 px-2 py-1 text-xs rounded-full ${d.status === 'VERIFIED' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                  {d.status}
                </span>
                {d.is_primary && <span className="ml-2 text-xs text-blue-500 font-bold">PRIMARY</span>}
              </div>
            </li>
          ))}
        </ul>
      )}

      <button onClick={() => {}} className="mt-6 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded transition-colors shadow-sm">
        Add Domain
      </button>
    </div>
  );
};
