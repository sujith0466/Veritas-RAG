import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useWorkspaceStore } from '../../stores/workspaceStore';

export const EditWorkspace: React.FC = () => {
  const navigate = useNavigate();
  const { slug } = useParams<{ slug: string }>();
  const { workspaces, currentWorkspace, updateWorkspace, isLoading, error } = useWorkspaceStore();
  
  const workspace = workspaces.find(w => w.slug === slug) || currentWorkspace;

  const [name, setName] = useState(workspace?.name || '');
  const [description, setDescription] = useState('');
  
  // Track original values to disable save button when unchanged
  const [originalName, setOriginalName] = useState(workspace?.name || '');
  const [originalDescription, setOriginalDescription] = useState('');

  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);
  const [confirmationName, setConfirmationName] = useState('');
  const [archiveReason, setArchiveReason] = useState('');

  const { archiveWorkspace, restoreWorkspace } = useWorkspaceStore();

  useEffect(() => {
    if (workspace) {
      setName(workspace.name);
      setOriginalName(workspace.name);
      // If we add description to workspace interface in future
      // setDescription(workspace.description || '');
      // setOriginalDescription(workspace.description || '');
    }
  }, [workspace]);

  const handleArchive = async () => {
    if (!workspace) return;
    try {
      await archiveWorkspace(workspace.id, workspace.updated_at, confirmationName, archiveReason);
      setIsArchiveModalOpen(false);
      setConfirmationName('');
      setArchiveReason('');
    } catch (err) {
      // Error is handled in store
    }
  };

  const handleRestore = async () => {
    if (!workspace) return;
    try {
      await restoreWorkspace(workspace.id, workspace.updated_at);
    } catch (err) {
      // Error is handled in store
    }
  };

  const hasChanges = name !== originalName || description !== originalDescription;

  if (!workspace) {
    return <div className="p-8">Workspace not found</div>;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasChanges) return;

    try {
      await updateWorkspace(workspace.id, workspace.updated_at, name, description);
      // On success, we could show a toast or just update state (handled in store)
      // and update our originals
      setOriginalName(name);
      setOriginalDescription(description);
      
      navigate(`/w/${workspace.slug}/dashboard`);
    } catch (err: any) {
      // Error handled in store, but we can do local specific handling if needed
      if (err?.response?.status === 409) {
        // Conflict - maybe reload data
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
          Workspace Settings
        </h2>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50 border-l-4 border-red-400 p-4">
                <div className="flex">
                  <div className="ml-3">
                    <p className="text-sm text-red-700">{error}</p>
                    {error.includes("another user") && (
                       <button 
                         type="button"
                         onClick={() => window.location.reload()}
                         className="mt-2 text-sm text-red-700 underline"
                       >
                         Reload latest data
                       </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Workspace Name
              </label>
              <div className="mt-1">
                <input
                  id="name"
                  name="name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div>
              <label htmlFor="slug" className="block text-sm font-medium text-gray-700">
                Workspace URL (Slug)
              </label>
              <div className="mt-1">
                <input
                  id="slug"
                  name="slug"
                  type="text"
                  value={workspace.slug}
                  disabled
                  className="appearance-none block w-full px-3 py-2 border border-gray-200 bg-gray-50 rounded-md shadow-sm text-gray-500 sm:text-sm"
                  title="Workspace slug cannot be changed"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">The workspace slug is permanent and cannot be changed.</p>
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <div className="mt-1">
                <textarea
                  id="description"
                  name="description"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading || !hasChanges || !name.trim() || workspace.status === 'ARCHIVED'}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>

        {/* Danger Zone */}
        <div className="mt-8 bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10 border border-red-200">
          <h3 className="text-lg leading-6 font-medium text-red-600 mb-4">Danger Zone</h3>
          
          {workspace.status === 'ACTIVE' && (
            <div>
              <p className="text-sm text-gray-500 mb-4">
                Archiving this workspace will pause all operations and revoke access to it. Data will be preserved.
              </p>
              <button
                type="button"
                onClick={() => setIsArchiveModalOpen(true)}
                className="inline-flex justify-center py-2 px-4 border border-red-300 rounded-md shadow-sm text-sm font-medium text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                Archive Workspace
              </button>
            </div>
          )}

          {workspace.status === 'ARCHIVED' && (
            <div>
              <p className="text-sm text-gray-500 mb-4">
                This workspace is currently archived. Restore it to resume operations.
              </p>
              <button
                type="button"
                onClick={handleRestore}
                disabled={isLoading}
                className="inline-flex justify-center py-2 px-4 border border-green-300 rounded-md shadow-sm text-sm font-medium text-green-700 bg-white hover:bg-green-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
              >
                Restore Workspace
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Archive Modal */}
      {isArchiveModalOpen && (
        <div className="fixed z-10 inset-0 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={() => setIsArchiveModalOpen(false)}></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div>
                <div className="mt-3 text-center sm:mt-5">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Archive Workspace
                  </h3>
                  <div className="mt-2 text-left">
                    <p className="text-sm text-gray-500 mb-4">
                      Are you sure you want to archive <strong>{workspace.name}</strong>? Please type the name of the workspace to confirm.
                    </p>
                    <input
                      type="text"
                      className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm mb-4"
                      placeholder={workspace.name}
                      value={confirmationName}
                      onChange={(e) => setConfirmationName(e.target.value)}
                    />
                    <label className="block text-sm font-medium text-gray-700 mb-1">Reason (Optional)</label>
                    <input
                      type="text"
                      className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm"
                      placeholder="e.g. End of project"
                      value={archiveReason}
                      onChange={(e) => setArchiveReason(e.target.value)}
                    />
                  </div>
                </div>
              </div>
              <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                <button
                  type="button"
                  disabled={confirmationName !== workspace.name || isLoading}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:col-start-2 sm:text-sm disabled:opacity-50"
                  onClick={handleArchive}
                >
                  Confirm Archive
                </button>
                <button
                  type="button"
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:col-start-1 sm:text-sm"
                  onClick={() => setIsArchiveModalOpen(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
