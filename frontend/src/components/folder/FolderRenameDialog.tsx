import React, { useState } from 'react';
import { useFolderStore } from '../../stores/folderStore';
import { useWorkspaceStore } from '../../stores/workspaceStore';
import { Folder } from '../../services/folderService';

interface FolderRenameDialogProps {
  folder: Folder;
  onClose: () => void;
  onSuccess?: () => void;
}

export const FolderRenameDialog: React.FC<FolderRenameDialogProps> = ({ folder, onClose, onSuccess }) => {
  const [name, setName] = useState(folder.name);
  const { renameFolder, isLoading, error, clearError } = useFolderStore();
  const { currentWorkspace } = useWorkspaceStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentWorkspace || !name.trim()) return;

    try {
      await renameFolder(currentWorkspace.id, folder.id, name, folder.version);
      onSuccess?.();
      onClose();
    } catch (err) {
      // Error is handled by store
    }
  };

  return (
    <div className="dialog-overlay">
      <div className="dialog-content">
        <h3>Rename Folder</h3>
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
            <button type="submit" disabled={isLoading || !name.trim() || name === folder.name}>
              {isLoading ? 'Renaming...' : 'Rename'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
