import React, { useState } from 'react';
import { DocumentStatusBadge } from '../../components/ui/StatusBadge';
import type { CourseDocument, DocumentChunk } from '../../types/course';
import { formatIsoTimestamp } from '../../utils/config';

interface DocumentListProps {
  documents: CourseDocument[];
  onDeleteDocument: (documentId: string) => Promise<void>;
  onInspectChunks: (documentId: string) => Promise<DocumentChunk[]>;
  onPreviewDocument?: (documentId: string) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  onDeleteDocument,
  onInspectChunks,
  onPreviewDocument,
}) => {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [chunksByDoc, setChunksByDoc] = useState<Record<string, DocumentChunk[]>>({});
  const [loadingChunksId, setLoadingChunksId] = useState<string | null>(null);

  const handleDelete = async (docId: string) => {
    setDeletingId(docId);
    try {
      await onDeleteDocument(docId);
      if (expandedDocId === docId) {
        setExpandedDocId(null);
      }
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleChunks = async (docId: string) => {
    if (expandedDocId === docId) {
      setExpandedDocId(null);
      return;
    }
    setExpandedDocId(docId);
    if (!chunksByDoc[docId]) {
      setLoadingChunksId(docId);
      try {
        const fetched = await onInspectChunks(docId);
        setChunksByDoc((prev) => ({ ...prev, [docId]: fetched }));
      } finally {
        setLoadingChunksId(null);
      }
    }
  };

  if (documents.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-paper-surface/60 p-8 text-center shadow-warm-sm">
        <p className="font-display text-base font-semibold text-ink">
          No course materials uploaded yet.
        </p>
        <p className="mt-1 text-xs text-ink-muted">
          Upload a lecture or syllabus PDF above to extract passages and start tutoring.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {documents.map((doc) => {
        const isDeleting = deletingId === doc.id;
        const isExpanded = expandedDocId === doc.id;
        const chunks = chunksByDoc[doc.id] || [];

        return (
          <div
            key={doc.id}
            className="rounded-2xl border border-line bg-paper-surface p-5 sm:p-6 shadow-warm-sm transition-all hover:border-forest/30"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sage-soft text-[#325235] text-sm font-bold">
                    📄
                  </span>
                  <div>
                    <h4 className="font-display text-base font-semibold text-ink">
                      {doc.filename}
                    </h4>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-ink-muted">
                      <span>{(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                      <span>•</span>
                      <span>
                        {doc.page_count !== null ? `${doc.page_count} pages` : 'N/A'}
                      </span>
                      <span>•</span>
                      <span>{doc.chunk_count} indexed chunks</span>
                      <span>•</span>
                      <span>{formatIsoTimestamp(doc.created_at)}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <DocumentStatusBadge status={doc.status} />

                {doc.status === 'READY' && onPreviewDocument && (
                  <button
                    type="button"
                    onClick={() => onPreviewDocument(doc.id)}
                    className="rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-bold text-ink hover:border-forest transition-colors shadow-warm-sm"
                  >
                    Preview PDF
                  </button>
                )}
                {doc.status === 'READY' && doc.chunk_count > 0 && (
                  <button
                    type="button"
                    onClick={() => void handleToggleChunks(doc.id)}
                    className="rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-bold text-ink hover:border-forest transition-colors shadow-warm-sm"
                  >
                    {isExpanded ? 'Hide Chunks' : `Chunks (${doc.chunk_count})`}
                  </button>
                )}
                <button
                  type="button"
                  disabled={isDeleting}
                  onClick={() => void handleDelete(doc.id)}
                  className="rounded-lg px-2.5 py-1.5 text-xs font-bold text-coral hover:bg-coral-soft transition-colors disabled:opacity-50"
                >
                  {isDeleting ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </div>

            {/* Extraction Failure Display */}
            {doc.error_message && (
              <div className="mt-4 rounded-xl border border-[#f0c2b8] bg-coral-soft p-3.5 text-xs text-[#85291b]">
                <p className="font-bold">Extraction Error:</p>
                <p className="mt-0.5">{doc.error_message}</p>
              </div>
            )}

            {/* Extraction Warnings Display */}
            {doc.extraction_warnings && doc.extraction_warnings.length > 0 && (
              <div className="mt-4 rounded-xl border border-[#ead8a4] bg-[#fdf8e9] p-3.5 text-xs text-[#7a5407]">
                <p className="font-bold">
                  Extraction Warnings ({doc.extraction_warnings.length}):
                </p>
                <ul className="mt-1 list-inside list-disc space-y-1">
                  {doc.extraction_warnings.map((warning, idx) => (
                    <li key={idx}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Extracted Chunks Inspector */}
            {isExpanded && (
              <div className="mt-5 border-t border-line/60 pt-4">
                <h5 className="text-[11px] font-bold uppercase tracking-wider text-ink-muted mb-2">
                  Indexed RAG Chunks
                </h5>
                {loadingChunksId === doc.id ? (
                  <p className="text-xs text-ink-muted">Loading chunk passages…</p>
                ) : (
                  <div className="max-h-80 space-y-2.5 overflow-y-auto pr-1">
                    {chunks.map((chunk) => (
                      <div
                        key={chunk.id}
                        className="rounded-xl border border-line bg-paper p-3.5 text-xs"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 text-ink-muted font-medium mb-1.5">
                          <span className="font-mono font-bold text-forest">
                            Chunk #{chunk.chunk_index}
                          </span>
                          <span>
                            Page{' '}
                            {chunk.page_start === chunk.page_end
                              ? chunk.page_start
                              : `${chunk.page_start}–${chunk.page_end}`}
                            {chunk.section_title ? ` • ${chunk.section_title}` : ''}
                          </span>
                        </div>
                        <p className="whitespace-pre-wrap text-ink leading-relaxed">
                          {chunk.chunk_text}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
