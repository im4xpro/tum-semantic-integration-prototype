// ── Ontology ─────────────────────────────────────────────────────────────────

export interface OntologyClass {
  uri: string;
  label: string;
  comment?: string;
  subclass_of: string[];
  is_extension: boolean;
}

export interface OntologyProperty {
  uri: string;
  label: string;
  comment?: string;
  domain: string[];
  range_: string[];
  is_object_property: boolean;
  is_extension: boolean;
}

// ── Schema ────────────────────────────────────────────────────────────────────

export interface ColumnSchema {
  name: string;
  data_type: string;
  is_primary_key: boolean;
  is_nullable: boolean;
}

export interface ExtractedSchema {
  source_name: string;
  source_type: string;
  columns: ColumnSchema[];
  inferred_fields: ColumnSchema[];
  sample_records: Record<string, unknown>[];
}

export interface SchemaInfo {
  source_name: string;
  source_type: string;
  column_count: number;
  filename: string;
}

// ── Mapping models (mirrors Python models) ───────────────────────────────────

export interface PropertySource {
  source: 'column' | 'constant' | 'row_index';
  column_name?: string;
  constant_value?: string;
}

export interface CodeTransformation {
  expression: string;
  language?: 'python';
}

export interface TypeMapping {
  class_uri: string;
}

export interface ValueType {
  type: 'literal' | 'iri';
  type_mappings: TypeMapping[];
  property_mappings: PropertyMapping[];
}

export interface ValueDefinition {
  value_source: PropertySource;
  transformation?: CodeTransformation;
  value_type: ValueType;
}

export type MappingBasis = 'name' | 'description' | 'value' | 'structural' | 'weak';

export interface PropertyMapping {
  property_uri: string;
  values: ValueDefinition[];
  confidence?: number;
  reasoning?: string;
  basis?: MappingBasis;
}

export interface SubjectMapping {
  label?: string;
  subject: PropertySource;
  subject_transformation?: CodeTransformation;
  type_mappings: TypeMapping[];
  property_mappings: PropertyMapping[];
  confidence?: number;
  reasoning?: string;
  basis?: MappingBasis;
}

export interface MappingDocument {
  id: string;
  name?: string;
  source_name: string;
  llm_model: string;
  strategy: string;
  ontology_format: string;
  rag_enabled: boolean;
  base_uri: string;
  namespaces: Record<string, string>;
  subject_mappings: SubjectMapping[];
  unmapped_fields: string[];
  generation_timestamp: string;
  prompt_tokens: number;
  completion_tokens: number;
  status: 'draft' | 'approved' | 'superseded' | 'rejected';
  reviewed_by?: string;
  reviewed_at?: string;
  superseded_by?: string;
  include_descriptions?: boolean;
  system_prompt?: string;
  user_prompt?: string;
  raw_response?: string;
}

export type MappingStrategy = 'zero_shot' | 'few_shot' | 'chain_of_thought';
export type OntologyFormat = 'turtle' | 'compact' | 'class_list';
export type LLMProvider = 'anthropic' | 'openai' | 'ollama' | 'fortiss' | 'openrouter';

export interface GenerateMappingRequest {
  source_schema: ExtractedSchema;
  strategy: MappingStrategy;
  provider: LLMProvider;
  llm_model: string;
  ontology_format: OntologyFormat;
  include_descriptions: boolean;
  column_descriptions: Record<string, string> | null;
  temperature: number;
}

export type GeneratedMappingResponse = Omit<MappingDocument, 'status' | 'rag_enabled'> & {
  status?: MappingDocument['status'];
  rag_enabled?: boolean;
};

export type PopulateConnector = 'postgres' | 'mongodb' | 'timescale';
export type RunStatus = 'queued' | 'mapping' | 'extracting' | 'completed' | 'failed' | 'cancelled';

export interface PopulateRequest {
  mapping: MappingDocument;
  source_name: string;
  connector: PopulateConnector;
  table?: string;
  data_limit?: number;
}

export interface RunStats {
  records_processed: number;
  entities_extracted: number;
  relations_extracted: number;
  triples_written: number;
  triples_in_db: number;
  duration_seconds: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface PopulateRun {
  id: string;
  status: RunStatus;
  mapping_id?: string | null;
  named_graph?: string | null;
  stats: RunStats;
  error?: string | null;
  created_at: string;
}

export interface PopulateResponse {
  run: PopulateRun;
  provenance_path: string;
}

export interface RunSummary {
  id: string;
  source_name: string;
  mapping_id?: string | null;
  status: RunStatus;
  records_processed: number;
  entities_extracted: number;
  relations_extracted: number;
  triples_in_db: number;
  created_at: string;
  target_named_graph?: string | null;
}

export interface RunEntry {
  subject_uri: string;
  source_record_id: string;
  class_uri?: string;
}

export interface ProvenanceManifest {
  run_id: string;
  source_name: string;
  mapping_name?: string | null;
  target_named_graph?: string | null;
  entry_count: number;
  entries: RunEntry[];
}

export interface MappingInfo {
  id: string;
  name?: string;
  filename: string;
  source_name: string;
  status: string;
  generation_timestamp: string;
  llm_model: string;
  strategy: string;
}

// ── API responses ─────────────────────────────────────────────────────────────

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}
