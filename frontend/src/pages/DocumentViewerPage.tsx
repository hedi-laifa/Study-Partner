import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, navigate } from '../app/router';
import { PageHeader } from '../components/ui/Layout';
import { DocumentStatusBadge } from '../components/ui/StatusBadge';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States';
import { useAsyncData } from '../hooks/useAsyncData';
import {
  fetchDocument,
  fetchDocumentChunks,
  fetchDocumentFile,
} from '../services/courseService';

interface Props {
  courseId: string;
  documentId: string;
  userId: string;
  page: number | null;
}

/** PDF viewer with a text "source preview" of the extracted passages for the selected page. */
export const DocumentViewerPage: React.FC<Props> = ({ courseId, documentId, userId, page }) => {
  const docLoader = useCallback(() => fetchDocument(documentId, userId), [documentId, userId]);
  const chunkLoader = useCallback(() => fetchDocumentChunks(documentId, userId), [documentId, userId]);
  const doc = useAsyncData(docLoader);
  const chunks = useAsyncData(chunkLoader);

  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pageInput, setPageInput] = useState<string>(page ? String(page) : '1');

  useEffect(() => {
    let revoked = false;
    let url: string | null = null;
    setPdfUrl(null);
    setPdfError(null);
    fetchDocumentFile(documentId, userId)
      .then((blob) => {
        if (revoked) return;
        url = URL.createObjectURL(blob);
        setPdfUrl(url);
      })
      .catch((err) => {
        if (!revoked) setPdfError(err instanceof Error ? err.message : 'Could not load the PDF.');
      });
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId, userId]);

  useEffect(() => {
    setPageInput(page ? String(page) : '1');
  }, [page]);

  const pageCount = doc.data?.page_count ?? null;
  const currentPage = page ?? 1;

  const passages = useMemo(() => {
    const all = chunks.data ?? [];
    if (!page) return all;
    return all.filter((c) => {
      const start = c.page_start ?? c.page_number ?? 0;
      const end = c.page_end ?? start;
      return page >= start && page <= end;
    });
  }, [chunks.data, page]);

  const goToPage = (e: React.FormEvent) => {
    e.preventDefault();
    const n = Number.parseInt(pageInput, 10);
    if (!Number.isFinite(n) || n < 1 || (pageCount && n > pageCount)) return;
    navigate(`/courses/${courseId}/documents/${documentId}?page=${n}`, { replace: true });
  };

  if (doc.isLoading && !doc.data) return <LoadingState label="Loading document…" />;
  if (doc.error && !doc.data) {
    return (
      <div className="space-y-4">
        <Link to={`/courses/${courseId}/documents`} className="text-xs font-semibold text-coral hover:underline">
          ← Back to documents
        </Link>
        <ErrorState message={doc.error} onRetry={() => void doc.reload()} title="Could not open this document" />
      </div>
    );
  }
  if (!doc.data) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={
          <Link to={`/courses/${courseId}/documents`} className="font-semibold text-coral hover:underline">
            ← Back to documents
          </Link>
        }
        title={doc.data.filename}
        description={`${pageCount ?? '?'} page(s) · ${doc.data.chunk_count} indexed passage(s)`}
        actions={<DocumentStatusBadge status={doc.data.status} />}
      />

      {doc.data.extraction_warnings.length > 0 && (
        <ul className="list-disc space-y-1 rounded-xl border border-coral/30 bg-coral/10 p-3 pl-7 text-xs text-ink">
          {doc.data.extraction_warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <section aria-label="PDF viewer" className="space-y-3 lg:col-span-3">
          <form onSubmit={goToPage} className="flex flex-wrap items-end gap-2">
            <div>
              <label htmlFor="viewer-page" className="block text-xs font-semibold uppercase tracking-wider text-ink/70">
                Go to page{pageCount ? ` (1–${pageCount})` : ''}
              </label>
              <input
                id="viewer-page"
                inputMode="numeric"
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value.replace(/\D/g, ''))}
                className="mt-1 w-24 rounded-xl border border-line bg-surface px-3 py-1.5 text-sm text-ink shadow-warm-sm focus:border-forest focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="rounded-xl border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink shadow-warm-sm hover:bg-paper"
            >
              Go
            </button>
            {pdfUrl && (
              <a
                href={pdfUrl}
                target="_blank"
                rel="noreferrer"
                className="ml-auto text-xs font-semibold text-coral hover:underline"
              >
                Open in new tab ↗
              </a>
            )}
          </form>

          {pdfError ? (
            <ErrorState message={pdfError} title="PDF unavailable" />
          ) : !pdfUrl ? (
            <LoadingState label="Loading PDF…" />
          ) : (
            <iframe
              key={`${pdfUrl}-${currentPage}`}
              title={`PDF: ${doc.data.filename}`}
              src={`${pdfUrl}#page=${currentPage}`}
              className="h-[72vh] w-full rounded-2xl border border-line bg-surface shadow-warm-sm"
            />
          )}
          <p className="text-xs text-ink/60">
            If your browser cannot display PDFs inline, use the extracted passages beside the viewer or open the file in a new tab.
          </p>
        </section>

        <section
          aria-label="Source preview"
          data-testid="source-preview"
          className="space-y-3 rounded-2xl border border-line bg-surface p-4 shadow-warm-sm lg:col-span-2"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line pb-3">
            <h2 className="font-display text-base font-bold text-ink">
              {page ? `Passages on page ${page}` : 'Extracted passages'}
            </h2>
            {page && (
              <button
                type="button"
                onClick={() => navigate(`/courses/${courseId}/documents/${documentId}`, { replace: true })}
                className="text-xs font-semibold text-coral hover:underline"
              >
                Show all
              </button>
            )}
          </div>
          {chunks.isLoading && !chunks.data ? (
            <LoadingState label="Loading passages…" />
          ) : chunks.error && !chunks.data ? (
            <ErrorState message={chunks.error} onRetry={() => void chunks.reload()} />
          ) : passages.length === 0 ? (
            <EmptyState
              title={page ? `No indexed text on page ${page}` : 'No extracted text'}
              description="This page may be blank or scanned without selectable text."
            />
          ) : (
            <ul className="max-h-[66vh] space-y-2.5 overflow-y-auto pr-1">
              {passages.map((c) => (
                <li key={c.id} className="rounded-xl border border-line bg-paper/40 p-3 text-xs shadow-warm-sm transition-all hover:border-forest/30">
                  <div className="mb-1 flex items-center justify-between gap-2 text-[11px] text-ink/60">
                    <span className="font-mono font-semibold text-forest">
                      {c.page_start === c.page_end || c.page_end === null
                        ? `p. ${c.page_start ?? c.page_number}`
                        : `pp. ${c.page_start}–${c.page_end}`}
                    </span>
                    {c.section_title && <span className="truncate font-medium">{c.section_title}</span>}
                  </div>
                  <p className="whitespace-pre-wrap leading-relaxed text-ink/90">{c.chunk_text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
};
