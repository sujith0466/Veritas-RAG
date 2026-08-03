import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Trash2, Plus, Save } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface MetadataEditorProps {
  documentId: string;
  initialMetadata: Record<string, any>;
  onSave: (metadata: Record<string, any>) => Promise<void>;
  onDeleteKey?: (key: string) => Promise<void>;
}

export function MetadataEditor({
  documentId,
  initialMetadata,
  onSave,
  onDeleteKey,
}: MetadataEditorProps) {
  const [metadata, setMetadata] = useState<Record<string, any>>(initialMetadata || {});
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const { toast } = useToast();

  const handleAdd = () => {
    if (!newKey.trim()) {
      toast({ title: 'Key required', description: 'Metadata key cannot be empty.', variant: 'destructive' });
      return;
    }
    if (Object.keys(metadata).length >= 100) {
      toast({ title: 'Limit reached', description: 'Maximum 100 metadata keys allowed.', variant: 'destructive' });
      return;
    }
    if (newKey.startsWith('__')) {
      toast({ title: 'Reserved key', description: 'Keys starting with "__" are reserved.', variant: 'destructive' });
      return;
    }

    setMetadata((prev) => ({ ...prev, [newKey]: newValue }));
    setNewKey('');
    setNewValue('');
  };

  const handleRemove = async (key: string) => {
    try {
      if (onDeleteKey) {
        await onDeleteKey(key);
      }
      setMetadata((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } catch (err: any) {
      toast({ title: 'Failed to remove', description: err.message, variant: 'destructive' });
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(metadata);
      toast({ title: 'Metadata updated', description: 'Successfully saved metadata.' });
    } catch (err: any) {
      toast({ title: 'Update failed', description: err.message, variant: 'destructive' });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-lg flex justify-between items-center">
          Document Metadata
          <span className="text-sm text-muted-foreground">{Object.keys(metadata).length} / 100 tags</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <Label>Key</Label>
            <Input
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="e.g. department"
              maxLength={64}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label>Value</Label>
            <Input
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder="e.g. engineering"
              maxLength={512}
            />
          </div>
          <Button onClick={handleAdd} type="button" variant="secondary">
            <Plus className="w-4 h-4 mr-2" />
            Add
          </Button>
        </div>

        <div className="space-y-2 mt-4">
          {Object.entries(metadata).map(([key, val]) => (
            <div key={key} className="flex items-center justify-between p-2 border rounded-md text-sm">
              <div className="flex gap-4">
                <span className="font-semibold text-muted-foreground w-32 truncate">{key}</span>
                <span className="truncate max-w-[200px]" title={String(val)}>
                  {String(val)}
                </span>
              </div>
              <Button variant="ghost" size="icon" onClick={() => handleRemove(key)}>
                <Trash2 className="w-4 h-4 text-destructive" />
              </Button>
            </div>
          ))}
          {Object.keys(metadata).length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">No metadata tags added yet.</p>
          )}
        </div>

        <div className="flex justify-end pt-4 border-t">
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save All Changes'}
            {!isSaving && <Save className="w-4 h-4 ml-2" />}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
