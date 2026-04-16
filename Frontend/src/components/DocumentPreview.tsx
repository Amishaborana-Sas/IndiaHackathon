import { useState, useMemo, useEffect } from 'react';
import { X, ZoomIn, ZoomOut } from 'lucide-react';
import { motion } from 'motion/react';

interface DocumentPreviewProps {
  file: File;
  onClose: () => void;
}

export default function DocumentPreview({ file, onClose }: DocumentPreviewProps) {
  const [zoom, setZoom] = useState(1);

  const url = useMemo(() => URL.createObjectURL(file), [file]);

  useEffect(() => {
    return () => URL.revokeObjectURL(url);
  }, [url]);

  const isPDF = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  const isImage = file.type.startsWith('image/');

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-white rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-3 min-w-0">
            <span className="font-bold text-slate-900 truncate">{file.name}</span>
            <span className="text-xs text-slate-400 shrink-0">
              ({(file.size / 1024 / 1024).toFixed(2)} MB)
            </span>
          </div>
          <div className="flex items-center gap-3">
            {isImage && (
              <div className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 px-2 py-1">
                <button
                  onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}
                  className="p-1 hover:bg-slate-100 rounded"
                >
                  <ZoomOut className="w-4 h-4 text-slate-600" />
                </button>
                <span className="text-xs font-mono text-slate-600 w-12 text-center">
                  {Math.round(zoom * 100)}%
                </span>
                <button
                  onClick={() => setZoom((z) => Math.min(4, z + 0.25))}
                  className="p-1 hover:bg-slate-100 rounded"
                >
                  <ZoomIn className="w-4 h-4 text-slate-600" />
                </button>
              </div>
            )}
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-full transition-colors"
            >
              <X className="w-5 h-5 text-slate-600" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto bg-slate-100 p-4">
          {isPDF && (
            <iframe
              src={`${url}#toolbar=1`}
              className="w-full h-full rounded-lg border border-slate-200"
              title={`Preview: ${file.name}`}
            />
          )}
          {isImage && (
            <div className="flex justify-center">
              <img
                src={url}
                alt={file.name}
                className="max-w-none transition-transform"
                style={{
                  transform: `scale(${zoom})`,
                  transformOrigin: 'top center',
                }}
              />
            </div>
          )}
          {!isPDF && !isImage && (
            <div className="flex items-center justify-center h-full text-slate-500">
              <p>Preview not available for this file type. Upload to process.</p>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
