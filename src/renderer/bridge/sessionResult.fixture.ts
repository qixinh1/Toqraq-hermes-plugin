/** Valid session snapshot shared by focused client tests. */

import type { SessionResult } from '../contracts/generated.js'

export function sessionResult(): SessionResult {
  return {
    id: 'session-1',
    run_revision: 2,
    runtime: {
      engine: 'godot',
      version: '4.7.1',
      build_id: 'godot-4.7.1+toqraq.1',
      distribution_id: 'toqraq.windows',
      platform: 'windows',
      architecture: 'x86_64',
    },
    project_dir: 'D:/game',
    root_pid: 42,
    process_state: 'running',
    alive: true,
    exit_code: null,
    started_at: 1,
    bridge: { id: 'toqraq.bridge', protocol: '1.0', capabilities: [] },
    capabilities: ['toqraq.preview.display'],
    preview: {
      state: 'ready',
      error: null,
      surface: { kind: 'native_window', viewport_size: { width: 960, height: 540 } },
    },
    perception: { state: 'ready', error: null },
    control: { state: 'ready', error: null },
  }
}
