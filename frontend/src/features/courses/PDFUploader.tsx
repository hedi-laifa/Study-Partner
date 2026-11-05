import React, { useRef, useState } from 'react';
import { AlertBanner } from '../../components/ui/AlertBanner';

const MAX_FILE_SIZE_MB = 50;

interface PDFUploaderProps {
  isUploading: boolean;
  onUpload: (file: File) => Promise<void>;
}

export const PDFUploader: React.FC<PDFUploaderProps> = ({
  isUploading,
  onUpload,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const validateAndSelectFile = (file: File | undefined) => {
    setClientError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setClientError(
        'Invalid file type. Please select a valid .pdf course document.'
      );
      setSelectedFile(null);
      return;
    }

    if (file.size === 0) {
      setClientError('The selected PDF file is empty (0 bytes).');
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setClientError(
        `File exceeds maximum allowed size of ${MAX_FILE_SIZE_MB} MB.`
      );
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleUploadClick = async () => {
    if (!selectedFile) return;
    await onUpload(selectedFile);
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    validateAndSelectFile(file);
  };

  return (
    <div className="rounded-2xl border border-line bg-paper-surface p-6 sm:p-7 shadow-warm-sm">
      <div className="flex items-center gap-3 mb-2">
        <span
          className="flex h-7 w-7 items-center justify-center rounded-md bg-sage-soft text-[#426145] text-xs font-bold"
          aria-hidden="true"
        >
          📄
        </span>
        <h3 className="font-display text-lg font-semibold tracking-tight text-ink">
          Upload Course Material (PDF)
        </h3>
      </div>
      <p className="text-xs sm:text-sm text-ink-muted leading-relaxed">
        Upload syllabus, lecture slides, or textbook readings (.pdf up to {MAX_FILE_SIZE_MB} MB).
        Our pipeline extracts page-aware text, detects scanned pages, and indexes overlapping chunks for grounded AI tutoring.
      </p>

      {clientError && (
        <div className="mt-4">
          <AlertBanner
            variant="error"
            title="File Validation Error"
            message={clientError}
            onDismiss={() => setClientError(null)}
          />
        </div>
      )}

      {/* StudyMate-inspired Sage Dropzone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`mt-5 flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
          isDragOver
            ? 'border-forest bg-sage-soft/90 scale-[1.01]'
            : 'border-sage/50 bg-sage-soft/40 hover:border-forest hover:bg-sage-soft/70'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          disabled={isUploading}
          onChange={(e) => validateAndSelectFile(e.target.files?.[0])}
          className="hidden"
        />

        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-paper-surface text-forest shadow-warm-sm text-xl">
          ↑
        </div>

        <div>
          <strong className="block text-sm font-semibold text-forest">
            {selectedFile ? selectedFile.name : 'Choose a PDF file or drag & drop here'}
          </strong>
          <span className="block text-xs text-ink-muted mt-1">
            {selectedFile
              ? `${(selectedFile.size / 1024).toFixed(1)} KB — Ready to upload`
              : `Supports multi-page lectures, handouts, and notes up to ${MAX_FILE_SIZE_MB} MB`}
          </span>
        </div>

        {selectedFile && !isUploading && (
          <div className="mt-2" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => void handleUploadClick()}
              className="inline-flex items-center gap-2 rounded-lg bg-forest px-5 py-2.5 text-xs sm:text-sm font-bold text-paper shadow-warm-sm hover:bg-forest-hover transition-all"
            >
              <span>Upload & Index Document</span>
              <span aria-hidden="true">→</span>
            </button>
          </div>
        )}

        {isUploading && (
          <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-forest">
            <span className="animate-spin text-lg">✦</span>
            <span>Extracting text & generating passage embeddings…</span>
          </div>
        )}
      </div>
    </div>
  );
};
