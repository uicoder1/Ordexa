import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { UploadedFileRecord } from '../types';
import { Trash2, FileText, RefreshCw } from 'lucide-react';

interface ImportHistoryPageProps {
  onRefreshMetrics: () => void;
}

export const ImportHistoryPage: React.FC<ImportHistoryPageProps> = ({ onRefreshMetrics }) => {
  const [history, setHistory] = useState<UploadedFileRecord[]>([]);

  const fetchHistory = async () => {
    try {
      const res = await api.get('/imports');
      setHistory(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleDelete = async (uploadId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete report '${filename}' and revert its transactions?`)) {
      return;
    }
    try {
      await api.delete(`/imports/${uploadId}`);
      fetchHistory();
      onRefreshMetrics();
    } catch (err) {
      alert('Failed to delete import.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex justify-between items-center">
        <div>
          <h2 className="text-base font-bold text-slate-900">Upload & Import History</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit uploaded settlement reports and reprocess or remove historical imports.
          </p>
        </div>
        <button
          onClick={fetchHistory}
          className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-600"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/70 text-slate-600 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="px-4 py-3">File Name</th>
                <th className="px-4 py-3">Marketplace</th>
                <th className="px-4 py-3">Uploaded At</th>
                <th className="px-4 py-3 text-center">Rows Processed</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {history.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3.5 font-semibold text-slate-900 flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>{item.filename}</span>
                  </td>
                  <td className="px-4 py-3.5 text-slate-600">{item.marketplace}</td>
                  <td className="px-4 py-3.5 text-slate-500">
                    {new Date(item.uploaded_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3.5 text-center font-semibold text-slate-900">
                    {item.rows_processed}
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        item.upload_status === 'completed'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {item.upload_status}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-right">
                    <button
                      onClick={() => handleDelete(item.id, item.filename)}
                      title="Delete import and revert numbers"
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
