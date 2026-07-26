import type {
  OntologyClass,
  OntologyProperty,
  ExtractedSchema,
  SchemaInfo,
  MappingDocument,
  MappingInfo,
} from '../types';
import { parseTurtleOntology } from './parseOntology';

// ── Ontology file format ──────────────────────────────────────────────────────
// ontology.ttl in the workspace root — standard OWL/RDFS Turtle file

export interface WorkspaceOntology {
  classes: OntologyClass[];
  properties: OntologyProperty[];
}

// ── Workspace interface ───────────────────────────────────────────────────────

export interface Workspace {
  readonly name: string;
  getOntology(): Promise<WorkspaceOntology>;
  listSchemas(): Promise<SchemaInfo[]>;
  getSchema(filename: string): Promise<ExtractedSchema>;
  saveSchema(schema: ExtractedSchema): Promise<{ filename: string }>;
  deleteSchema(filename: string): Promise<void>;
  listMappings(): Promise<MappingInfo[]>;
  getMapping(filename: string): Promise<MappingDocument>;
  saveMapping(doc: MappingDocument): Promise<{ id: string; filename: string }>;
  deleteMapping(filename: string): Promise<void>;
}

// ── File System helpers ───────────────────────────────────────────────────────

async function readJson<T>(fh: FileSystemFileHandle): Promise<T> {
  const file = await fh.getFile();
  return JSON.parse(await file.text()) as T;
}

async function writeJson(
  dir: FileSystemDirectoryHandle,
  filename: string,
  data: unknown,
): Promise<void> {
  const fh = await dir.getFileHandle(filename, { create: true });
  const writable = await fh.createWritable();
  await writable.write(JSON.stringify(data, null, 2));
  await writable.close();
}

async function getOrCreateSubdir(
  root: FileSystemDirectoryHandle,
  name: string,
): Promise<FileSystemDirectoryHandle> {
  return root.getDirectoryHandle(name, { create: true });
}

// ── File System Workspace ─────────────────────────────────────────────────────

class FileSystemWorkspace implements Workspace {
  readonly name: string;

  constructor(private root: FileSystemDirectoryHandle) {
    this.name = root.name;
  }

  async getOntology(): Promise<WorkspaceOntology> {
    try {
      const fh = await this.root.getFileHandle('ontology.ttl');
      const file = await fh.getFile();
      const text = await file.text();
      return parseTurtleOntology(text);
    } catch {
      return { classes: [], properties: [] };
    }
  }

  async listSchemas(): Promise<SchemaInfo[]> {
    const dir = await getOrCreateSubdir(this.root, 'schemas');
    const result: SchemaInfo[] = [];
    for await (const [name, handle] of dir.entries()) {
      if (handle.kind !== 'file' || !name.endsWith('.json')) continue;
      try {
        const schema = await readJson<ExtractedSchema>(handle as FileSystemFileHandle);
        result.push({
          source_name: schema.source_name,
          source_type: schema.source_type,
          column_count: schema.columns.length,
          filename: name,
        });
      } catch {
        // skip malformed files
      }
    }
    return result.sort((a, b) => a.source_name.localeCompare(b.source_name));
  }

  // filename is the literal file name in schemas/ (e.g. "customers.json")
  async getSchema(filename: string): Promise<ExtractedSchema> {
    const dir = await getOrCreateSubdir(this.root, 'schemas');
    const fh = await dir.getFileHandle(filename);
    return readJson<ExtractedSchema>(fh);
  }

  async saveSchema(schema: ExtractedSchema): Promise<{ filename: string }> {
    const dir = await getOrCreateSubdir(this.root, 'schemas');
    const filename = `${schema.source_name}.json`;
    await writeJson(dir, filename, schema);
    return { filename };
  }

  // filename is the literal file name in schemas/ (e.g. "customers.json")
  async deleteSchema(filename: string): Promise<void> {
    const dir = await getOrCreateSubdir(this.root, 'schemas');
    await dir.removeEntry(filename);
  }

  async listMappings(): Promise<MappingInfo[]> {
    const dir = await getOrCreateSubdir(this.root, 'mappings');
    const result: MappingInfo[] = [];
    for await (const [name, handle] of dir.entries()) {
      if (handle.kind !== 'file' || !name.endsWith('.json')) continue;
      try {
        const doc = await readJson<MappingDocument>(handle as FileSystemFileHandle);
        result.push({
          id: doc.id,
          name: doc.name,
          filename: name,
          source_name: doc.source_name,
          status: doc.status,
          generation_timestamp: doc.generation_timestamp,
          llm_model: doc.llm_model,
          strategy: doc.strategy,
        });
      } catch {
        // skip malformed files
      }
    }
    return result.sort((a, b) =>
      b.generation_timestamp.localeCompare(a.generation_timestamp),
    );
  }

  // filename is the literal file name in mappings/ (e.g. "uuid.json")
  async getMapping(filename: string): Promise<MappingDocument> {
    const dir = await getOrCreateSubdir(this.root, 'mappings');
    const fh = await dir.getFileHandle(filename);
    return readJson<MappingDocument>(fh);
  }

  async saveMapping(doc: MappingDocument): Promise<{ id: string; filename: string }> {
    const dir = await getOrCreateSubdir(this.root, 'mappings');
    const id = doc.id || crypto.randomUUID();
    const slug = doc.source_name.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
    const filename = `${slug}-${id}.json`;
    await writeJson(dir, filename, { ...doc, id });
    return { id, filename };
  }

  // filename is the literal file name in mappings/ (e.g. "uuid.json")
  async deleteMapping(filename: string): Promise<void> {
    const dir = await getOrCreateSubdir(this.root, 'mappings');
    await dir.removeEntry(filename);
  }
}

// ── Public opener ─────────────────────────────────────────────────────────────

export function isFileSystemAccessSupported(): boolean {
  return typeof window !== 'undefined' && 'showDirectoryPicker' in window;
}

/** Prompts the user to pick a folder; throws AbortError if cancelled. */
export async function openWorkspace(): Promise<Workspace> {
  if (!isFileSystemAccessSupported()) {
    throw new Error('File System Access API is not supported in this browser. Use Chrome or Edge.');
  }
  const root = await window.showDirectoryPicker({ mode: 'readwrite' });
  return new FileSystemWorkspace(root);
}
