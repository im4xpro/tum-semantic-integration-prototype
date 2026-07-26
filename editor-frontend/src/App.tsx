import { useState, useCallback } from 'react';
import { ReactFlowProvider } from '@xyflow/react';

import { openWorkspace, isFileSystemAccessSupported } from './lib/workspace';
import { validateMapping } from './lib/validate';
import { api, normalizeGeneratedMapping, toBackendMapping } from './api';
import { formatNumber } from './lib/format';
import type { Workspace } from './lib/workspace';
import type {
  OntologyClass,
  OntologyProperty,
  ExtractedSchema,
  SchemaInfo,
  MappingDocument,
  MappingInfo,
  SubjectMapping,
  ValueType,
  ValidationResult,
  LLMProvider,
  RunSummary,
} from './types';
import type { NewMappingResult } from './components/dialogs/NewMappingDialog';
import type { PopulateOptions } from './components/dialogs/PopulateDialog';

import { MappingCanvas } from './components/MappingCanvas';
import { OntologyGraphView } from './components/OntologyGraphView';
import { MappingPreview } from './components/MappingPreview';
import { RunsPanel } from './components/RunsPanel';
import { OntologyPanel } from './components/panels/OntologyPanel';
import { AddSubjectDialog } from './components/dialogs/AddSubjectDialog';
import { AddPropertyDialog } from './components/dialogs/AddPropertyDialog';
import { InlineObjectDialog } from './components/dialogs/InlineObjectDialog';
import { AddSourceDialog } from './components/dialogs/AddSourceDialog';
import { NewMappingDialog } from './components/dialogs/NewMappingDialog';
import { PopulateDialog } from './components/dialogs/PopulateDialog';

// ─── helpers ──────────────────────────────────────────────────────────────────

function shortUri(uri: string, namespaces: Record<string, string>): string {
  for (const [prefix, ns] of Object.entries(namespaces)) {
    if (uri.startsWith(ns)) return `${prefix}:${uri.slice(ns.length)}`;
  }
  return uri;
}

function emptyMapping(sourceName: string, name?: string): MappingDocument {
  return {
    id: '',
    name: name || undefined,
    source_name: sourceName,
    llm_model: 'manual',
    strategy: 'manual',
    ontology_format: 'manual',
    rag_enabled: false,
    base_uri: import.meta.env.VITE_DEFAULT_BASE_URI ?? '',
    namespaces: import.meta.env.VITE_DEFAULT_NAMESPACE_PREFIX
      ? { [import.meta.env.VITE_DEFAULT_NAMESPACE_PREFIX]: import.meta.env.VITE_DEFAULT_NAMESPACE_URI ?? '' }
      : {},
    subject_mappings: [],
    unmapped_fields: [],
    generation_timestamp: new Date().toISOString(),
    prompt_tokens: 0,
    completion_tokens: 0,
    status: 'draft',
  };
}

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── toast ────────────────────────────────────────────────────────────────────

type ToastKind = 'success' | 'error' | 'info';
interface Toast { id: number; msg: string; kind: ToastKind }
let toastCounter = 0;

type ViewMode = 'editor' | 'preview' | 'graph' | 'runs';

interface ViewModeDef {
  id: ViewMode;
  label: string;
  enabled: boolean;
  disabled: boolean;
  onEnter?: () => void;
}

const AI_ENABLED_KEY = 'mapping-editor:ai-enabled';

