/// <reference types="vite/client" />

// File System Access API — not yet fully typed in lib.dom.d.ts
interface FileSystemDirectoryHandle {
  entries(): AsyncIterableIterator<[string, FileSystemHandle]>;
}

interface Window {
  showDirectoryPicker(options?: { mode?: 'read' | 'readwrite' }): Promise<FileSystemDirectoryHandle>;
}

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_DEFAULT_BASE_URI?: string;
  readonly VITE_DEFAULT_NAMESPACE_PREFIX?: string;
  readonly VITE_DEFAULT_NAMESPACE_URI?: string;
  readonly VITE_LLM_PROVIDER?: string;
  readonly VITE_LLM_MODEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
