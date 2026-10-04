import AppKit
let folder = URL(fileURLWithPath: CommandLine.arguments[1]); try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
let image = NSImage(size: NSSize(width: 1024, height: 1024)); image.lockFocus()
let bounds = NSBezierPath(roundedRect: NSRect(x: 22, y: 22, width: 980, height: 980), xRadius: 215, yRadius: 215)
NSGradient(starting: NSColor(calibratedRed: 0.10, green: 0.24, blue: 0.34, alpha: 1), ending: NSColor(calibratedRed: 0.05, green: 0.48, blue: 0.49, alpha: 1))!.draw(in: bounds, angle: -45)
for (i, x) in [170.0, 365.0, 560.0].enumerated() {
    let y = 510.0 - Double(i) * 96
    let panel = NSBezierPath(roundedRect: NSRect(x: x, y: y, width: 300, height: 255), xRadius: 35, yRadius: 35)
    NSColor(calibratedWhite: 1, alpha: 0.18 + Double(i) * 0.16).setFill(); panel.fill()
    NSColor.white.withAlphaComponent(0.85).setStroke(); panel.lineWidth = 8; panel.stroke()
    for dot in 0..<3 { NSColor.white.withAlphaComponent(0.8).setFill(); NSBezierPath(ovalIn: NSRect(x: x+24+Double(dot)*28, y: y+212, width: 13, height: 13)).fill() }
}
let arrow = NSBezierPath(); arrow.move(to: NSPoint(x: 255, y: 250)); arrow.curve(to: NSPoint(x: 775, y: 250), controlPoint1: NSPoint(x: 380, y: 135), controlPoint2: NSPoint(x: 650, y: 135)); arrow.lineWidth = 28; arrow.lineCapStyle = .round; NSColor.white.setStroke(); arrow.stroke()
let head = NSBezierPath(); head.move(to: NSPoint(x: 736, y: 220)); head.line(to: NSPoint(x: 793, y: 251)); head.line(to: NSPoint(x: 763, y: 306)); head.lineWidth = 24; head.lineCapStyle = .round; head.lineJoinStyle = .round; head.stroke()
image.unlockFocus()
for (size, name) in [(16,"16x16"),(32,"16x16@2x"),(32,"32x32"),(64,"32x32@2x"),(128,"128x128"),(256,"128x128@2x"),(256,"256x256"),(512,"256x256@2x"),(512,"512x512"),(1024,"512x512@2x")] {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    image.draw(in: NSRect(x: 0, y: 0, width: size, height: size)); NSGraphicsContext.restoreGraphicsState()
    try rep.representation(using: .png, properties: [:])!.write(to: folder.appendingPathComponent("icon_\(name).png"))
}
