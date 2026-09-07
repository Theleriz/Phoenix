/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Dev-scaffold only: the same shared secret the Python imu-gateway uses to
   * authenticate ingestion/WS. Shipping it to every patient's browser bundle
   * is a known architectural gap (see docs/architecture/client-side-sensor-connectivity.md)
   * -- fine for this local dev stand, not for a real deployment.
   */
  readonly VITE_PHOENIX_GATEWAY_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
