import AppKit
import Foundation

struct Profile: Decodable, Sendable {
    let id: String; let name: String; let kind: String; let bundle: String; let bundleID: String
    let ready: Bool; let running: Bool; let sessions: Int; let archived: Int
}
struct Summary: Decodable { let profiles: [Profile]; let pending: [String]; let lastSync: Report? }
struct Check: Decodable { let busy: [String]; let errors: [String]; let running: [String]; let eligible: [String]; let pending: [String] }
struct Report: Decodable { let profiles: Int; let sessions: Int; let newBranches: Int; let filesChanged: Int; let backup: String; let warnings: Int?; let pending: [String]? }
struct BackendResult: Sendable { let status: Int32; let data: Data; let error: String }
let support = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support")
let legacyRoot = support.appendingPathComponent("ClaudeThreeDesktop")
let root = FileManager.default.fileExists(atPath: legacyRoot.appendingPathComponent("profiles.json").path) ? legacyRoot : support.appendingPathComponent("ClaudeHarbor")

func executePython(_ arguments: [String]) async throws -> Data {
    let result: BackendResult = try await withCheckedThrowingContinuation { continuation in
        let process = Process(); let output = Pipe(); let errors = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = arguments
        process.standardOutput = output; process.standardError = errors
        process.terminationHandler = { finished in
            continuation.resume(returning: BackendResult(status: finished.terminationStatus,
                data: output.fileHandleForReading.readDataToEndOfFile(),
                error: String(decoding: errors.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)))
        }
        do { try process.run() } catch { continuation.resume(throwing: error) }
    }
    guard result.status == 0 else { throw NSError(domain: "ClaudeHarbor", code: Int(result.status), userInfo: [NSLocalizedDescriptionKey: result.error]) }
    return result.data
}

func backend(_ arguments: [String]) async throws -> Data {
    try await executePython([root.appendingPathComponent("manager.py").path] + arguments)
}

