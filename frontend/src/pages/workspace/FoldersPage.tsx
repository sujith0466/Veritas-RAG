import React, { useEffect } from 'react';
import { useWorkspaceStore } from '../../stores/workspaceStore';
import { useFolderStore } from '../../stores/folderStore';
import { FolderTree } from '../../components/folder/FolderTree';

export const FoldersPage: React.FC = () => {
  const { currentWorkspace } = useWorkspaceStore();
  const { error, clearError } = useFolderStore();

  useEffect(() => {
    // In a real app we'd fetch the initial folders from API here.
    // For now, it's just local state for creation
    return () => {
      clearError();
    };
  }, [clearError]);

  if (!currentWorkspace) {
    return <div>Select a workspace to manage folders.</div>;
  }

  return (
    <div className="folders-page">
      <h1>Document Folders</h1>
      {error && <div className="error-banner">{error}</div>}
      
      <div className="folders-container">
        <FolderTree />
      </div>
    </div>
  );
};
