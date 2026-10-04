# Changelog

## v0.1.0 — 2026-10-04

First public experimental release of **Claude Harbor**.

- Native AppKit manager with independent Claude Desktop profiles and a menu-bar shortcut.
- Create profiles, open one/all apps, and synchronize ready profiles with one button.
- Preserve separate account logins, import readable old local Code history, and retain divergent conversation branches.
- Back up writes, roll back failed transactions, and audit unavailable/empty transcript records.
- Bundle Harbor's backend scripts for first-launch setup on another Mac; retain the original prototype's registry and login/session data.
- Include a narrowly scoped experimental Magpie local gateway preset.
- English/Vietnamese README and real application screenshots.

**Validation:** 18 automated tests pass. The three-profile original installation was verified with 3,146 session groups, zero incomplete managed groups and zero conversation-content mismatches.

**Release asset:** macOS 14+, Apple Silicon arm64. Ad-hoc signed; not notarized. Requires an installed official Claude Desktop plus Apple Command Line Tools/Python 3. No Claude binaries, account data or transcripts are redistributed.

**Limits:** local Code only; no web Chat/Cowork/cloud or multi-device/live shared-session sync; no coordinated clone updater; experimental Magpie remap rather than arbitrary provider configuration. Intel can be built from source but is not runtime-tested in this release.
