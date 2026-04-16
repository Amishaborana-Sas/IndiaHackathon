import { useState, useRef, DragEvent, ChangeEvent } from 'react';
import { Upload, FileText, X, Eye } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface UploadBoxProps {
  onFilesSelect: (files: File[]) => void;
  selectedFiles: File[];
  onPreview?: (file: File) => void;
}

export default function UploadBox({ onFilesSelect, selectedFiles, onPreview }: UploadBoxProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files) as File[];
    if (files.length > 0) {
      onFilesSelect([...selectedFiles, ...files]);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? (Array.from(e.target.files) as File[]) : [];
    if (files.length > 0) {
      onFilesSelect([...selectedFiles, ...files]);
    }
  };

  const removeFile = (index: number) => {
    const newFiles = [...selectedFiles];
    newFiles.splice(index, 1);
    onFilesSelect(newFiles);
  };

  const getFileIcon = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return 'PDF';
    if (['png', 'jpg', 'jpeg', 'tiff', 'webp', 'bmp'].includes(ext || '')) return 'IMG';
    if (ext === 'docx') return 'DOC';
    if (['csv', 'xlsx', 'xlsm', 'tsv'].includes(ext || '')) return 'XLS';
    if (['wav', 'mp3', 'm4a', 'aac', 'ogg', 'flac', 'wma', 'webm'].includes(ext || '')) return 'AUD';
    return 'TXT';
  };

  return (
    <div className="w-full space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center cursor-pointer transition-all
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-blue-400 hover:bg-slate-50'}
        `}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.webp,.bmp,.docx,.txt,.csv,.xlsx,.xlsm,.tsv,.json,.html,.htm,.md,.log,.wav,.mp3,.m4a,.aac,.ogg,.flac,.wma,.webm"
        />
        <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 ${isDragging ? 'bg-blue-100' : 'bg-slate-100'}`}>
          <Upload className={`w-8 h-8 ${isDragging ? 'text-blue-600' : 'text-slate-400'}`} />
        </div>
        <h4 className="text-lg font-semibold text-slate-900 mb-1">Click or drag files to upload</h4>
        <p className="text-sm text-slate-500">
          PDF, Images, Scanned Docs, DOCX, XLSX, CSV, JSON, TXT, Audio (WAV, MP3, M4A) — Max 50MB
        </p>
      </div>

      <AnimatePresence>
        {selectedFiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2"
          >
            <div className="flex items-center justify-between px-2">
              <span className="text-sm font-bold text-slate-700">{selectedFiles.length} File{selectedFiles.length > 1 ? 's' : ''} Selected</span>
              <button
                onClick={() => onFilesSelect([])}
                className="text-xs text-red-500 hover:underline font-medium"
              >
                Clear All
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {selectedFiles.map((file, index) => (
                <motion.div
                  key={`${file.name}-${index}`}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="bg-blue-50 border border-blue-100 rounded-xl p-3 flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
                      <span className="text-[10px] font-bold text-white">{getFileIcon(file)}</span>
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-blue-900 truncate">
                        {file.name}
                      </p>
                      <p className="text-[10px] text-blue-600 font-medium">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {onPreview && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onPreview(file);
                        }}
                        className="p-1.5 hover:bg-blue-200 rounded-full text-blue-600 transition-colors opacity-0 group-hover:opacity-100"
                        title="Preview document"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(index);
                      }}
                      className="p-1.5 hover:bg-red-200 rounded-full text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                      title="Remove file"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
