import React, { useState } from 'react';
import { AlertBanner } from '../../components/ui/AlertBanner';

interface CreateCourseFormProps {
  isSubmitting: boolean;
  onCreate: (data: {
    title: string;
    code?: string;
    description?: string;
  }) => Promise<void>;
}

export const CreateCourseForm: React.FC<CreateCourseFormProps> = ({
  isSubmitting,
  onCreate,
}) => {
  const [title, setTitle] = useState('');
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setValidationError('Course title is required.');
      return;
    }

    await onCreate({
      title: trimmedTitle,
      code: code.trim() || undefined,
      description: description.trim() || undefined,
    });
    setTitle('');
    setCode('');
    setDescription('');
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="rounded-2xl border border-line bg-paper-surface p-6 sm:p-7 shadow-warm-sm"
    >
      <div className="flex items-center gap-3 mb-2">
        <span
          className="flex h-7 w-7 items-center justify-center rounded-md bg-forest-soft text-forest text-xs font-bold"
          aria-hidden="true"
        >
          ✦
        </span>
        <h3 className="font-display text-lg font-semibold tracking-tight text-ink">
          Create New Course Workspace
        </h3>
      </div>
      <p className="text-xs sm:text-sm text-ink-muted leading-relaxed">
        Organize your lecture slides, textbook chapters, and study sessions by course module.
      </p>

      {validationError && (
        <div className="mt-4">
          <AlertBanner
            variant="error"
            message={validationError}
            onDismiss={() => setValidationError(null)}
          />
        </div>
      )}

      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label
            htmlFor="course-title"
            className="block text-xs font-bold uppercase tracking-wider text-ink-muted"
          >
            Course Title <span className="text-coral">*</span>
          </label>
          <input
            id="course-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Distributed Systems"
            maxLength={200}
            className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-all placeholder:text-ink-subtle focus:border-forest focus:ring-2 focus:ring-forest/15"
          />
        </div>

        <div>
          <label
            htmlFor="course-code"
            className="block text-xs font-bold uppercase tracking-wider text-ink-muted"
          >
            Course Code
          </label>
          <input
            id="course-code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="e.g., CS-401"
            maxLength={50}
            className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-all placeholder:text-ink-subtle focus:border-forest focus:ring-2 focus:ring-forest/15"
          />
        </div>

        <div className="sm:col-span-3">
          <label
            htmlFor="course-description"
            className="block text-xs font-bold uppercase tracking-wider text-ink-muted"
          >
            Description
          </label>
          <textarea
            id="course-description"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Consensus, replication, fault tolerance, and vector clocks..."
            className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-all placeholder:text-ink-subtle focus:border-forest focus:ring-2 focus:ring-forest/15"
          />
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex items-center gap-2 rounded-lg bg-forest px-5 py-2.5 text-xs sm:text-sm font-bold text-paper shadow-warm-sm transition-all hover:bg-forest-hover disabled:opacity-50"
        >
          {isSubmitting ? 'Creating Course…' : 'Create Course'}
        </button>
      </div>
    </form>
  );
};
