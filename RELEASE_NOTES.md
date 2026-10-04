Claude Harbor v0.1.0 is the first public experimental release: a native macOS manager for multiple independent Claude Desktop accounts and one-click synchronization of local Code sessions.

### Included

- Add another Claude Desktop profile, sign in separately, and open one/all profiles.
- Wait for replies, gently close ready apps, back up/sync and reopen with one button.
- Import readable old local history and keep divergent conversations as separate branches.
- Menu-bar shortcuts, pending-profile status, audit reports and transaction backups.
- Bundled Harbor backend scripts, English/Vietnamese documentation and screenshots.

### Download and requirements

Download **Claude-Harbor-0.1.0-macOS-arm64.zip** and move the extracted **Claude Harbor.app** into Applications.

Requires **Apple Silicon, macOS 14+, an official Claude Desktop installation at `/Applications/Claude.app`, and Apple Command Line Tools/Python 3**. The app is **ad-hoc signed, not notarized**. Harbor does not redistribute Claude's binaries, icon or account/session data.

See the README for installation, building from source and SHA-256 checksums.

### Validation and current scope

18 automated tests pass. A real three-profile installation was checked across 3,146 session groups with zero incomplete managed groups and zero conversation-content mismatches.

**Local Code on the same Mac only.** No web Chat/Cowork/cloud, cross-device sync, live shared-session writes or coordinated clone updater. Missing/deleted transcripts cannot be restored. Magpie is an experimental preset for the tested loopback gateway rather than a universal provider configuration UI. Intel source builds are available but not runtime-tested.

Independent community utility; not an Anthropic product. Source license: MIT.
