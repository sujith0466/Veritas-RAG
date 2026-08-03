import React, { useState } from 'react';
import { useFolderStore } from '../../stores/folderStore';
import { Folder } from '../../services/folderService';
import { FolderCreateDialog } from './FolderCreateDialog';
import { FolderRenameDialog } from './FolderRenameDialog';
import { useWorkspaceStore } from '../../stores/workspaceStore';

export const FolderTree: React.FC = () => {
  const { folders, softDeleteFolder } = useFolderStore();
  const { currentWorkspace } = useWorkspaceStore();
  
  const [createParentId, setCreateParentId] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  
  const [renameFolder, setRenameFolder] = useState<Folder | null>(null);

  if (!currentWorkspace) return null;

  const rootFolders = folders.filter(f => !f.parent_id);

  const handleDelete = async (folder: Folder) => {
    if (confirm(`Are you sure you want to delete ${folder.name}?`)) {
      await softDeleteFolder(currentWorkspace.id, folder.id, folder.version);
    }
  };

  const renderFolder = (folder: Folder) => {
    const children = folders.filter(f => f.parent_id === folder.id);
    return (
      <div key={folder.id} className="folder-node" style={{ marginLeft: 20 }}>
        <div className="folder-row">
          <span>📁 {folder.name}</span>
          <div className="folder-actions">
            <button onClick={() => { setCreateParentId(folder.id); setIsCreateOpen(true); }}>New Subfolder</button>
            <button onClick={() => setRenameFolder(folder)}>Rename</button>
            <button onClick={() => handleDelete(folder)}>Delete</button>
          </div>
        </div>
        {children.length > 0 && (
          <div className="folder-children">
            {children.map(renderFolder)}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="folder-tree">
      <div className="folder-tree-header">
        <h2>Folders</h2>
        <button onClick={() => { setCreateParentId(null); setIsCreateOpen(true); }}>New Root Folder</button>
      </div>
      
      <div className="folder-list">
        {rootFolders.length === 0 ? (
          <p>No folders yet.</p>
        ) : (
          rootFolders.map(renderFolder)
        )}
      </div>

      {isCreateOpen && (
        <FolderCreateDialog 
          parentId={createParentId} 
          onClose={() => setIsCreateOpen(false)} 
        />
      )}

      {renameFolder && (
        <FolderRenameDialog 
          folder={renameFolder} 
          onClose={() => setRenameFolder(null)} 
        />
      )}
    </div>
  );
};