function readAiEnabled(): boolean {
  const stored = localStorage.getItem(AI_ENABLED_KEY);
  return stored === null ? true : stored === 'true';
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [classes, setClasses] = useState<OntologyClass[]>([]);
  const [properties, setProperties] = useState<OntologyProperty[]>([]);
  const [schemaList, setSchemaList] = useState<SchemaInfo[]>([]);
  const [selectedSchemaName, setSelectedSchemaName] = useState('');
  const [schema, setSchema] = useState<ExtractedSchema | null>(null);
  const [mappingList, setMappingList] = useState<MappingInfo[]>([]);
  const [mapping, setMapping] = useState<MappingDocument | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [activeFilename, setActiveFilename] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [showValidation, setShowValidation] = useState(false);
  const [showOntology, setShowOntology] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('editor');
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const [newMappingOpen, setNewMappingOpen] = useState(false);
  const [sampleIndex, setSampleIndex] = useState(0);
  const [aiEnabled, setAiEnabled] = useState(readAiEnabled);
  const [generating, setGenerating] = useState(false);
  const [populateOpen, setPopulateOpen] = useState(false);
  const [populating, setPopulating] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);

  // ── dialog state ────────────────────────────────────────────────────────
  const [addSubjectOpen, setAddSubjectOpen] = useState(false);
  const [addPropState, setAddPropState] = useState<{ open: boolean; si: number; classUri: string }>({
    open: false, si: -1, classUri: '',
  });
  const [inlineObjState, setInlineObjState] = useState<{
    open: boolean; si: number; pi: number;
  }>({ open: false, si: -1, pi: -1 });

  // ── toast helper ────────────────────────────────────────────────────────
  const toast = useCallback((msg: string, kind: ToastKind = 'info') => {
    const id = ++toastCounter;
    setToasts((prev) => [...prev, { id, msg, kind }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3500);
  }, []);

  // ── load workspace data ─────────────────────────────────────────────────
  const loadWorkspaceData = useCallback(async (ws: Workspace) => {
    try {
      const [ontology, schemas, maps] = await Promise.all([
        ws.getOntology(),
        ws.listSchemas(),
        ws.listMappings(),
      ]);
      setClasses(ontology.classes);
      setProperties(ontology.properties);
      setSchemaList(schemas);
      setMappingList(maps);
      if (ontology.classes.length === 0) {
        toast('No ontology.ttl found in workspace — ontology panel will be empty.', 'info');
      }
    } catch (e) {
      toast(`Failed to load workspace: ${e}`, 'error');
    }
  }, [toast]);

  // ── open workspace ──────────────────────────────────────────────────────
  const handleOpenWorkspace = useCallback(async () => {
    try {
      const ws = await openWorkspace();
      setWorkspace(ws);
      setMapping(null);
      setActiveFilename(null);
      setSchema(null);
      setSelectedSchemaName('');
      setValidation(null);
      await loadWorkspaceData(ws);
      toast(`Workspace "${ws.name}" opened`, 'success');
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === 'AbortError') return; // user cancelled
      toast(`Could not open workspace: ${e}`, 'error');
    }
  }, [loadWorkspaceData, toast]);

  // ── schema selection ────────────────────────────────────────────────────
  // keepMapping=true is used by loadMapping, which sets the mapping itself
  // before calling here — we must not overwrite it.
  const handleSelectSchema = useCallback(async (sourceName: string, { keepMapping = false } = {}) => {
    setSelectedSchemaName(sourceName);
    setSampleIndex(0);
    if (!keepMapping) {
      setMapping(null);
      setActiveFilename(null);
      setValidation(null);
    }
    if (!sourceName || !workspace) { setSchema(null); return; }
    const info = schemaList.find((s) => s.source_name === sourceName);
    if (!info) { setSchema(null); return; }
    try {
      const s = await workspace.getSchema(info.filename);
      setSchema(s);
    } catch (e) {
      toast(`Schema load failed: ${e}`, 'error');
      setSchema(null);
    }
  }, [workspace, toast, schemaList]);

  // ── add source ──────────────────────────────────────────────────────────
  const handleAddSource = useCallback(async (newSchema: ExtractedSchema) => {
    if (!workspace) return;
    try {
      await workspace.saveSchema(newSchema);
      const schemas = await workspace.listSchemas();
      setSchemaList(schemas);
      setAddSourceOpen(false);
      // Set schema state directly to avoid the stale-schemaList closure
      // that handleSelectSchema would have right after setSchemaList.
      setSelectedSchemaName(newSchema.source_name);
      setSchema(newSchema);
      setSampleIndex(0);
      toast(`Source "${newSchema.source_name}" saved`, 'success');
    } catch (e) {
      toast(`Failed to save source: ${e}`, 'error');
    }
  }, [workspace, toast]);

  // ── load mapping ────────────────────────────────────────────────────────
  // Keyed by filename — avoids the empty-id pitfall where m.id === "" is
  // falsy and the onChange handler silently skips the load.
  const loadMapping = useCallback(async (filename: string) => {
    if (!workspace) return;
    try {
      const m = await workspace.getMapping(filename);
      setMapping(m);
      setActiveFilename(filename);
      setIsDirty(false);
      setValidation(null);
      await handleSelectSchema(m.source_name, { keepMapping: true });
    } catch (e) {
      toast(`Mapping load failed: ${e}`, 'error');
    }
  }, [workspace, toast, handleSelectSchema]);

  const loadNewDocument = useCallback((doc: MappingDocument) => {
    setMapping(doc);
    setActiveFilename(null);
    setIsDirty(true);
    setValidation(null);
  }, []);

  const handleNewMapping = useCallback(async (result: NewMappingResult) => {
    if (result.mode === 'manual') {
      loadNewDocument(emptyMapping(selectedSchemaName, result.name || undefined));
      setNewMappingOpen(false);
      return;
    }

    if (!schema) { toast('Select a source before generating', 'error'); return; }
    setGenerating(true);
    try {
      const raw = await api.generateMapping({
        source_schema: schema,
        strategy: result.strategy,
        provider: (import.meta.env.VITE_LLM_PROVIDER ?? 'anthropic') as LLMProvider,
        llm_model: import.meta.env.VITE_LLM_MODEL ?? '',
        ontology_format: result.ontology_format,
        include_descriptions: false,
        column_descriptions: null,
        temperature: 0.0,
      });
      const doc = normalizeGeneratedMapping(raw);
      if (result.name) doc.name = result.name;
      loadNewDocument(doc);
      setNewMappingOpen(false);
      toast('Mapping generated — review it in the canvas before saving', 'success');
    } catch (e) {
      toast(`Generation failed: ${e}`, 'error');
    } finally {
      setGenerating(false);
    }
  }, [selectedSchemaName, schema, loadNewDocument, toast]);

  const toggleAiEnabled = useCallback(() => {
    setAiEnabled((prev) => {
      const next = !prev;
      localStorage.setItem(AI_ENABLED_KEY, String(next));
      return next;
    });
  }, []);

  const loadRuns = useCallback(async () => {
    if (!aiEnabled) return;
    setRunsLoading(true);
    try {
      setRuns(await api.listPopulateRuns());
    } catch (e) {
      toast(`Failed to load runs: ${e}`, 'error');
    } finally {
      setRunsLoading(false);
    }
  }, [aiEnabled, toast]);

  const handlePopulate = useCallback(async (opts: PopulateOptions) => {
    if (!mapping) return;
    setPopulating(true);
    try {
      const res = await api.populate({
        mapping: toBackendMapping(mapping),
        source_name: mapping.source_name,
        connector: opts.connector,
        table: opts.table,
        data_limit: opts.data_limit,
      });
      setPopulateOpen(false);
      const stats = res.run.stats;
      toast(
        `Populated: ${formatNumber(stats.entities_extracted)} entities, ` +
        `${formatNumber(stats.triples_written)} triples`,
        'success',
      );
      loadRuns();
    } catch (e) {
      toast(`Populate failed: ${e}`, 'error');
    } finally {
      setPopulating(false);
    }
  }, [mapping, toast, loadRuns]);

  const handleMappingChange = useCallback((m: MappingDocument) => {
    setMapping(m);
    setIsDirty(true);
    setValidation(null);
  }, []);

  // ── add subject ─────────────────────────────────────────────────────────
  const handleAddSubject = useCallback((cls: OntologyClass) => {
    if (!mapping) return;
    const classUri = shortUri(cls.uri, mapping.namespaces);
    const newSubject: SubjectMapping = {
      subject: { source: 'column' },
      type_mappings: [{ class_uri: classUri }],
      property_mappings: [],
    };
    handleMappingChange({ ...mapping, subject_mappings: [...mapping.subject_mappings, newSubject] });
  }, [mapping, handleMappingChange]);

  // ── add property ────────────────────────────────────────────────────────
  const handleRequestAddProperty = useCallback((si: number, classUri: string) => {
    setAddPropState({ open: true, si, classUri });
  }, []);

  const handleAddProperty = useCallback((prop: OntologyProperty) => {
    if (!mapping) return;
    const { si } = addPropState;
    const propUri = shortUri(prop.uri, mapping.namespaces);
    const subjects = mapping.subject_mappings.map((sm, i) => {
      if (i !== si) return sm;
      return {
        ...sm,
        property_mappings: [
          ...sm.property_mappings,
          {
            property_uri: propUri,
            values: [{
              value_source: { source: 'column' as const },
              value_type: {
                type: (prop.is_object_property ? 'iri' : 'literal') as 'literal' | 'iri',
                type_mappings: [],
                property_mappings: [],
              },
            }],
          },
        ],
      };
    });
    handleMappingChange({ ...mapping, subject_mappings: subjects });
  }, [mapping, addPropState, handleMappingChange]);

  // ── inline object editing ───────────────────────────────────────────────
  const handleRequestEditInlineObject = useCallback((si: number, pi: number) => {
    setInlineObjState({ open: true, si, pi });
  }, []);

  const currentInlineVt: ValueType | null = (() => {
    if (!mapping || !inlineObjState.open) return null;
    return mapping.subject_mappings[inlineObjState.si]
      ?.property_mappings[inlineObjState.pi]
      ?.values[0]
      ?.value_type ?? null;
  })();

  const handleInlineObjectChange = useCallback((updatedVt: ValueType) => {
    if (!mapping) return;
    const { si, pi } = inlineObjState;
    const subjects = mapping.subject_mappings.map((sm, i) => {
      if (i !== si) return sm;
      const pms = sm.property_mappings.map((pm, j) => {
        if (j !== pi) return pm;
        return { ...pm, values: pm.values.map((v, vi) => vi === 0 ? { ...v, value_type: updatedVt } : v) };
      });
      return { ...sm, property_mappings: pms };
    });
    handleMappingChange({ ...mapping, subject_mappings: subjects });
  }, [mapping, inlineObjState, handleMappingChange]);

  // ── save ────────────────────────────────────────────────────────────────
  const handleSave = useCallback(async () => {
    if (!mapping || !workspace) return;
    try {
      const { id, filename } = await workspace.saveMapping(mapping);
      setActiveFilename(filename);
      setMapping((m) => m ? { ...m, id } : m);
      setIsDirty(false);
      setMappingList(await workspace.listMappings());
      toast('Saved', 'success');
    } catch (e) {
      toast(`Save failed: ${e}`, 'error');
    }
  }, [mapping, workspace, toast]);

  // ── validate ────────────────────────────────────────────────────────────
  const handleValidate = useCallback(() => {
    if (!mapping) return;
    const result = validateMapping(mapping, schema);
    setValidation(result);
    setShowValidation(true);
  }, [mapping, schema]);

  // ── export ──────────────────────────────────────────────────────────────
  const handleExport = useCallback(() => {
    if (!mapping) return;
    const filename = `mapping-${mapping.id || 'draft'}-${mapping.source_name}.json`;
    downloadJson(mapping, filename);
  }, [mapping]);

  // ── status ──────────────────────────────────────────────────────────────
  const setStatus = useCallback(async (status: MappingDocument['status']) => {
    if (!mapping || !workspace) return;
    const updated = { ...mapping, status };
    try {
      const { id, filename } = await workspace.saveMapping(updated);
      setActiveFilename(filename);
      setMapping({ ...updated, id });
      setIsDirty(false);
      toast(`Status → ${status}`, 'success');
    } catch (e) {
      toast(`Failed: ${e}`, 'error');
    }
  }, [mapping, workspace, toast]);

  // ── welcome screen (no workspace) ───────────────────────────────────────
  if (!workspace) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-gray-50 gap-6 px-4">
        <div className="text-center">
          <div className="text-5xl mb-4">🗺</div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Mapping Editor</h1>
          <p className="text-sm text-gray-500 max-w-sm">
            Select a local folder to use as your workspace. Schemas, mappings, and ontology
            are stored as JSON files inside it.
          </p>
        </div>

        {isFileSystemAccessSupported() ? (
          <button
            onClick={handleOpenWorkspace}
            className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 shadow-sm text-sm"
          >
            Open Workspace Folder
          </button>
        ) : (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3 max-w-sm text-center">
            Your browser does not support the File System Access API.
            Please use Chrome or Edge.
          </div>
        )}

        <div className="text-xs text-gray-400 max-w-xs text-center">
          Place an <code className="bg-gray-100 px-1 rounded">ontology.ttl</code> file in the
          workspace root to load your ontology.
          Sources go in <code className="bg-gray-100 px-1 rounded">schemas/</code>,
          mappings in <code className="bg-gray-100 px-1 rounded">mappings/</code>.
        </div>
      </div>
    );
  }

  // ── render ──────────────────────────────────────────────────────────────
  const viewModes: ViewModeDef[] = [
    { id: 'editor', label: 'Editor', enabled: true, disabled: false },
    { id: 'preview', label: 'Preview', enabled: true, disabled: !mapping },
    { id: 'graph', label: 'Ontology Graph', enabled: true, disabled: false },
    { id: 'runs', label: 'Runs', enabled: aiEnabled, disabled: false, onEnter: loadRuns },
  ];
  const effectiveViewMode: ViewMode =
    viewModes.some((v) => v.id === viewMode && v.enabled) ? viewMode : 'editor';

  return (
    <div className="h-screen flex flex-col bg-gray-100 font-sans text-sm">

      {/* ── Toolbar ── */}
      <header className="flex items-center gap-3 px-4 py-2 bg-white border-b border-gray-200 shadow-sm z-10 flex-shrink-0 flex-wrap">
        <span className="font-bold text-indigo-700 text-base whitespace-nowrap">Mapping Editor</span>
        <span className="text-xs text-gray-400 font-mono truncate max-w-[140px]" title={workspace.name}>
          {workspace.name}
        </span>
        <button
          onClick={handleOpenWorkspace}
          className="text-xs text-gray-400 hover:text-indigo-600 underline underline-offset-2"
          title="Switch workspace"
        >
          switch
        </button>
        <div className="h-5 border-l border-gray-200" />

        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 whitespace-nowrap">Source:</label>
          <select
            className="border border-gray-300 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300"
            value={selectedSchemaName}
            onChange={(e) => handleSelectSchema(e.target.value)}
          >
            <option value="">-- select --</option>
            {schemaList.map((s) => (
              <option key={s.source_name} value={s.source_name}>
                {s.source_name} ({s.source_type}, {s.column_count} cols)
              </option>
            ))}
          </select>
          <button
            onClick={() => setAddSourceOpen(true)}
            className="px-2 py-1 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
            title="Add a new source manually"
          >
            + Source
          </button>
        </div>

        {schema && schema.sample_records.length > 0 && (
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-400 whitespace-nowrap">Sample:</span>
            <button
              className="w-5 h-5 flex items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 text-xs"
              disabled={sampleIndex === 0}
              onClick={() => setSampleIndex((i) => i - 1)}
              title="Previous sample"
            >&#8249;</button>
            <span className="text-xs text-gray-600 tabular-nums">
              {sampleIndex + 1}/{schema.sample_records.length}
            </span>
            <button
              className="w-5 h-5 flex items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 text-xs"
              disabled={sampleIndex === schema.sample_records.length - 1}
              onClick={() => setSampleIndex((i) => i + 1)}
              title="Next sample"
            >&#8250;</button>
          </div>
        )}

        <div className="h-5 border-l border-gray-200" />

        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 whitespace-nowrap">Mapping:</label>
          <select
            className="border border-gray-300 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300 max-w-[220px] disabled:opacity-40 disabled:cursor-not-allowed"
            value={activeFilename ?? ''}
            disabled={!selectedSchemaName}
            onChange={(e) => { if (e.target.value) loadMapping(e.target.value); }}
          >
            <option value="">{selectedSchemaName ? '-- load existing --' : '-- select a source first --'}</option>
            {mappingList
              .filter((m) => m.source_name === selectedSchemaName)
              .map((m) => (
                <option key={m.filename} value={m.filename}>
                  {m.name || m.strategy} [{m.status}]
                </option>
              ))}
          </select>
        </div>

        <div className="h-5 border-l border-gray-200" />

        <button
          className="px-3 py-1 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40"
          disabled={!selectedSchemaName}
          onClick={() => setNewMappingOpen(true)}
        >
          New
        </button>

        {mapping && (
          <>
            <button
              className="px-3 py-1 text-xs rounded bg-gray-800 text-white hover:bg-gray-900 flex items-center gap-1"
              onClick={handleSave}
            >
              {isDirty && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />}
              Save
            </button>
            <button
              className="px-3 py-1 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
              onClick={handleValidate}
            >
              Validate
            </button>
            <button
              className="px-3 py-1 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
              onClick={handleExport}
            >
              Export JSON
            </button>
            {aiEnabled && (
              <button
                className="px-3 py-1 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-700"
                onClick={() => setPopulateOpen(true)}
                title="Materialize this mapping's source into the knowledge graph (online, backend required)"
              >
                Populate
              </button>
            )}

            <div className="flex items-center gap-1 ml-auto">
              {(['draft', 'approved', 'rejected'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className={`px-2 py-0.5 text-[10px] rounded font-medium border transition-colors ${
                    mapping.status === s
                      ? s === 'approved' ? 'bg-green-500 text-white border-green-600'
                        : s === 'rejected' ? 'bg-red-500 text-white border-red-600'
                        : 'bg-amber-400 text-white border-amber-500'
                      : 'bg-white text-gray-500 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </>
        )}

        <div className={`h-5 border-l border-gray-200 ${mapping ? '' : 'ml-auto'}`} />

        <label
          className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer select-none whitespace-nowrap"
          title="Enable AI-assisted mapping generation. When off, the tool is fully manual and no network calls are made."
        >
          <input
            type="checkbox"
            checked={aiEnabled}
            onChange={toggleAiEnabled}
            className="accent-indigo-600"
          />
          AI assist
        </label>

        <div className="h-5 border-l border-gray-200" />

        <div className="flex items-center gap-1 bg-gray-100 rounded p-0.5">
          {viewModes.filter((v) => v.enabled).map((v) => (
            <button
              key={v.id}
              onClick={() => { if (v.disabled) return; setViewMode(v.id); v.onEnter?.(); }}
              disabled={v.disabled}
              className={`px-2.5 py-1 text-xs rounded font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                effectiveViewMode === v.id ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>

        {effectiveViewMode === 'editor' && (
          <button
            className="px-2 py-1 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
            onClick={() => setShowOntology((v) => !v)}
          >
            {showOntology ? 'Hide Ontology' : 'Show Ontology'}
          </button>
        )}
      </header>

      {/* ── Main ── */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 flex flex-col min-w-0 relative">
          {effectiveViewMode === 'runs' ? (
            <RunsPanel
              runs={runs}
              loading={runsLoading}
              onRefresh={loadRuns}
              fetchEntries={api.getPopulateRunEntries}
              fetchRun={api.getPopulateRun}
            />
          ) : effectiveViewMode === 'graph' ? (
            <OntologyGraphView classes={classes} properties={properties} mapping={mapping} />
          ) : effectiveViewMode === 'preview' && mapping ? (
            <MappingPreview mapping={mapping} schema={schema} properties={properties} />
          ) : !mapping ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-4">
              <div className="text-6xl">🗺</div>
              <div className="text-lg font-medium text-gray-500">No mapping loaded</div>
              <p className="text-sm text-gray-400 text-center max-w-sm">
                Select a data source above (or add one with <strong>+ Source</strong>),
                then click <strong>New</strong> to start or load an existing mapping.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 px-4 py-1.5 bg-white border-b border-gray-200 flex-shrink-0">
                <span className="text-xs text-gray-400 whitespace-nowrap">{mapping.source_name}</span>
                <span className="text-gray-300">/</span>
                <input
                  type="text"
                  value={mapping.name ?? ''}
                  onChange={(e) => handleMappingChange({ ...mapping, name: e.target.value || undefined })}
                  placeholder="Untitled mapping"
                  className="text-xs font-medium text-gray-700 bg-transparent border-b border-transparent hover:border-gray-300 focus:border-indigo-400 outline-none px-0.5 min-w-0 w-40"
                />
                <span className="text-xs text-gray-400">
                  — {mapping.subject_mappings.length} subject(s)
                </span>
                {isDirty && <span className="text-amber-500 font-medium text-xs">● unsaved</span>}
                <button
                  className="ml-auto px-3 py-1 text-xs rounded bg-indigo-100 text-indigo-700 hover:bg-indigo-200 font-medium"
                  onClick={() => setAddSubjectOpen(true)}
                >
                  + Add Subject Mapping
                </button>
              </div>

              <ReactFlowProvider>
                <MappingCanvas
                  schema={schema}
                  mapping={mapping}
                  classes={classes}
                  properties={properties}
                  sampleRecord={schema?.sample_records?.[sampleIndex] ?? {}}
                  onMappingChange={handleMappingChange}
                  onRequestAddProperty={handleRequestAddProperty}
                  onRequestEditInlineObject={handleRequestEditInlineObject}
                />
              </ReactFlowProvider>
            </>
          )}
        </div>

        {showOntology && effectiveViewMode === 'editor' && (
          <div className="w-64 flex-shrink-0">
            <OntologyPanel
              classes={classes}
              properties={properties}
              onAddSubject={(cls) => {
                if (!mapping) { toast('Create or load a mapping first', 'info'); return; }
                handleAddSubject(cls);
              }}
            />
          </div>
        )}
      </div>

      {/* ── Validation drawer ── */}
      {showValidation && validation && (
        <div className="absolute inset-x-0 bottom-0 bg-white border-t border-gray-200 shadow-xl z-20 max-h-64 overflow-y-auto">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200 sticky top-0">
            <span className="font-semibold text-sm">
              Validation —{' '}
              {validation.valid
                ? <span className="text-green-600">Valid</span>
                : <span className="text-red-600">{validation.errors.length} error(s)</span>}
              {validation.warnings.length > 0 && (
                <span className="text-amber-600 ml-2">{validation.warnings.length} warning(s)</span>
              )}
            </span>
            <button onClick={() => setShowValidation(false)} className="text-gray-400 hover:text-gray-700 text-xl">&times;</button>
          </div>
          <div className="px-4 py-3 space-y-1.5">
            {validation.errors.map((e, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-red-700">
                <span className="mt-0.5 flex-shrink-0">✖</span><span>{e}</span>
              </div>
            ))}
            {validation.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-amber-700">
                <span className="mt-0.5 flex-shrink-0">⚠</span><span>{w}</span>
              </div>
            ))}
            {validation.valid && validation.warnings.length === 0 && (
              <div className="text-xs text-green-700 font-medium">All checks passed.</div>
            )}
          </div>
        </div>
      )}

      {/* ── Toasts ── */}
      <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-2 rounded-lg shadow-lg text-sm font-medium pointer-events-auto ${
              t.kind === 'success' ? 'bg-green-600 text-white'
              : t.kind === 'error' ? 'bg-red-600 text-white'
              : 'bg-gray-800 text-white'
            }`}
          >
            {t.msg}
          </div>
        ))}
      </div>

      {/* ── Dialogs ── */}
      <NewMappingDialog
        open={newMappingOpen}
        sourceName={selectedSchemaName}
        aiEnabled={aiEnabled}
        generating={generating}
        onConfirm={handleNewMapping}
        onClose={() => setNewMappingOpen(false)}
      />

      {mapping && aiEnabled && (
        <PopulateDialog
          open={populateOpen}
          sourceName={mapping.source_name}
          populating={populating}
          onConfirm={handlePopulate}
          onClose={() => setPopulateOpen(false)}
        />
      )}

      <AddSourceDialog
        open={addSourceOpen}
        onSave={handleAddSource}
        onClose={() => setAddSourceOpen(false)}
      />

      <AddSubjectDialog
        open={addSubjectOpen}
        classes={classes}
        onSelect={(cls) => { handleAddSubject(cls); setAddSubjectOpen(false); }}
        onClose={() => setAddSubjectOpen(false)}
      />

      <AddPropertyDialog
        open={addPropState.open}
        subjectClassUri={addPropState.classUri}
        classes={classes}
        properties={properties}
        namespaces={mapping?.namespaces ?? {}}
        onSelect={(prop) => { handleAddProperty(prop); setAddPropState((s) => ({ ...s, open: false })); }}
        onClose={() => setAddPropState((s) => ({ ...s, open: false }))}
      />

      {inlineObjState.open && currentInlineVt && (
        <InlineObjectDialog
          open={inlineObjState.open}
          valueType={currentInlineVt}
          classes={classes}
          properties={properties}
          columns={schema?.columns ?? []}
          namespaces={mapping?.namespaces ?? {}}
          sampleRecord={schema?.sample_records?.[0] ?? {}}
          onChange={handleInlineObjectChange}
          onClose={() => setInlineObjState((s) => ({ ...s, open: false }))}
        />
      )}
    </div>
  );
}
