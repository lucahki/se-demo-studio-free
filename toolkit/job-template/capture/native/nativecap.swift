// nativecap: record and drive one native macOS app (for example the Webex desktop app) for the demo studio.
// Built on first use by capture/native.js with the Swift compiler from the Xcode Command Line Tools.
//
//   nativecap check [--prompt]       permissions as JSON (--prompt opens the macOS permission requests)
//   nativecap list                   running apps that have windows on screen, as JSON
//   nativecap serve --app <name|bundle id> [--mode app|window]
//                                    JSON lines on stdin and stdout: {"id":1,"op":"prep",...} -> {"id":1,"ok":true,...}
//
// Coordinates in every op are frame pixels: the app's main window mapped to 1920x1080, the same space as Chrome
// takes, so the edit, camera, cursor, and redaction code work unchanged. The window is resized to 16:9 by "prep".
// Recording uses ScreenCaptureKit without the real cursor (the render draws the logged pointer path). In "app"
// mode (default) every window of the app is captured, cropped to the main window, so its menus, pop-ups, and
// call windows show and other apps' windows over it do not. "window" mode captures only the main window.
// Input goes through real mouse and keyboard events: a click or scroll is refused when another app's window covers
// the point, and typing is refused when the app is not in front, so a take can never click, scroll, or type into
// another app.
// Needs Screen Recording and Accessibility for the terminal app that runs it (System Settings, Privacy & Security).
import AppKit
import ApplicationServices
import CoreMedia
import CoreVideo
import Foundation
import ImageIO
import ScreenCaptureKit
import UniformTypeIdentifiers

// ---------- output ----------
let outLock = NSLock()
func emit(_ obj: [String: Any]) {
  outLock.lock(); defer { outLock.unlock() }
  guard let d = try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]) else { return }
  FileHandle.standardOutput.write(d); FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}
struct Fail: Error { let msg: String; init(_ m: String) { msg = m } }

// Run an async call from a synchronous queue (the command queues are not the Swift concurrency executor).
func blocking<T>(_ f: @escaping () async throws -> T) throws -> T {
  let sem = DispatchSemaphore(value: 0); var res: Result<T, Error>!
  Task.detached { do { res = .success(try await f()) } catch { res = .failure(error) }; sem.signal() }
  sem.wait(); return try res.get()
}

// ---------- permissions ----------
func permissions(prompt: Bool) -> [String: Any] {
  if prompt {
    if !CGPreflightScreenCaptureAccess() { _ = CGRequestScreenCaptureAccess() }
    let opt = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
    _ = AXIsProcessTrustedWithOptions(opt)
  }
  return ["screen": CGPreflightScreenCaptureAccess(), "accessibility": AXIsProcessTrusted()]
}

