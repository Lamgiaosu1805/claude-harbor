# Session synchronization

Harbor isolates each profile's GUI and Code directories. It does not share a live transcript file between processes.

1. Resolve the signed-in Code identity for each registered profile. Pending profiles are excluded until initialized.
2. Check active Claude SDK processes and saved completed-turn markers. Wait for active replies, with cancellation available during this stage.
3. Ask the ready Claude apps to terminate normally. Refuse to write if a process remains open.
4. Hold an exclusive sync lock. Launcher processes wait on this lock before starting Electron.
5. Discover Desktop records and main Code transcripts from managed profiles and available local history locations. Read the original Claude stores without modifying them.
6. Compare stable user/assistant message signatures. Extend prefix histories; preserve divergent maximal histories as separate branches.
7. Copy needed history and write Desktop records atomically. Preserve target settings/model/permissions and never copy source login state. Keep previous-file backups and commit lineage metadata last.
8. Reopen ready profiles and show counts plus any audit warnings.

Readable old/archived sessions are included. An unavailable transcript, malformed record or empty transcript produces an audit entry instead of a false success. `history-audit.json` can contain private project paths and titles; do not attach it publicly without reviewing/redacting it.

The backup directory is accessible through **Báo cáo & sao lưu**. Automatic rollback handles a failed write transaction. There is not yet a user-facing rollback browser for choosing an earlier successful sync.

Account-bound MCP permissions are not cloned from the source. Workspace files stay in their original locations; Harbor syncs session history rather than copying a project checkout. Tools may require renewed permissions in the target account.

## Magpie preset

The preset uses a loopback Anthropic-compatible gateway at `http://127.0.0.1:3425`, loopback key `magpie-claude-desktop`, and the Desktop remapped model ID `mythos-magpie-1026517788`. The loopback key is a gateway convention, not a user credential. Keep the gateway running. This preset was validated on the original installation; remapping and upstream model availability can change between Magpie versions.

## Compatibility

Cloning and history import rely on Claude Desktop's current local storage and Electron bundle layout. The clone preserves the internal `CFBundleName=Claude`; vendor frameworks stay signed, while the native wrapper and outer app are signed ad-hoc with JIT/library validation entitlements. The release includes only Harbor code, its own icon and runtime scripts. It never includes Claude.app, Claude's icon, account databases or conversation transcripts.
