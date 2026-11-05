import React, { useState } from 'react';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { askCourseTutor } from '../../services/tutorService';
import type {
  ConversationTurn,
  SourceReference,
  TutorChatMessage,
} from '../../types/tutor';

interface CourseTutorChatProps {
  courseId: string;
  courseTitle: string;
  userId: string;
  hasReadyDocuments: boolean;
  onOpenSource?: (documentId: string, page: number) => void;
}

const SourceCitationCard: React.FC<{
  source: SourceReference;
  onOpenSource?: (documentId: string, page: number) => void;
}> = ({ source, onOpenSource }) => {
  const [expanded, setExpanded] = useState(false);
  const pageLabel =
    source.page_start === source.page_end
      ? `p. ${source.page_start}`
      : `pp. ${source.page_start}–${source.page_end}`;

  return (
    <div className="rounded-xl border border-line bg-paper-surface p-3.5 text-xs shadow-warm-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-forest-soft px-2 py-0.5 font-mono text-[10px] font-bold text-forest">
            [Source {source.source_index}]
          </span>
          <span className="font-semibold text-ink">
            {source.filename}
          </span>
          <span className="rounded bg-paper-deep px-2 py-0.5 font-mono text-[11px] text-ink-muted">
            {pageLabel}
          </span>
          {source.section_title && (
            <span className="text-ink-muted">
              • {source.section_title}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-ink-muted text-[11px]">
            Relevance: {(source.relevance_score * 100).toFixed(0)}%
          </span>
          {onOpenSource && (
            <button
              type="button"
              onClick={() => onOpenSource(source.document_id, source.page_start)}
              className="font-bold text-forest hover:underline"
            >
              Open in PDF →
            </button>
          )}
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="font-semibold text-ink-muted hover:text-ink"
          >
            {expanded ? 'Hide Excerpt' : 'Show Excerpt'}
          </button>
        </div>
      </div>

      {expanded && (
        <blockquote className="mt-2.5 border-l-2 border-forest bg-paper p-3 text-xs italic text-ink rounded-r-lg">
          {source.excerpt}
        </blockquote>
      )}
    </div>
  );
};

export const CourseTutorChat: React.FC<CourseTutorChatProps> = ({
  courseId,
  courseTitle,
  userId,
  hasReadyDocuments,
  onOpenSource,
}) => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<TutorChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealedHintsByMsg, setRevealedHintsByMsg] = useState<
    Record<string, boolean>
  >({});

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isLoading) return;

    setError(null);
    const studentMsg: TutorChatMessage = {
      id: `msg-${Date.now()}-student`,
      role: 'student',
      content: trimmed,
      timestamp: new Date().toISOString(),
    };

    const historyPayload: ConversationTurn[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, studentMsg]);
    setQuestion('');
    setIsLoading(true);

    try {
      const response = await askCourseTutor({
        courseId,
        userId,
        question: trimmed,
        conversationHistory: historyPayload,
      });

      const tutorMsg: TutorChatMessage = {
        id: `msg-${Date.now()}-tutor`,
        role: 'tutor',
        content: response.answer,
        timestamp: new Date().toISOString(),
        tutorResponse: response,
      };
      setMessages((prev) => [...prev, tutorMsg]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to generate AI Tutor response.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const toggleHints = (msgId: string) => {
    setRevealedHintsByMsg((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  return (
    <section className="rounded-2xl border border-line bg-paper-surface p-6 sm:p-7 shadow-warm-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-forest text-paper text-xs font-bold">
              ✦
            </span>
            <h3 className="font-display text-lg font-semibold tracking-tight text-ink">
              Course-Grounded AI Tutor
            </h3>
          </div>
          <p className="mt-1 text-xs text-ink-muted leading-relaxed">
            Ask questions about your uploaded PDFs in <strong className="text-ink">{courseTitle}</strong>.
            Every explanation is grounded in retrieved course passages with page citations.
          </p>
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setMessages([]);
              setError(null);
            }}
            className="rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-ink-muted hover:border-forest hover:text-ink transition-colors"
          >
            Clear Conversation
          </button>
        )}
      </div>

      {!hasReadyDocuments && (
        <div className="mt-4">
          <AlertBanner
            variant="info"
            title="Upload Course PDF Material First"
            message="No processed PDF documents are ready in this course yet. Upload a PDF in the Documents tab so the AI Tutor can retrieve grounded passages and page references."
          />
        </div>
      )}

      {error && (
        <div className="mt-4">
          <AlertBanner
            variant="error"
            title="AI Tutor Error"
            message={error}
            onDismiss={() => setError(null)}
          />
        </div>
      )}

      {/* Conversation History */}
      <div className="mt-5 max-h-[540px] space-y-4 overflow-y-auto rounded-2xl border border-line bg-paper/60 p-4 sm:p-5">
        {messages.length === 0 ? (
          <div className="py-12 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-forest-soft text-forest text-xl font-display">
              ✦
            </div>
            <p className="font-display text-base font-semibold text-ink">
              Your Personal Academic Tutor is Ready
            </p>
            <p className="mx-auto mt-1 max-w-md text-xs text-ink-muted leading-relaxed">
              Ask any concept or question below to retrieve semantic passages from ChromaDB and receive a grounded explanation with page references.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            if (msg.role === 'student') {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-2xl rounded-2xl rounded-tr-none bg-forest px-4 py-3 text-xs sm:text-sm text-paper shadow-warm-sm">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-[#d7ceff] mb-1">
                      You
                    </div>
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  </div>
                </div>
              );
            }

            const res = msg.tutorResponse;
            const hintsShown = Boolean(revealedHintsByMsg[msg.id]);

            return (
              <div key={msg.id} className="flex justify-start">
                <div className="w-full max-w-3xl space-y-3 rounded-2xl rounded-tl-none border border-line bg-paper-surface p-5 shadow-warm-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/60 pb-2.5">
                    <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-forest">
                      <span>✦</span>
                      <span>AI Tutor</span>
                    </span>
                    {res?.insufficient_evidence ? (
                      <span className="rounded-full border border-[#ead8a4] bg-[#fdf8e9] px-2.5 py-0.5 text-[11px] font-semibold text-[#7a5407]">
                        Insufficient Evidence in Course PDFs
                      </span>
                    ) : (
                      res &&
                      res.relevant_pages.length > 0 && (
                        <span className="rounded-full bg-sage-soft px-2.5 py-0.5 text-[11px] font-bold text-[#2d4c30]">
                          Grounded • Pages: {res.relevant_pages.join(', ')}
                        </span>
                      )
                    )}
                  </div>

                  {/* Main Tutor Explanation */}
                  <div className="whitespace-pre-wrap text-xs sm:text-sm leading-relaxed text-ink">
                    {msg.content}
                  </div>

                  {/* Comprehension Questions */}
                  {res && res.comprehension_questions.length > 0 && (
                    <div className="rounded-xl border border-lilac/30 bg-lilac-soft/60 p-4">
                      <p className="text-xs font-bold uppercase tracking-wider text-[#524474] mb-2">
                        Check Your Understanding:
                      </p>
                      <ul className="list-inside list-disc space-y-1.5 text-xs text-ink">
                        {res.comprehension_questions.map((q, idx) => (
                          <li key={idx} className="leading-relaxed">{q}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Hints */}
                  {res && res.hints.length > 0 && (
                    <div>
                      <button
                        type="button"
                        onClick={() => toggleHints(msg.id)}
                        className="text-xs font-bold text-coral hover:underline"
                      >
                        {hintsShown
                          ? 'Hide Study Hints'
                          : `Show Study Hints (${res.hints.length}) →`}
                      </button>
                      {hintsShown && (
                        <ul className="mt-2 list-inside list-disc rounded-xl border border-[#ead8a4] bg-[#fdf8e9] p-3.5 text-xs text-[#7a5407] space-y-1">
                          {res.hints.map((hint, idx) => (
                            <li key={idx}>{hint}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {/* Source Citations */}
                  {res && res.source_references.length > 0 && (
                    <div className="space-y-2 border-t border-line/60 pt-3">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-ink-muted">
                        Verified Source Citations ({res.source_references.length})
                      </p>
                      <div className="space-y-2">
                        {res.source_references.map((src) => (
                          <SourceCitationCard
                            key={`${src.document_id}-${src.chunk_index}`}
                            source={src}
                            onOpenSource={onOpenSource}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Retrieval Metadata Footer */}
                  {res && (
                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-2 text-[10px] text-ink-muted">
                      <span>
                        Retrieved {res.retrieval_metadata.passages_retrieved} /{' '}
                        {res.retrieval_metadata.total_candidates_indexed} candidate passages
                        in {res.retrieval_metadata.retrieval_latency_ms} ms
                      </span>
                      <span>
                        Model: {res.retrieval_metadata.llm_model}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-tl-none border border-line bg-paper-surface px-5 py-3.5 text-xs font-medium text-ink-muted shadow-warm-sm flex items-center gap-2">
              <span className="animate-spin text-forest">✦</span>
              <span>Retrieving relevant passages from ChromaDB &amp; generating grounded explanation…</span>
            </div>
          </div>
        )}
      </div>

      {/* Question Input Form */}
      <form onSubmit={(e) => void handleAsk(e)} className="mt-4 flex gap-3">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={isLoading}
          placeholder="Ask a question about your uploaded course materials…"
          className="flex-1 rounded-xl border border-line bg-surface px-4 py-3 text-xs sm:text-sm text-ink outline-none transition-all placeholder:text-ink-subtle focus:border-forest focus:ring-2 focus:ring-forest/15 disabled:bg-paper-deep"
        />
        <button
          type="submit"
          disabled={isLoading || question.trim().length < 2}
          className="inline-flex items-center gap-2 rounded-xl bg-forest px-6 py-3 text-xs sm:text-sm font-bold text-paper shadow-warm-sm transition-all hover:bg-forest-hover disabled:opacity-50"
        >
          {isLoading ? 'Thinking…' : 'Ask Tutor'}
        </button>
      </form>
    </section>
  );
};
