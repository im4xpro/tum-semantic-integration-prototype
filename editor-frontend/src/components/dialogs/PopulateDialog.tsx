import { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { Spinner } from '../Spinner';
import type { PopulateConnector } from '../../types';

export interface PopulateOptions {
  connector: PopulateConnector;
  table?: string;
  data_limit?: number;
}

interface Props {
  open: boolean;
  sourceName: string;
  populating: boolean;
  onConfirm: (opts: PopulateOptions) => void;
  onClose: () => void;
}

const CONNECTORS: PopulateConnector[] = ['postgres', 'mongodb', 'timescale'];

export function PopulateDialog({ open, sourceName, populating, onConfirm, onClose }: Props) {
  const [connector, setConnector] = useState<PopulateConnector>('postgres');
  const [table, setTable] = useState('');
  const [rowLimit, setRowLimit] = useState('');

  useEffect(() => {
    if (open) {
      setConnector('postgres');
      setTable('');
      setRowLimit('');
    }
  }, [open]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (populating) return;
    const trimmedTable = table.trim();
    const parsedLimit = parseInt(rowLimit, 10);
    onConfirm({
      connector,
      table: trimmedTable || undefined,
      data_limit: Number.isFinite(parsedLimit) && parsedLimit > 0 ? parsedLimit : undefined,
    });
  }

  return (
    <Modal open={open} onClose={onClose} title="Populate Knowledge Graph" width="max-w-sm">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="text-xs text-gray-500">
          Materialize the loaded mapping for source{' '}
          <span className="font-medium text-gray-700">{sourceName}</span> into the knowledge graph.
          This runs on the backend and does not modify your local mapping.
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Connector</label>
          <select
            value={connector}
            onChange={(e) => setConnector(e.target.value as PopulateConnector)}
            className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm bg-white outline-none focus:ring-2 focus:ring-indigo-300"
          >
            {CONNECTORS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Table / collection</label>
          <input
            type="text"
            value={table}
            onChange={(e) => setTable(e.target.value)}
            placeholder={sourceName}
            className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <div className="text-[10px] text-gray-400 mt-1">
            Leave blank to use the source name.
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Row limit</label>
          <input
            type="number"
            min={1}
            value={rowLimit}
            onChange={(e) => setRowLimit(e.target.value)}
            placeholder="all rows"
            className="w-full border border-gray-300 rounded px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <div className="text-[10px] text-gray-400 mt-1">
            Optional cap on how many source records to process.
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={populating}
            className="px-3 py-1.5 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={populating}
            className="px-4 py-1.5 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 font-medium disabled:opacity-60 flex items-center gap-1.5"
          >
            {populating && <Spinner />}
            {populating ? 'Populating…' : 'Populate'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
