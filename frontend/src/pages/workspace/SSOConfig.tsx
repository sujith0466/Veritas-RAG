import React, { useState, useEffect } from 'react';
import { apiClient } from '../../api/client';
import { useParams } from 'react-router-dom';

export const SSOConfigPage: React.FC = () => {
  const [idps, setIdps] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { workspaceId } = useParams<{ workspaceId: string }>();

  const fetchIdps = async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const response = await apiClient.get(`/workspaces/${workspaceId}/idp`);
      setIdps(response.data);
    } catch (err: any) {
      setError(err.message || "Failed to load IdPs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIdps();
  }, [workspaceId]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">SSO Configuration</h1>
      {error && <div className="text-red-500 mb-4">{error}</div>}
      
      {loading ? (
        <div className="text-gray-500">Loading...</div>
      ) : idps.length === 0 ? (
        <div className="text-gray-500">No Identity Providers configured.</div>
      ) : (
        <ul className="space-y-4">
          {idps.map(idp => (
            <li key={idp.id} className="p-4 bg-white dark:bg-gray-800 rounded shadow border border-gray-100 dark:border-gray-700">
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold text-lg text-gray-900 dark:text-white">{idp.name}</span>
                <span className={`px-2 py-1 text-xs rounded-full ${idp.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                  {idp.is_active ? 'ACTIVE' : 'INACTIVE'}
                </span>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <p>Type: <span className="font-medium">{idp.type}</span></p>
                <p>Issuer: <span className="font-medium">{idp.entity_id_issuer}</span></p>
                {idp.jit_enabled && <p className="text-blue-500 text-xs mt-1">JIT Enabled</p>}
              </div>
            </li>
          ))}
        </ul>
      )}

      <button onClick={() => {}} className="mt-6 bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded transition-colors shadow-sm">
        Configure SSO
      </button>
    </div>
  );
};