@MainActor final class Manager: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var profiles: [Profile] = []
    let status = NSTextField(wrappingLabelWithString: "Đang đọc các profile…")
    let footer = NSTextField(wrappingLabelWithString: "")
    let sync = NSButton(title: "Đồng bộ tất cả", target: nil, action: nil)
    let add = NSButton(title: "+ Thêm tài khoản", target: nil, action: nil)
    let openAll = NSButton(title: "Mở tất cả", target: nil, action: nil)
    let refresh = NSButton(title: "Làm mới", target: nil, action: nil)
    let rows = NSStackView()
    var working = false; var waiting = false; var operation: Task<Void, Never>?
    var item: NSStatusItem!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu(); let appMenu = NSMenuItem(); menu.addItem(appMenu)
        let appSub = NSMenu(); appMenu.submenu = appSub
        appSub.addItem(withTitle: "Thoát Claude Harbor", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 700, height: 540), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Claude Harbor"; window.center(); window.isReleasedWhenClosed = false
        let title = NSTextField(labelWithString: "Các tài khoản Claude")
        title.font = .boldSystemFont(ofSize: 25); title.frame = NSRect(x: 28, y: 480, width: 640, height: 36)
        let subtitle = NSTextField(wrappingLabelWithString: "Mỗi tài khoản chạy trong một app riêng. Tiếp tục lịch sử Code giữa các tài khoản bằng một lần bấm.")
        subtitle.frame = NSRect(x: 28, y: 435, width: 644, height: 38); subtitle.textColor = .secondaryLabelColor
        add.frame = NSRect(x: 24, y: 389, width: 164, height: 32); add.target = self; add.action = #selector(addProfile)
        openAll.frame = NSRect(x: 196, y: 389, width: 128, height: 32); openAll.target = self; openAll.action = #selector(openEveryProfile)
        refresh.frame = NSRect(x: 328, y: 389, width: 110, height: 32); refresh.target = self; refresh.action = #selector(refreshNow)
        for b in [add, openAll, refresh, sync] { b.bezelStyle = .rounded }
        let scroll = NSScrollView(frame: NSRect(x: 28, y: 185, width: 644, height: 193)); scroll.hasVerticalScroller = true; scroll.drawsBackground = false
        rows.orientation = .vertical; rows.alignment = .leading; rows.spacing = 10
        scroll.documentView = rows
        footer.frame = NSRect(x: 28, y: 141, width: 644, height: 35); footer.font = .systemFont(ofSize: 12); footer.textColor = .secondaryLabelColor
        status.frame = NSRect(x: 28, y: 58, width: 644, height: 76); status.font = .systemFont(ofSize: 13)
        sync.frame = NSRect(x: 451, y: 18, width: 220, height: 34); sync.target = self; sync.action = #selector(synchronize); sync.keyEquivalent = "\r"
        let report = NSButton(title: "Báo cáo & sao lưu", target: self, action: #selector(showReport)); report.bezelStyle = .rounded; report.frame = NSRect(x: 24, y: 18, width: 175, height: 34)
        for view in [title, subtitle, add, openAll, refresh, scroll, footer, status, sync, report] { window.contentView?.addSubview(view) }
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = "C≋"
        let quick = NSMenu()
        for (name, action) in [("Claude Harbor…", #selector(showWindow)), ("Mở tất cả", #selector(openEveryProfile)), ("Đồng bộ tất cả", #selector(synchronize))] {
            let entry = quick.addItem(withTitle: name, action: action, keyEquivalent: ""); entry.target = self
        }
        item.menu = quick
        showWindow(); setWorking(true)
        Task {
            do {
                if let bootstrap = Bundle.main.resourceURL?.appendingPathComponent("backend/bootstrap.py"), FileManager.default.fileExists(atPath: bootstrap.path) {
                    _ = try await executePython([bootstrap.path])
                }
                setWorking(false); await load()
            } catch { setWorking(false); status.stringValue = "Không khởi tạo được runtime: " + error.localizedDescription }
        }
    }
    @objc func showWindow() { window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true) }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { showWindow(); return true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if waiting { operation?.cancel(); return .terminateNow }; return working ? .terminateCancel : .terminateNow
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func setWorking(_ value: Bool) {
        working = value; add.isEnabled = !value; openAll.isEnabled = !value; refresh.isEnabled = !value; sync.isEnabled = !value
        for case let row as NSStackView in rows.arrangedSubviews { for case let b as NSButton in row.arrangedSubviews { b.isEnabled = !value } }
        if value { window.styleMask.remove(.closable) } else { window.styleMask.insert(.closable) }
    }
    func load() async {
        do {
            let summary = try JSONDecoder().decode(Summary.self, from: try await backend(["status"]))
            profiles = summary.profiles
            for view in rows.arrangedSubviews { rows.removeArrangedSubview(view); view.removeFromSuperview() }
            for (index, p) in profiles.enumerated() {
                let row = NSStackView(); row.orientation = .horizontal; row.spacing = 12
                let marker = NSTextField(labelWithString: p.running ? "●" : "○"); marker.textColor = p.running ? .systemGreen : .secondaryLabelColor
                let text = NSTextField(wrappingLabelWithString: "\(p.name)\n\(p.kind == "magpie" ? "Magpie gateway" : "Tài khoản Claude") · \(p.ready ? "\(p.sessions) phiên Code" : "Chờ đăng nhập / mở tab Code")")
                text.font = .systemFont(ofSize: 13)
                let button = NSButton(title: "Mở", target: self, action: #selector(openOne(_:))); button.tag = index; button.bezelStyle = .rounded; button.isEnabled = !working
                row.addArrangedSubview(marker); row.addArrangedSubview(text); row.addArrangedSubview(button)
                row.widthAnchor.constraint(equalToConstant: 620).isActive = true; row.heightAnchor.constraint(equalToConstant: 50).isActive = true
                marker.widthAnchor.constraint(equalToConstant: 18).isActive = true; text.widthAnchor.constraint(equalToConstant: 493).isActive = true
                rows.addArrangedSubview(row)
            }
            rows.frame = NSRect(x: 0, y: 0, width: 620, height: max(193, profiles.count * 60))
            footer.stringValue = "Đồng bộ Code local, gồm phiên cũ và đã lưu trữ. Chat web / Cowork / cloud chưa được hỗ trợ."
            if !working {
                if let last = summary.lastSync { status.stringValue = "Lần gần nhất: \(last.sessions) phiên trong \(last.profiles) app.\nNhấn Đồng bộ tất cả: chờ trả lời xong → đóng app → sao lưu, đồng bộ → mở lại."
                } else { status.stringValue = "Thêm tài khoản, đăng nhập trong cửa sổ Claude rồi mở tab Code. Sau đó bấm Đồng bộ tất cả." }
                if !summary.pending.isEmpty { status.stringValue += "\n\(summary.pending.count) profile đang chờ khởi tạo Code." }
            }
            sync.isEnabled = !working && profiles.filter(\.ready).count >= 2
        } catch { status.stringValue = error.localizedDescription }
    }
    @objc func refreshNow() { guard !working else { return }; Task { await load() } }
    func open(_ selected: [Profile]) async {
        var failures: [String] = []
        for profile in selected {
            let config = NSWorkspace.OpenConfiguration(); config.activates = selected.count == 1
            let failure: String? = await withCheckedContinuation { continuation in
                NSWorkspace.shared.openApplication(at: URL(fileURLWithPath: profile.bundle), configuration: config) { _, error in continuation.resume(returning: error?.localizedDescription) }
            }
            if let failure { failures.append(profile.name + ": " + failure) }
        }
        if !failures.isEmpty { status.stringValue = failures.joined(separator: "\n") }
    }
    @objc func openOne(_ sender: NSButton) { guard !working, profiles.indices.contains(sender.tag) else { return }; let p = profiles[sender.tag]; Task { await open([p]); await load() } }
    @objc func openEveryProfile() { guard !working else { return }; Task { await open(profiles); await load() } }
    @objc func addProfile() {
        guard !working else { return }
        let alert = NSAlert(); alert.messageText = "Thêm bản Claude"; alert.informativeText = "Bản mới có đăng nhập riêng. Sau khi mở, đăng nhập rồi vào tab Code và tạo một phiên local."
        alert.addButton(withTitle: "Tạo và mở"); alert.addButton(withTitle: "Hủy")
        let accessory = NSView(frame: NSRect(x: 0, y: 0, width: 350, height: 76))
        let name = NSTextField(frame: NSRect(x: 0, y: 42, width: 350, height: 24)); name.placeholderString = "Ví dụ: Công việc, Cá nhân…"
        let kind = NSPopUpButton(frame: NSRect(x: 0, y: 4, width: 350, height: 30)); kind.addItems(withTitles: ["Tài khoản Claude Pro / Max", "Magpie GPT-6.1 (gateway hiện tại)"])
        accessory.addSubview(name); accessory.addSubview(kind); alert.accessoryView = accessory
        alert.beginSheetModal(for: window) { response in
            guard response == .alertFirstButtonReturn else { return }
            let title = name.stringValue; let type = kind.indexOfSelectedItem == 1 ? "magpie" : "claude"
            self.setWorking(true); self.status.stringValue = "Đang tạo bản Claude riêng…"
            Task {
                do {
                    _ = try await backend(["create", title, type]); await self.load()
                    self.setWorking(false)
                    if let p = self.profiles.last { await self.open([p]) }
                    self.status.stringValue = "Đã tạo app. Đăng nhập trong Claude và mở tab Code, rồi bấm Làm mới để bật đồng bộ."
                } catch { self.setWorking(false); self.status.stringValue = error.localizedDescription }
            }
        }
    }
    @objc func showReport() { NSWorkspace.shared.open(root) }
    @objc func synchronize() {
        if waiting { operation?.cancel(); return }; guard !working else { return }
        setWorking(true); operation = Task { await performSync() }
    }
    func performSync() async {
        var previous: [Profile] = []; var closing = false
        do {
            status.stringValue = "Đang kiểm tra các phiên…"
            var check: Check
            while true {
                check = try JSONDecoder().decode(Check.self, from: try await backend(["check"]))
                if !check.errors.isEmpty { throw NSError(domain: "Sync", code: 1, userInfo: [NSLocalizedDescriptionKey: check.errors.joined(separator: "\n")]) }
                if check.busy.isEmpty { break }
                waiting = true; sync.title = "Dừng chờ"; sync.isEnabled = true
                status.stringValue = "Chờ trả lời xong: " + check.busy.joined(separator: "; ")
                try await Task.sleep(nanoseconds: 2_000_000_000)
            }
            waiting = false; sync.title = "Đồng bộ tất cả"; sync.isEnabled = false
            try Task.checkCancellation()
            let selected = profiles.filter { check.eligible.contains($0.id) }
            let applications = selected.flatMap { NSRunningApplication.runningApplications(withBundleIdentifier: $0.bundleID) }
            previous = selected.filter { p in applications.contains { $0.bundleIdentifier == p.bundleID } }
            status.stringValue = "Đang đóng các bản Claude và lưu phiên…"; closing = true
            for app in applications { _ = app.terminate() }
            for _ in 0..<150 {
                if applications.allSatisfy(\.isTerminated) { break }; try await Task.sleep(nanoseconds: 200_000_000)
            }
            guard applications.allSatisfy(\.isTerminated) else { throw NSError(domain: "Sync", code: 2, userInfo: [NSLocalizedDescriptionKey: "Một app chưa đóng được; chưa ghi dữ liệu đồng bộ."]) }
            status.stringValue = "Đang sao lưu và đồng bộ toàn bộ lịch sử Code…"
            let report = try JSONDecoder().decode(Report.self, from: try await backend(["sync"]))
            status.stringValue = "Đang mở lại các app…"; await open(selected)
            await load()
            status.stringValue = "Đã đồng bộ \(report.sessions) phiên vào \(report.profiles) app. \(report.filesChanged) tệp cập nhật.\(report.newBranches > 0 ? " Giữ thêm \(report.newBranches) nhánh." : "")\nCó bản sao lưu trong Báo cáo & sao lưu."
            if (report.warnings ?? 0) > 0 { status.stringValue += " Có bản ghi rỗng / thiếu transcript; xem history-audit.json." }
            if !(report.pending ?? []).isEmpty { status.stringValue += " \(report.pending!.count) profile chờ đăng nhập / khởi tạo Code." }
        } catch is CancellationError { status.stringValue = "Đã dừng chờ, chưa thay đổi lịch sử."
        } catch {
            if closing { await open(previous) }; status.stringValue = "Chưa hoàn tất: \(error.localizedDescription)"
        }
        waiting = false; operation = nil; sync.title = "Đồng bộ tất cả"; setWorking(false)
    }
}
@main struct EntryPoint {
    @MainActor static func main() {
        let app = NSApplication.shared; let delegate = Manager()
        app.setActivationPolicy(.regular); app.delegate = delegate
        withExtendedLifetime(delegate) { app.run() }
    }
}