// ---------- windows ----------
func windowList() -> [[String: Any]] {
  (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]) ?? []
}
func bounds(_ w: [String: Any]) -> CGRect {
  guard let b = w[kCGWindowBounds as String] as? NSDictionary, let r = CGRect(dictionaryRepresentation: b) else { return .zero }
  return r
}
func findApp(_ q: String) -> NSRunningApplication? {
  let apps = NSWorkspace.shared.runningApplications.filter { $0.activationPolicy == .regular }
  let l = q.lowercased()
  return apps.first { $0.bundleIdentifier?.lowercased() == l } ?? apps.first { $0.localizedName?.lowercased() == l }
    ?? apps.first { ($0.localizedName ?? "").lowercased().hasPrefix(l) }
}
// the app's largest normal window on screen (layer 0)
func mainWindow(_ pid: pid_t) -> (id: CGWindowID, frame: CGRect, title: String)? {
  let ws = windowList().filter { ($0[kCGWindowOwnerPID as String] as? Int32) == pid && ($0[kCGWindowLayer as String] as? Int) == 0 }
    .map { (id: CGWindowID(($0[kCGWindowNumber as String] as? Int) ?? 0), frame: bounds($0), title: ($0[kCGWindowName as String] as? String) ?? "") }
    .filter { $0.frame.width >= 300 && $0.frame.height >= 200 }
  return ws.max { $0.frame.width * $0.frame.height < $1.frame.width * $1.frame.height }
}
func displayFor(_ r: CGRect) -> CGDirectDisplayID {
  var ids = [CGDirectDisplayID](repeating: 0, count: 16); var n: UInt32 = 0
  CGGetDisplaysWithPoint(CGPoint(x: r.midX, y: r.midY), 16, &ids, &n)
  return n > 0 ? ids[0] : CGMainDisplayID()
}
func scaleOf(_ d: CGDirectDisplayID) -> Double {
  guard let m = CGDisplayCopyDisplayMode(d), m.width > 0 else { return 1 }
  return Double(m.pixelWidth) / Double(m.width)
}
// the display's area below the menu bar and beside the Dock, in global top-left coordinates
func visibleArea(_ d: CGDirectDisplayID) -> CGRect {
  let full = CGDisplayBounds(d)
  guard let s = NSScreen.screens.first(where: { ($0.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value == d }),
        let primary = NSScreen.screens.first else { return full }
  let v = s.visibleFrame
  return CGRect(x: v.minX, y: primary.frame.height - v.maxY, width: v.width, height: v.height)
}

// ---------- accessibility ----------
func ax(_ e: AXUIElement, _ a: String) -> CFTypeRef? {
  var v: CFTypeRef?; return AXUIElementCopyAttributeValue(e, a as CFString, &v) == .success ? v : nil
}
func axStr(_ e: AXUIElement, _ a: String) -> String? { (ax(e, a) as? String).flatMap { $0.isEmpty ? nil : $0 } }
func axFrame(_ e: AXUIElement) -> CGRect? {
  guard let p = ax(e, kAXPositionAttribute), let s = ax(e, kAXSizeAttribute) else { return nil }
  var pt = CGPoint.zero, sz = CGSize.zero
  guard CFGetTypeID(p) == AXValueGetTypeID(), CFGetTypeID(s) == AXValueGetTypeID(),
        AXValueGetValue(p as! AXValue, .cgPoint, &pt), AXValueGetValue(s as! AXValue, .cgSize, &sz) else { return nil }
  return CGRect(origin: pt, size: sz)
}
struct Node { let role: String; let subrole: String; let text: [String]; let frame: CGRect?; let url: String }
// Walk the app's windows (and their pop-ups) in reading order, within node and time limits.
func walk(_ pid: pid_t, maxNodes: Int = 8000, seconds: Double = 2.5) -> [Node] {
  let app = AXUIElementCreateApplication(pid); AXUIElementSetMessagingTimeout(app, 0.4)
  // Chromium-based apps build their accessibility tree only when asked; harmless for other apps
  AXUIElementSetAttributeValue(app, "AXManualAccessibility" as CFString, kCFBooleanTrue)
  var out: [Node] = []; let t0 = Date()
  var stack: [(AXUIElement, Int)] = ((ax(app, kAXWindowsAttribute) as? [AXUIElement]) ?? []).reversed().map { ($0, 0) }
  while let (e, depth) = stack.popLast(), out.count < maxNodes, Date().timeIntervalSince(t0) < seconds {
    let role = axStr(e, kAXRoleAttribute) ?? ""
    var text: [String] = []
    for a in [kAXTitleAttribute, kAXValueAttribute, kAXDescriptionAttribute, kAXPlaceholderValueAttribute as String] {
      if let s = axStr(e, a), !text.contains(s) { text.append(s) }
    }
    let url = (ax(e, kAXURLAttribute) as? URL)?.absoluteString ?? ""
    out.append(Node(role: role, subrole: axStr(e, kAXSubroleAttribute) ?? "", text: text, frame: axFrame(e), url: url))
    if depth < 60, let kids = ax(e, kAXChildrenAttribute) as? [AXUIElement] { for k in kids.reversed() { stack.append((k, depth + 1)) } }
  }
  return out
}
// Sign-in screens are never recorded. Same rules as signInReason in capture/cdp.js, read from the app's
// accessibility tree: a sign-in address in an embedded web view, a password or code field, an email-first step,
// or a sign-in window title. It errs toward stopping: a false alarm costs a rerun, a miss records a sign-in.
let SIGNIN_URL = try! NSRegularExpression(pattern: #"^https?://((login|signin|sso|auth|accounts|idp|id|cloudsso)[.-]|[^/?#]*\.(okta|oktapreview|duosecurity|auth0)\.com(?=[/:?#]|$))|/(login|log-in|signin|sign-in|logon|authorize|saml2?|sso|adfs|as/authorization)(?=[/?#.]|$)"#, options: [.caseInsensitive])
let SIGNIN_TITLE = try! NSRegularExpression(pattern: #"\b(sign[ -]?in|log[ -]?in|single sign-on|verify (it's|its|your identity)|two-factor|multi-factor)\b"#, options: [.caseInsensitive])
let SIGNIN_TEXT = try! NSRegularExpression(pattern: #"\b(sign in|log in|single sign-on|verify your identity|enter (your|the) (password|passcode|code|email)|one-time (code|passcode)|two-factor|multi-factor)\b"#, options: [.caseInsensitive])
let EMAIL_FIELD = try! NSRegularExpression(pattern: #"e-?mail|user ?name|user id|sign[ -]?in"#, options: [.caseInsensitive])
func has(_ re: NSRegularExpression, _ s: String) -> Bool { re.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil }
func signInReason(_ pid: pid_t, _ win: CGRect) -> String {
  if ProcessInfo.processInfo.environment["SIGNIN_GUARD"] == "off" { return "" }
  if !AXIsProcessTrusted() { return "cannot check the app for a sign-in screen without the Accessibility permission" }
  let nodes = walk(pid)
  let onScreen = nodes.filter { n in guard let f = n.frame else { return n.role == kAXWindowRole }; return f.width > 1 && f.height > 1 && f.intersects(win) }
  if let n = onScreen.first(where: { !$0.url.isEmpty && has(SIGNIN_URL, $0.url) }) { return "sign-in address " + (n.url.components(separatedBy: "?").first ?? "") }
  if onScreen.contains(where: { $0.role == "AXSecureTextField" || $0.subrole == "AXSecureTextField" }) { return "password field" }
  for n in onScreen where n.role == kAXWindowRole { if let t = n.text.first, has(SIGNIN_TITLE, t) { return "sign-in window title \"\(t)\"" } }
  let fields = onScreen.filter { [kAXTextFieldRole, kAXTextAreaRole, kAXComboBoxRole].contains($0.role) }
  if fields.count == 1, let s = fields[0].text.first(where: { has(EMAIL_FIELD, $0) }) { return "username or email sign-in field \"\(s.prefix(40))\"" }
  if fields.count <= 1, let s = onScreen.filter({ $0.role == kAXStaticTextRole || $0.role == kAXHeadingRole }).flatMap({ $0.text }).first(where: { has(SIGNIN_TEXT, $0) }) {
    return "sign-in text \"\(s.prefix(60))\""
  }
  return ""
}
func frontPid() -> pid_t? {
  guard let a = ax(AXUIElementCreateSystemWide(), kAXFocusedApplicationAttribute) else { return nil }
  var pid: pid_t = 0; return AXUIElementGetPid(a as! AXUIElement, &pid) == .success ? pid : nil
}

// ---------- the controlled app ----------
// behind the window's rounded corners in "app" mode (the configuration holds it unretained, so it lives here)
let BACKGROUND = CGColor(red: 0.95, green: 0.96, blue: 0.976, alpha: 1)
final class Target {
  let app: NSRunningApplication; let pid: pid_t; let mode: String
  var win: CGRect = .zero; var winID: CGWindowID = 0; var scale = 2.0
  init(_ a: NSRunningApplication, mode: String) { app = a; pid = a.processIdentifier; self.mode = mode }
  var name: String { app.localizedName ?? "app" }

  // the main window: the one already chosen (by id) while it is open, else the app's largest normal window
  func refresh() throws {
    if winID != 0, let w = appWindows().first(where: { $0.id == winID }) { win = w.frame; scale = scaleOf(displayFor(w.frame)); return }
    guard let w = mainWindow(pid) else { throw Fail("\(name) has no window on screen: open its main window (not minimized, not full screen) and rerun") }
    win = w.frame; winID = w.id; scale = scaleOf(displayFor(w.frame))
  }
  func activate() {
    let a = AXUIElementCreateApplication(pid)
    AXUIElementSetAttributeValue(a, kAXFrontmostAttribute as CFString, kCFBooleanTrue)
    if let url = app.bundleURL {
      let c = NSWorkspace.OpenConfiguration(); c.activates = true
      NSWorkspace.shared.openApplication(at: url, configuration: c) { _, _ in }
    }
    if let w = (ax(a, kAXMainWindowAttribute) ?? (ax(a, kAXWindowsAttribute) as? [AXUIElement])?.first as CFTypeRef?) {
      AXUIElementPerformAction(w as! AXUIElement, kAXRaiseAction as CFString)
    }
    Thread.sleep(forTimeInterval: 0.6)
  }
  // Bring the app to the front and size its main window to 16:9, centered on the display it is on, or with
  // anchor "bottom-right" in the free area's bottom-right corner (where Webex opens its incoming-call toast,
  // so the toast is inside the recorded area).
  func prep(_ w: Double?, _ h: Double?, _ anchor: String = "center") throws -> [String: Any] {
    guard anchor == "center" || anchor == "bottom-right" else {
      throw Fail("unknown \"anchor\" \"\(anchor)\" in job.json native: use \"center\" or \"bottom-right\"")
    }
    activate(); try refresh()
    let d = displayFor(win), vis = visibleArea(d)
    let sizes: [(Double, Double)] = w != nil && h != nil ? [(w!, h!)] : [(1920, 1080), (1600, 900), (1440, 810), (1280, 720), (1120, 630)]
    guard let size = sizes.first(where: { $0.0 <= Double(vis.width) && $0.1 <= Double(vis.height) }) else {
      throw Fail("the window size \(Int(sizes[0].0))x\(Int(sizes[0].1)) does not fit on this display (\(Int(vis.width))x\(Int(vis.height)) points free)")
    }
    let a = AXUIElementCreateApplication(pid)
    let wins = (ax(a, kAXWindowsAttribute) as? [AXUIElement]) ?? []
    // the accessibility window that matches the main window's position and size
    guard let axw = wins.min(by: { d1, d2 in
      let f1 = axFrame(d1) ?? .zero, f2 = axFrame(d2) ?? .zero
      return abs(f1.minX - win.minX) + abs(f1.minY - win.minY) + abs(f1.width - win.width) < abs(f2.minX - win.minX) + abs(f2.minY - win.minY) + abs(f2.width - win.width)
    }) else { throw Fail("cannot reach \(name)'s window through Accessibility") }
    var pos = CGPoint(x: (vis.minX + (vis.width - size.0) / 2).rounded(), y: (vis.minY + (vis.height - size.1) / 2).rounded())
    if anchor == "bottom-right" { pos = CGPoint(x: (vis.maxX - size.0).rounded(), y: (vis.maxY - size.1).rounded()) }
    var sz = CGSize(width: size.0, height: size.1)
    for _ in 0..<2 {   // some apps apply position and size in either order; twice settles both
      AXUIElementSetAttributeValue(axw, kAXSizeAttribute as CFString, AXValueCreate(.cgSize, &sz)!)
      AXUIElementSetAttributeValue(axw, kAXPositionAttribute as CFString, AXValueCreate(.cgPoint, &pos)!)
      Thread.sleep(forTimeInterval: 0.4)
    }
    try refresh()
    if abs(win.width / win.height - 16.0 / 9.0) > 0.01 {
      throw Fail("\(name)'s window is \(Int(win.width))x\(Int(win.height)) after resizing, not 16:9 (the app may have a minimum size, or be full screen); set \"size\" in job.json native to a size it accepts")
    }
    return info()
  }
  func info() -> [String: Any] {
    ["app": name, "bundle": app.bundleIdentifier ?? "", "pid": Int(pid), "mode": mode,
     "x": Double(win.minX), "y": Double(win.minY), "w": Double(win.width), "h": Double(win.height), "scale": scale,
     "px": [Int(win.width * scale), Int(win.height * scale)]]
  }
  // frame pixels (1920x1080) <-> global screen points
  func toScreen(_ x: Double, _ y: Double) -> CGPoint { CGPoint(x: win.minX + x * win.width / 1920, y: win.minY + y * win.height / 1080) }
  // each axis on its own, as in toScreen: the 16:9 check in prep allows a window 1% off, and the clip is scaled
  // to 1920x1080 on both axes
  func toFrame(_ r: CGRect) -> [Double] {
    let kx = 1920 / win.width, ky = 1080 / win.height
    return [Double((r.minX - win.minX) * kx), Double((r.minY - win.minY) * ky), Double(r.width * kx), Double(r.height * ky)].map { ($0 * 10).rounded() / 10 }
  }
  // what would receive a click at this point: the front-most visible window that contains it
  // The Dock (and some other system processes) keep a window over the whole display that is transparent except for
  // the Dock itself; it counts only outside the display's free area (where the Dock and the menu bar are).
  // Smaller system windows, such as a notification banner, still count.
  static let SYSTEM = Set(["Dock", "Window Server", "WindowManager", "Control Center", "SystemUIServer"])
  func coveredBy(_ p: CGPoint) -> String? {
    for w in windowList() {
      let alpha = (w[kCGWindowAlpha as String] as? Double) ?? 1
      let b = bounds(w)
      if alpha < 0.05 || !b.contains(p) { continue }
      if Target.SYSTEM.contains((w[kCGWindowOwnerName as String] as? String) ?? ""), (w[kCGWindowOwnerPID as String] as? Int32) != pid {
        let d = displayFor(b)
        if b.equalTo(CGDisplayBounds(d)) && visibleArea(d).contains(p) { continue }
      }
      if (w[kCGWindowOwnerPID as String] as? Int32) == pid { return nil }
      return (w[kCGWindowOwnerName as String] as? String) ?? "another app"
    }
    return "nothing (the point is outside every window)"
  }
  // every visible window of the app, front to back: the main window, and pop-ups such as an incoming-call toast
  func appWindows() -> [(id: CGWindowID, frame: CGRect, title: String, layer: Int)] {
    windowList().filter { ($0[kCGWindowOwnerPID as String] as? Int32) == pid && (($0[kCGWindowAlpha as String] as? Double) ?? 1) > 0.05 }
      .map { (id: CGWindowID(($0[kCGWindowNumber as String] as? Int) ?? 0), frame: bounds($0), title: ($0[kCGWindowName as String] as? String) ?? "",
              layer: ($0[kCGWindowLayer as String] as? Int) ?? 0) }
      .filter { $0.frame.width >= 40 && $0.frame.height >= 20 }
  }
  // the accessibility window for a window on screen, matched by position and size
  func axWindow(_ frame: CGRect) -> AXUIElement? {
    let a = AXUIElementCreateApplication(pid)
    let ws = ((ax(a, kAXWindowsAttribute) as? [AXUIElement]) ?? []).compactMap { w in axFrame(w).map { (w, $0) } }
    let d = { (f: CGRect) in abs(f.minX - frame.minX) + abs(f.minY - frame.minY) + abs(f.width - frame.width) + abs(f.height - frame.height) }
    return ws.min { d($0.1) < d($1.1) }.flatMap { d($0.1) < 8 ? $0.0 : nil }
  }
  // Move (and optionally size) one of the app's windows, in frame pixels; by default onto the capture area, so a
  // call window that opens elsewhere fills the recorded frame. The capture area itself does not move.
  func place(_ id: CGWindowID, _ box: [Double]?) throws -> [String: Any] {
    guard let w = appWindows().first(where: { $0.id == id }) else { throw Fail("no \(name) window with id \(id) on screen") }
    guard let axw = axWindow(w.frame) else { throw Fail("cannot reach that \(name) window through Accessibility, so it cannot be moved") }
    let kx = win.width / 1920, ky = win.height / 1080, b = box ?? [0, 0, 1920, 1080]
    var pos = CGPoint(x: win.minX + b[0] * kx, y: win.minY + b[1] * ky)
    if b.count == 4 { var sz = CGSize(width: b[2] * kx, height: b[3] * ky); AXUIElementSetAttributeValue(axw, kAXSizeAttribute as CFString, AXValueCreate(.cgSize, &sz)!) }
    AXUIElementSetAttributeValue(axw, kAXPositionAttribute as CFString, AXValueCreate(.cgPoint, &pos)!)
    if b.count == 4 { var sz = CGSize(width: b[2] * kx, height: b[3] * ky); AXUIElementSetAttributeValue(axw, kAXSizeAttribute as CFString, AXValueCreate(.cgSize, &sz)!) }
    AXUIElementPerformAction(axw, kAXRaiseAction as CFString)
    Thread.sleep(forTimeInterval: 0.3)
    guard let n = appWindows().first(where: { $0.id == id }) else { throw Fail("the window closed while it was being moved") }
    let f = toFrame(n.frame); return ["x": f[0], "y": f[1], "w": f[2], "h": f[3]]
  }
  func checkWindow() throws {
    // the main window by its id, so a bigger call or meeting window opening on top does not count as a move
    guard let w = appWindows().first(where: { $0.id == winID }) else { throw Fail("\(name)'s main window closed or was minimized") }
    if abs(w.frame.minX - win.minX) > 1 || abs(w.frame.minY - win.minY) > 1 || abs(w.frame.width - win.width) > 1 {
      throw Fail("\(name)'s window moved or changed size; run prep again (leave the window alone during a take)")
    }
  }
  func shareable() throws -> (SCContentFilter, SCStreamConfiguration) {
    try refresh()
    let content = try blocking { try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true) }
    let did = displayFor(win)
    guard let disp = content.displays.first(where: { $0.displayID == did }) else { throw Fail("display not found for \(name)'s window") }
    let cfg = SCStreamConfiguration()
    cfg.width = Int(win.width * scale); cfg.height = Int(win.height * scale)
    // scalesToFit: without it, a capture smaller than the output size (a 1600x900 window into a 1920x1080 shot)
    // sits unscaled in the top-left corner
    cfg.scalesToFit = true; cfg.showsCursor = false; cfg.pixelFormat = kCVPixelFormatType_32BGRA; cfg.colorSpaceName = CGColorSpace.sRGB
    cfg.backgroundColor = BACKGROUND
    let filter: SCContentFilter
    if mode == "window" {
      guard let w = content.windows.first(where: { $0.windowID == winID }) else { throw Fail("\(name)'s window is not shareable") }
      filter = SCContentFilter(desktopIndependentWindow: w)
    } else {
      guard let a = content.applications.first(where: { $0.processID == pid }) else { throw Fail("\(name) is not shareable") }
      filter = SCContentFilter(display: disp, including: [a], exceptingWindows: [])
      let db = CGDisplayBounds(did)
      cfg.sourceRect = CGRect(x: win.minX - db.minX, y: win.minY - db.minY, width: win.width, height: win.height)
    }
    return (filter, cfg)
  }
}

// ---------- recording ----------
final class Recorder: NSObject, SCStreamOutput, SCStreamDelegate {
  let dir: URL; let quality: Double
  var stream: SCStream?; var n = 0; var dropped = 0; var frames: [[String: Any]] = []; var error: String?
  let q = DispatchQueue(label: "frames"); let wq = DispatchQueue(label: "write", attributes: .concurrent)
  let group = DispatchGroup(); let slots = DispatchSemaphore(value: 10); let lock = NSLock()
  var tb = mach_timebase_info_data_t()
  init(dir: URL, quality: Double) { self.dir = dir; self.quality = quality; super.init(); mach_timebase_info(&tb) }
  func start(_ t: Target) throws {
    let (filter, cfg) = try t.shareable()
    cfg.minimumFrameInterval = CMTime(value: 1, timescale: 30); cfg.queueDepth = 8
    let s = SCStream(filter: filter, configuration: cfg, delegate: self)
    try s.addStreamOutput(self, type: .screen, sampleHandlerQueue: q)
    try blocking { try await s.startCapture() }
    stream = s
  }
  func stop() throws -> [String: Any] {
    if let s = stream { try? blocking { try await s.stopCapture() } }
    stream = nil; q.sync {}; group.wait()
    lock.lock(); defer { lock.unlock() }
    let fs = frames.sorted { ($0["f"] as! String) < ($1["f"] as! String) }
    return ["frames": fs, "dropped": dropped, "error": error ?? ""]
  }
  // mach host time (the frame's display time) -> seconds since 1970, the clock rec.js and the logs use
  func wall(_ mach: UInt64) -> Double {
    let now = mach_absolute_time(), w = Date().timeIntervalSince1970
    let ago = Double(Int64(bitPattern: now &- mach)) * Double(tb.numer) / Double(tb.denom) / 1e9
    return w - ago
  }
  func stream(_ stream: SCStream, didStopWithError e: Error) { error = e.localizedDescription }
  func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
    guard type == .screen, sb.isValid,
          let att = CMSampleBufferGetSampleAttachmentsArray(sb, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
          let a = att.first, let raw = a[.status] as? Int, SCFrameStatus(rawValue: raw) == .complete,
          let pb = sb.imageBuffer else { return }
    let t = (a[.displayTime] as? UInt64).map(wall) ?? Date().timeIntervalSince1970
    // only the newest frames matter: when the writers fall behind, drop this one rather than queue memory
    if slots.wait(timeout: .now()) == .timedOut { dropped += 1; return }
    CVPixelBufferLockBaseAddress(pb, .readOnly)
    let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), bpr = CVPixelBufferGetBytesPerRow(pb)
    let data = Data(bytes: CVPixelBufferGetBaseAddress(pb)!, count: bpr * h)
    CVPixelBufferUnlockBaseAddress(pb, .readOnly)
    let name = String(format: "%05d.jpg", n); n += 1
    let url = dir.appendingPathComponent(name), qual = quality
    group.enter()
    wq.async { [self] in
      defer { slots.signal(); group.leave() }
      guard let prov = CGDataProvider(data: data as CFData),
            let img = CGImage(width: w, height: h, bitsPerComponent: 8, bitsPerPixel: 32, bytesPerRow: bpr, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                              bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.noneSkipFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue),
                              provider: prov, decode: nil, shouldInterpolate: false, intent: .defaultIntent),
            let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { return }
      CGImageDestinationAddImage(dest, img, [kCGImageDestinationLossyCompressionQuality: qual] as CFDictionary)
      if CGImageDestinationFinalize(dest) { lock.lock(); frames.append(["f": name, "t": t]); lock.unlock() }
    }
  }
}

func savePNG(_ img: CGImage, _ path: String) throws {
  let url = URL(fileURLWithPath: path)
  try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
  guard let d = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else { throw Fail("cannot write \(path)") }
  CGImageDestinationAddImage(d, img, nil); if !CGImageDestinationFinalize(d) { throw Fail("cannot write \(path)") }
}

// ---------- input ----------
let KEYS: [String: CGKeyCode] = [
  "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
  "forwarddelete": 117, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
  "left": 123, "right": 124, "down": 125, "up": 126,
  "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14,
  "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27,
  "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41,
  "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50]
let MODS: [String: CGEventFlags] = ["cmd": .maskCommand, "command": .maskCommand, "shift": .maskShift, "alt": .maskAlternate,
                                    "option": .maskAlternate, "ctrl": .maskControl, "control": .maskControl]
final class Input {
  let t: Target; let src = CGEventSource(stateID: .hidSystemState)
  var pos = CGPoint.zero; var down = false
  init(_ t: Target) { self.t = t }
  func front() throws { if frontPid() != t.pid { throw Fail("\(t.name) is not the front app (something else took focus); input refused") } }
  func move(_ x: Double, _ y: Double) {
    pos = t.toScreen(x, y)
    CGEvent(mouseEventSource: src, mouseType: down ? .leftMouseDragged : .mouseMoved, mouseCursorPosition: pos, mouseButton: .left)?.post(tap: .cghidEventTap)
  }
  func button(_ isDown: Bool, right: Bool, count: Int) throws {
    if isDown {
      if let other = t.coveredBy(pos) { throw Fail("click refused: \(other) is in front of \(t.name) at that point") }
      try t.checkWindow()
    }
    let type: CGEventType = right ? (isDown ? .rightMouseDown : .rightMouseUp) : (isDown ? .leftMouseDown : .leftMouseUp)
    let e = CGEvent(mouseEventSource: src, mouseType: type, mouseCursorPosition: pos, mouseButton: right ? .right : .left)
    e?.setIntegerValueField(.mouseEventClickState, value: Int64(count)); e?.post(tap: .cghidEventTap)
    if !right { down = isDown }
  }
  func type(_ s: String) throws {
    if s.contains("\n") || s.contains("\r") { throw Fail("type() takes no line breaks: press keys with key('return') (or key('return', ['shift']) for a new line)") }
    try front()
    for ch in s {
      let u = Array(String(ch).utf16)
      for d in [true, false] {
        let e = CGEvent(keyboardEventSource: src, virtualKey: 0, keyDown: d)
        e?.flags = []; e?.keyboardSetUnicodeString(stringLength: u.count, unicodeString: u); e?.post(tap: .cghidEventTap)
      }
    }
  }
  func key(_ name: String, _ mods: [String]) throws {
    guard let code = KEYS[name.lowercased()] else { throw Fail("unknown key \"\(name)\"; known: \(KEYS.keys.sorted().joined(separator: " "))") }
    var flags: CGEventFlags = []
    for m in mods { guard let f = MODS[m.lowercased()] else { throw Fail("unknown modifier \"\(m)\" (cmd, shift, alt, ctrl)") }; flags.insert(f) }
    try front()
    for d in [true, false] { let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: d); e?.flags = flags; e?.post(tap: .cghidEventTap) }
  }
  // dy > 0 scrolls down (the content moves up), as page.mouse.wheel does in Chrome takes; in frame pixels
  // the scroll goes to whatever is under the pointer, so it is refused where another window covers it, as a click is
  func scroll(_ dy: Double, _ dx: Double) throws {
    try front()
    if let other = t.coveredBy(pos) { throw Fail("scroll refused: \(other) is in front of \(t.name) at the pointer") }
    let k = t.win.width / 1920
    CGEvent(scrollWheelEvent2Source: src, units: .pixel, wheelCount: 2, wheel1: Int32((-dy * k).rounded()), wheel2: Int32((-dx * k).rounded()), wheel3: 0)?.post(tap: .cghidEventTap)
  }
}

// ---------- server ----------
func serve(_ target: Target) {
  let input = Input(target); var rec: Recorder?
  let cmdq = DispatchQueue(label: "cmd"), axq = DispatchQueue(label: "ax")
  func num(_ m: [String: Any], _ k: String) -> Double? { (m[k] as? NSNumber)?.doubleValue }
  func handle(_ m: [String: Any]) throws -> [String: Any] {
    let op = m["op"] as? String ?? ""
    switch op {
    case "check": return permissions(prompt: false)
    case "prep": return try target.prep(num(m, "w"), num(m, "h"), (m["anchor"] as? String) ?? "center")
    case "window": return target.info()
    case "windows":
      return ["windows": target.appWindows().map { w -> [String: Any] in let f = target.toFrame(w.frame)
        return ["id": Int(w.id), "title": w.title, "layer": w.layer, "main": w.id == target.winID, "x": f[0], "y": f[1], "w": f[2], "h": f[3]] }]
    case "place":
      guard let id = num(m, "window") else { throw Fail("place needs a window (its id from windows)") }
      return try target.place(CGWindowID(id), (m["box"] as? [NSNumber])?.map { $0.doubleValue })
    case "activate": target.activate(); return [:]
    case "guard":
      var moved = ""; do { try target.checkWindow() } catch let f as Fail { moved = f.msg }
      return ["reason": signInReason(target.pid, target.win), "moved": moved, "front": frontPid() == target.pid]
    case "text":
      let lim = Int(num(m, "max") ?? 20000), anywhere = m["anywhere"] as? Bool ?? false
      var lines: [String] = []
      for n in walk(target.pid) { guard let f = n.frame, anywhere || f.intersects(target.win), f.width > 1, f.height > 1 else { continue }
        for s in n.text where lines.last != s { lines.append(s) } }
      let s = lines.joined(separator: "\n"); return ["text": String(s.suffix(lim))]
    case "find":
      guard let pat = m["pattern"] as? String, let re = try? NSRegularExpression(pattern: pat, options: [.caseInsensitive]) else { throw Fail("find needs a valid pattern") }
      let role = m["role"] as? String, anywhere = m["anywhere"] as? Bool ?? false
      let hits = walk(target.pid).filter { n in
        guard let f = n.frame, f.width > 1, f.height > 1, anywhere || f.intersects(target.win) else { return false }
        if let r = role, n.role != r { return false }
        return n.text.contains { has(re, $0) }
      }.prefix(50).map { n -> [String: Any] in let b = target.toFrame(n.frame!)
        return ["role": n.role, "text": n.text.joined(separator: " | ").prefix(200).description, "x": b[0], "y": b[1], "w": b[2], "h": b[3]] }
      return ["hits": Array(hits)]
    case "shot":
      guard let path = m["path"] as? String else { throw Fail("shot needs a path") }
      let why = signInReason(target.pid, target.win)
      if !why.isEmpty { return ["refused": why] }
      let (filter, cfg) = try target.shareable(); cfg.width = 1920; cfg.height = 1080
      let img = try blocking { try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: cfg) }
      try savePNG(img, path); return ["path": path]
    case "start":
      guard rec == nil else { throw Fail("already recording") }
      guard let dir = m["dir"] as? String else { throw Fail("start needs a dir") }
      try target.checkWindow()
      let r = Recorder(dir: URL(fileURLWithPath: dir), quality: (num(m, "quality") ?? 90) / 100)
      try r.start(target); rec = r; return target.info()
    case "stop":
      guard let r = rec else { throw Fail("not recording") }
      rec = nil; return try r.stop()
    case "move": input.move(num(m, "x") ?? 0, num(m, "y") ?? 0); return [:]
    case "down": try input.button(true, right: m["button"] as? String == "right", count: Int(num(m, "count") ?? 1)); return [:]
    case "up": try input.button(false, right: m["button"] as? String == "right", count: Int(num(m, "count") ?? 1)); return [:]
    case "type": try input.type(m["text"] as? String ?? ""); return [:]
    case "key": try input.key(m["key"] as? String ?? "", m["mods"] as? [String] ?? []); return [:]
    case "scroll": try input.scroll(num(m, "dy") ?? 0, num(m, "dx") ?? 0); return [:]
    case "quit": if let r = rec { _ = try? r.stop() }; emit(["id": m["id"] ?? 0, "ok": true]); exit(0)
    default: throw Fail("unknown op \"\(op)\"")
    }
  }
  Thread {
    while let line = readLine() {
      guard let d = line.data(using: .utf8), let m = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any] else { continue }
      let id = m["id"] ?? 0
      // the accessibility walks run on their own queue so pointer moves keep flowing during a take
      let q = ["guard", "text", "find"].contains(m["op"] as? String ?? "") ? axq : cmdq
      q.async {
        do { var r = try handle(m); r["id"] = id; r["ok"] = true; emit(r) }
        catch let f as Fail { emit(["id": id, "ok": false, "error": f.msg]) }
        catch { emit(["id": id, "ok": false, "error": error.localizedDescription]) }
      }
    }
    cmdq.async { if let r = rec { _ = try? r.stop() }; exit(0) }   // stdin closed: finish writing frames, then quit
  }.start()
  RunLoop.main.run()
}

