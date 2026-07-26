import type {
  MappingDocument,
  GenerateMappingRequest,
  GeneratedMappingResponse,
  PopulateRequest,
  PopulateResponse,
  PopulateRun,
  RunSummary,
  RunEntry,
  ProvenanceManifest,
} from './types';

const BASE = '/api';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

export const api = {
  generateMapping: (payload: GenerateMappingRequest) =>
    req<GeneratedMappingResponse>('/mappings/generate', json('POST', payload)),

  populate: (payload: PopulateRequest) =>
    req<PopulateResponse>('/populate', json('POST', payload)),
  listPopulateRuns: () =>
    req<RunSummary[]>('/populate/runs'),
  getPopulateRun: (runId: string) =>
    req<PopulateRun>(`/populate/runs/${encodeURIComponent(runId)}`),
  getPopulateRunEntries: (runId: string): Promise<RunEntry[]> =>
    req<ProvenanceManifest>(`/populate/runs/${encodeURIComponent(runId)}/entries`).then((m) => m.entries),
};

export function normalizeGeneratedMapping(raw: GeneratedMappingResponse): MappingDocument {
  return {
    ...raw,
    id: '',
    status: 'draft',
    rag_enabled: raw.rag_enabled ?? false,
  };
}

export function toBackendMapping(mapping: MappingDocument): MappingDocument {
  return { ...mapping, include_descriptions: mapping.include_descriptions ?? false };
}
