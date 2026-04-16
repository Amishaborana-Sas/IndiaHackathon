import { Loader2, FileText, CheckCircle2, Clock } from 'lucide-react';
import { motion } from 'motion/react';

interface OcrProgressProps {
  currentPage: number;
  totalPages: number;
  elapsedMs: number;
  scannedPages: number[];
}

function formatTime(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  return `${min}m ${remSec}s`;
}

export default function OcrProgress({ currentPage, totalPages, elapsedMs, scannedPages }: OcrProgressProps) {
  const progress = totalPages > 0 ? (currentPage / totalPages) * 100 : 0;
  const avgPerPage = currentPage > 0 ? elapsedMs / currentPage : 0;
  const estimatedRemaining = avgPerPage * (totalPages - currentPage);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-blue-50 border border-blue-200 rounded-2xl p-6 space-y-4"
    >
      <div className="flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
        <h3 className="text-sm font-bold text-blue-900">OCR Scanning in Progress</h3>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-blue-700">
          <span className="font-semibold">Page {currentPage} of {totalPages}</span>
          <span className="font-semibold">{Math.round(progress)}%</span>
        </div>
        <div className="h-2.5 bg-blue-100 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-blue-600 rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>

      {/* Time info */}
      <div className="flex items-center gap-6 text-xs text-blue-700">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          <span>Elapsed: <strong>{formatTime(elapsedMs)}</strong></span>
        </div>
        {currentPage > 0 && currentPage < totalPages && (
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            <span>Est. remaining: <strong>{formatTime(estimatedRemaining)}</strong></span>
          </div>
        )}
        {avgPerPage > 0 && (
          <div className="flex items-center gap-1.5">
            <span>Avg: <strong>{formatTime(avgPerPage)}/page</strong></span>
          </div>
        )}
      </div>

      {/* Page list */}
      {totalPages > 0 && totalPages <= 50 && (
        <div className="space-y-2">
          <span className="text-xs font-bold text-blue-800">Page Status</span>
          <div className="flex flex-wrap gap-1.5">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
              const isScanned = scannedPages.includes(page);
              const isCurrent = page === currentPage;
              return (
                <div
                  key={page}
                  className={`
                    w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold transition-all
                    ${isScanned
                      ? 'bg-green-100 text-green-700 border border-green-200'
                      : isCurrent
                        ? 'bg-blue-600 text-white animate-pulse'
                        : 'bg-white text-slate-400 border border-slate-200'}
                  `}
                  title={isScanned ? `Page ${page}: Scanned` : isCurrent ? `Page ${page}: Scanning...` : `Page ${page}: Pending`}
                >
                  {isScanned ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : (
                    page
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] text-blue-600 pt-1 border-t border-blue-100">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-green-100 border border-green-200" />
          <span>Scanned</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-blue-600" />
          <span>In progress</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-white border border-slate-200" />
          <span>Pending</span>
        </div>
      </div>
    </motion.div>
  );
}
