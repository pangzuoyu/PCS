/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PROJECT_ID?: string;
  readonly VITE_DEV_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}