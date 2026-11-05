import React from 'react';
import type { Course } from '../../types/course';
import { formatIsoTimestamp } from '../../utils/config';

interface CourseCardProps {
  course: Course;
  onSelect: (course: Course) => void;
  onDelete: (courseId: string) => Promise<void>;
  index?: number;
}

export const CourseCard: React.FC<CourseCardProps> = ({
  course,
  onSelect,
  onDelete,
  index = 0,
}) => {
  // Deterministic color theme cycle inspired by StudyMate
  const themes = [
    { banner: 'bg-forest-soft text-forest', badge: 'bg-forest text-paper', bar: 'bg-forest' },
    { banner: 'bg-coral-soft text-coral', badge: 'bg-coral text-white', bar: 'bg-coral' },
    { banner: 'bg-sage-soft text-[#365c3b]', badge: 'bg-[#4f6f52] text-white', bar: 'bg-[#4f6f52]' },
    { banner: 'bg-lilac-soft text-[#5c4e7c]', badge: 'bg-[#6b5b8f] text-white', bar: 'bg-[#6b5b8f]' },
  ];
  const theme = themes[index % themes.length];

  return (
    <div className="flex flex-col justify-between overflow-hidden rounded-2xl border border-line bg-paper-surface shadow-warm-sm transition-all duration-200 hover:-translate-y-1 hover:border-forest/40 hover:shadow-warm-md">
      {/* StudyMate Course Banner */}
      <div className={`relative flex h-24 items-center justify-between px-5 ${theme.banner}`}>
        {course.code ? (
          <span className={`rounded-md px-2.5 py-1 font-mono text-[11px] font-bold tracking-wider uppercase ${theme.badge}`}>
            {course.code}
          </span>
        ) : (
          <span className="text-xs font-bold uppercase tracking-wider opacity-70">
            Course Module
          </span>
        )}
        <span className="flex items-center gap-1.5 rounded-full bg-paper-surface/90 px-3 py-1 text-xs font-bold text-ink shadow-sm">
          <span>📄</span>
          <span>
            {course.document_count} {course.document_count === 1 ? 'PDF' : 'PDFs'}
          </span>
        </span>
      </div>

      {/* Card Body */}
      <div className="flex-1 p-5 sm:p-6 flex flex-col justify-between">
        <div>
          <h3 className="font-display text-lg font-semibold tracking-tight text-ink line-clamp-1">
            {course.title}
          </h3>
          <p className="mt-2 line-clamp-2 text-xs sm:text-sm text-ink-muted leading-relaxed">
            {course.description || 'Structured academic materials and lecture readings.'}
          </p>
        </div>

        {/* Progress bar decoration */}
        <div className="mt-5 pt-4 border-t border-line/60">
          <div className="flex items-center justify-between text-[11px] text-ink-muted mb-1.5 font-medium">
            <span>Material Readiness</span>
            <span className="font-bold text-ink">
              {course.document_count > 0 ? '100%' : '0%'}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-paper-deep">
            <div
              className={`h-full rounded-full ${course.document_count > 0 ? theme.bar : 'bg-line'}`}
              style={{ width: course.document_count > 0 ? '100%' : '5%' }}
            />
          </div>
        </div>
      </div>

      {/* Card Footer Actions */}
      <div className="flex items-center justify-between bg-paper/60 px-5 py-3.5 border-t border-line text-xs">
        <span className="text-[11px] text-ink-muted" title={course.created_at}>
          Added {formatIsoTimestamp(course.created_at)}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void onDelete(course.id)}
            className="rounded px-2.5 py-1.5 font-semibold text-coral hover:bg-coral-soft transition-colors"
          >
            Delete
          </button>
          <button
            type="button"
            onClick={() => onSelect(course)}
            className="inline-flex items-center gap-1 rounded-lg bg-forest px-3.5 py-1.5 font-semibold text-paper hover:bg-forest-hover shadow-warm-sm transition-all"
          >
            <span>Workspace</span>
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>
    </div>
  );
};
