import { useState, useEffect, useCallback, useRef } from 'react';
import type { RunSummary, RunEntry, PopulateRun } from '../types';
import { formatNumber } from '../lib/format';

interface Props {
  runs: RunSummary[];
  loading: boolean;
  onRefresh: () => void;
  fetchEntries: (runId: string) => Promise<RunEntry[]>;
  fetchRun: (runId: string) => Promise<PopulateRun>;
}

function statusClasses(status: string): string {
  if (status === 'completed') return 'bg-green-100 text-green-700 border-green-200';
  if (status === 'failed') return 'bg-red-100 text-red-700 border-red-200';
  return 'bg-gray-100 text-gray-600 border-gray-200';
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function EntriesTable({ fetchEntries, runId }: { fetchEntries: (id: string) => Promise<RunEntry[]>; runId: string }) {
  const [entries, setEntries] = useState<RunEntry[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await fetchEntries(runId));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [fetchEntries, runId]);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <div className="px-3 py-2 text-xs text-gray-400">Loading entries…</div>;
  if (error) {
    return (
      <div className="px-3 py-2 text-xs text-red-600 flex items-center gap-2">
        <span>Failed to load entries: {error}</span>
        <button onClick={load} className="underline underline-offset-2 hover:text-red-800">retry</button>
      </div>
    );
  }
  if (!entries || entries.length === 0) {
    return <div className="px-3 py-2 text-xs text-gray-400 italic">No entries in this run.</div>;
  }

  const q = filter.trim().toLowerCase();
  const shown = q
    ? entries.filter((e) =>
        e.subject_uri.toLowerCase().includes(q) ||
        e.source_record_id.toLowerCase().includes(q) ||
        (e.class_uri ?? '').toLowerCase().includes(q))
    : entries;

  return (
    <div className="border-t border-gray-100">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter entries…"
          className="flex-1 border border-gray-200 rounded px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-indigo-300"
        />
        <span className="text-[10px] text-gray-400 whitespace-nowrap tabular-nums">
          {shown.length} / {entries.length}
        </span>
      </div>
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 border-y border-gray-100 sticky top-0">
            <tr>
              <th className="text-left px-3 py-1.5 font-medium text-gray-500">Subject URI</th>
              <th className="text-left px-3 py-1.5 font-medium text-gray-500 w-40">Source record</th>
              <th className="text-left px-3 py-1.5 font-medium text-gray-500 w-40">Class</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((e, i) => (
              <tr key={i} className="border-t border-gray-50">
                <td className="px-3 py-1 font-mono text-violet-700 break-all">{e.subject_uri}</td>
                <td className="px-3 py-1 font-mono text-gray-600 break-all">{e.source_record_id}</td>
                <td className="px-3 py-1 font-mono text-gray-500 break-all">{e.class_uri ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FailedRunError({ fetchRun, runId }: { fetchRun: (id: string) => Promise<PopulateRun>; runId: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const full = await fetchRun(runId);
      setMessage(full.error ?? 'No error message recorded.');
    } catch (e) {
      setMessage(`Could not load run detail: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [fetchRun, runId]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="px-3 py-2 text-xs text-red-700 bg-red-50 border-t border-red-100">
      {loading ? 'Loading error…' : <><span className="font-semibold">Error: </span>{message}</>}
    </div>
  );
}

function RunRow({ run, expanded, onToggle, fetchEntries, fetchRun }: {
  run: RunSummary;
  expanded: boolean;
  onToggle: () => void;
  fetchEntries: (id: string) => Promise<RunEntry[]>;
  fetchRun: (id: string) => Promise<PopulateRun>;
}) {
  const failed = run.status === 'failed';
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50"
      >
        <span className="text-gray-400 text-xs flex-shrink-0">{expanded ? '▾' : '▸'}</span>
        <div className="flex-1 min-w-0">
          <span className="font-medium text-gray-800 text-sm truncate block">{run.source_name}</span>
          <div className="text-[10px] text-gray-400 font-mono truncate" title={run.target_named_graph ?? undefined}>
            {run.target_named_graph ?? run.id}
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0 text-xs text-gray-500">
          <span className="tabular-nums" title="entities extracted">{formatNumber(run.entities_extracted)} ent</span>
          <span className="tabular-nums" title="triples in graph">{formatNumber(run.triples_in_db)} tpl</span>
          <span className="text-gray-400 whitespace-nowrap">{fmtTime(run.created_at)}</span>
          <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${statusClasses(run.status)}`}>
            {run.status}
          </span>
        </div>
      </button>

      {expanded && (
        failed
          ? <FailedRunError fetchRun={fetchRun} runId={run.id} />
          : <EntriesTable fetchEntries={fetchEntries} runId={run.id} />
      )}
    </div>
  );
}

export function RunsPanel({ runs, loading, onRefresh, fetchEntries, fetchRun }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const entriesCache = useRef(new Map<string, RunEntry[]>());
  const runCache = useRef(new Map<string, PopulateRun>());

  const cachedFetchEntries = useCallback(async (id: string) => {
    const hit = entriesCache.current.get(id);
    if (hit) return hit;
    const data = await fetchEntries(id);
    entriesCache.current.set(id, data);
    return data;
  }, [fetchEntries]);

  const cachedFetchRun = useCallback(async (id: string) => {
    const hit = runCache.current.get(id);
    if (hit) return hit;
    const data = await fetchRun(id);
    runCache.current.set(id, data);
    return data;
  }, [fetchRun]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 bg-white border-b border-gray-200 flex-shrink-0">
        <span className="font-semibold text-sm text-gray-800">Population Runs</span>
        <span className="text-xs text-gray-400">— {runs.length} run(s)</span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="ml-auto px-2 py-1 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40"
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
            <div className="text-4xl">📥</div>
            <div className="text-sm">{loading ? 'Loading runs…' : 'No population runs yet.'}</div>
            {!loading && (
              <div className="text-xs text-gray-400 text-center max-w-xs">
                Load a mapping and click <strong>Populate</strong> to materialize a source into the
                knowledge graph. Runs appear here.
              </div>
            )}
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-2">
            {runs.map((run) => (
              <RunRow
                key={run.id}
                run={run}
                expanded={expandedId === run.id}
                onToggle={() => setExpandedId((cur) => (cur === run.id ? null : run.id))}
                fetchEntries={cachedFetchEntries}
                fetchRun={cachedFetchRun}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
