import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        // Apply COOP/COEP headers to all routes.
        // Required for Godot WASM to use SharedArrayBuffer (threads).
        // NOTE: These headers will break cross-origin iframes/popups if added in Phase 4.
        // Flag for review if OAuth or third-party embeds are introduced.
        source: '/(.*)',
        headers: [
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'require-corp',
          },
        ],
      },
    ]
  },
}

export default nextConfig
