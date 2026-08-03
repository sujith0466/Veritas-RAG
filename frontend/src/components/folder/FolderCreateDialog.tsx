import React, { useState } from 'react';
import { useFolderStore } from '../../stores/folderStore';
import { useWorkspaceStore } from '../../stores/workspaceStore';

interface FolderCreateDialogProps {
  parentId: string | null;
  onClose: () => void;
  onSuccess?: () => void;
}

export const FolderCreateDialog: React.FC<FolderCreateDialogProps> = ({ parentId, onClose, onSuccess }) => {
  const [name, setName] = useState('');
  const { createFolder, isLoading, error, clearError } = useFolderStore();
  const { currentWorkspace } = useWorkspaceStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentWorkspace || !name.trim()) return;

    try {
      await createFolder(currentWorkspace.id, name, parentId);
      onSuccess?.();
      onClose();
    } catch (err) {
      // Error is handled by store
    }
  };

  return (
    <div className="dialog-overlay">
      <div className="dialog-content">
        <h3>Create New Folder</h3>
        {error && <div className="error-alert">{error}</div>}
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={name}
            onChange={(e) => { setName(e.target.value); clearError(); }}
            placeholder="Folder Name"
            maxLength={255}
            required
            autoFocus
          />
          <div className="dialog-actions">
            <button type="button" onClick={onClose} disabled={isLoading}>Cancel</button>
            <button type="submit" disabled={isLoading || !name.trim()}>
              {isLoading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
