import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { Building2, Sparkles, ArrowLeft, Loader2, AlertCircle } from 'lucide-react';

export const CreateWorkspace: React.FC = () => {
  const navigate = useNavigate();
  const { createWorkspace, isLoading, error, clearError } = useWorkspaceStore();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setClientError(null);
    clearError();

    const trimmedName = name.trim();
    if (!trimmedName) {
      setClientError('Workspace name is required.');
      return;
    }

    if (trimmedName.length < 2) {
      setClientError('Workspace name must be at least 2 characters long.');
      return;
    }

    if (trimmedName.length > 100) {
      setClientError('Workspace name cannot exceed 100 characters.');
      return;
    }

    // Double-submit protection
    if (isSubmitting || isLoading) return;

    try {
      setIsSubmitting(true);
      await createWorkspace(trimmedName, description.trim() || undefined);
      // Active workspace session context is authoritatively established by createWorkspace -> switchWorkspace
      navigate('/dashboard', { replace: true });
    } catch {
      // Error is stored in workspaceStore and rendered below
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeError = clientError || error;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8 text-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <button
          type="button"
          onClick={() => navigate('/onboarding')}
          className="inline-flex items-center text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors mb-6 group"
        >
          <ArrowLeft className="h-4 w-4 mr-1.5 transition-transform group-hover:-translate-x-1" />
          Back to Onboarding
        </button>

        <div className="flex justify-center mb-4">
          <div className="h-14 w-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-inner">
            <Building2 className="h-7 w-7" />
          </div>
        </div>

        <h1 className="text-center text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Create a New Workspace
        </h1>
        <p className="mt-2 text-center text-xs sm:text-sm text-slate-400">
          Set up an isolated multi-tenant organization for your knowledge, documents, and AI assistants.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-900 border border-slate-800 py-8 px-6 shadow-2xl rounded-2xl sm:px-10 backdrop-blur-xl">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {activeError && (
              <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/50 flex items-start space-x-3 text-red-200">
                <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
                <div className="text-xs leading-relaxed">{activeError}</div>
              </div>
            )}

            <div>
              <label htmlFor="workspace-name" className="block text-xs font-medium uppercase tracking-wider text-slate-300">
                Workspace Name <span className="text-indigo-400">*</span>
              </label>
              <div className="mt-2">
                <input
                  id="workspace-name"
                  name="name"
                  type="text"
                  required
                  autoFocus
                  maxLength={100}
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (activeError) {
                      setClientError(null);
                      clearError();
                    }
                  }}
                  className="block w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm transition-all"
                  placeholder="e.g. Acme Research Lab"
                  disabled={isLoading || isSubmitting}
                />
              </div>
              <p className="mt-1.5 text-xs text-slate-500">
                A public display name for your organization or team.
              </p>
            </div>

            <div>
              <label htmlFor="workspace-description" className="block text-xs font-medium uppercase tracking-wider text-slate-300">
                Description <span className="text-slate-500 font-normal lowercase">(optional)</span>
              </label>
              <div className="mt-2">
                <textarea
                  id="workspace-description"
                  name="description"
                  rows={3}
                  maxLength={500}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="block w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm transition-all resize-none"
                  placeholder="Brief description of this workspace's purpose..."
                  disabled={isLoading || isSubmitting}
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading || isSubmitting || !name.trim()}
                className="w-full flex justify-center items-center py-2.5 px-4 border border-transparent rounded-xl shadow-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {isLoading || isSubmitting ? (
                  <span className="flex items-center space-x-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Creating & Provisioning...</span>
                  </span>
                ) : (
                  <span className="flex items-center space-x-2">
                    <Sparkles className="h-4 w-4" />
                    <span>Create Workspace</span>
                  </span>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