// ---------- main ----------
_ = NSApplication.shared; NSApp.setActivationPolicy(.prohibited)
setvbuf(stdout, nil, _IOLBF, 0)
let args = CommandLine.arguments
func arg(_ k: String) -> String? { args.firstIndex(of: k).flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil } }
switch args.count > 1 ? args[1] : "" {
case "check": emit(permissions(prompt: args.contains("--prompt")))
case "list":
  var seen: [Int32: [String: Any]] = [:]
  for w in windowList() where (w[kCGWindowLayer as String] as? Int) == 0 {
    guard let pid = w[kCGWindowOwnerPID as String] as? Int32, seen[pid] == nil, let a = NSRunningApplication(processIdentifier: pid), a.activationPolicy == .regular else { continue }
    let f = bounds(w); seen[pid] = ["app": a.localizedName ?? "", "bundle": a.bundleIdentifier ?? "", "w": Double(f.width), "h": Double(f.height)]
  }
  emit(["apps": Array(seen.values)])
case "serve":
  guard let q = arg("--app"), let a = findApp(q) else { emit(["ok": false, "error": "app \"\(arg("--app") ?? "")\" is not running: open it, sign in off camera, and rerun"]); exit(1) }
  serve(Target(a, mode: arg("--mode") == "window" ? "window" : "app"))
default:
  FileHandle.standardError.write("usage: nativecap check [--prompt] | list | serve --app <name|bundle id> [--mode app|window]\n".data(using: .utf8)!); exit(64)
}
