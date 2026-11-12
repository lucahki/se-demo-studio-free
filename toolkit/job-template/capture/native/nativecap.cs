// nativecap (Windows): record and drive one desktop app (for example the Webex app) for the demo studio.
// The Windows twin of nativecap.swift: the same commands, ops, and replies, so capture/native.js and everything above
// it work unchanged. Built on first use by capture/native.js with the C# compiler that ships with Windows
// (.NET Framework 4, C# 5 syntax only), after tlbconv.cs has turned the UI Automation type library into an interop
// assembly (embedded here with /link, so nativecap.exe is one file).
//
//   nativecap check [--prompt]       {"screen": true, "accessibility": true}: Windows has no such permissions
//   nativecap list                   running apps that have windows on screen, as JSON
//   nativecap serve --app <name> [--mode app|window] [--title <regex>]
//                                    JSON lines on stdin and stdout: {"id":1,"op":"prep",...} -> {"id":1,"ok":true,...}
//
// The app is every process with the same program file as the one whose window matched --app (the Webex app runs
// three CiscoCollabHost.exe processes). --app matches the program name (CiscoCollabHost), its file description
// (Webex), or a window title. --title picks the main window when the app has several large ones.
// Coordinates in every op are frame pixels: the app's main window mapped to 1920x1080, the same space as Chrome
// takes. Screen positions are physical pixels: the process is per-monitor DPI aware.
// Recording: "app" mode (default) copies the screen rectangle under the main window (DWM composed, no cursor), so
// the app's menus, toasts, and call windows show. Unlike macOS, another app's window over that rectangle would show
// too, so "guard" reports it as "covered" and the recorders stop and delete the take. "window" mode renders only
// the main window (PrintWindow), slower. A frame identical to the one before is skipped, as ScreenCaptureKit does.
// Input goes through SendInput: a click or scroll is refused when another app's window is at the point, and typing
// is refused when the app is not in front. cmd/command in key() means Ctrl, so macOS take scripts run as they are.
// UI Automation (the native COM client) reads labels and text; elements outside the recorded area are skipped,
// which keeps a walk of the Webex app under about two seconds.
using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using UIAutomationClient;

class Fail : Exception { public Fail(string m) : base(m) { } }

// ---------- Win32 ----------
static class W {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [StructLayout(LayoutKind.Sequential)] public struct MONITORINFO { public int cbSize; public RECT rcMonitor, rcWork; public uint dwFlags; }
  [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int dx, dy, mouseData; public uint dwFlags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Explicit)] public struct INPUTU { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public INPUTU u; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);

  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h, uint cmd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
  [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr h, uint flags);
  [DllImport("user32.dll")] public static extern bool GetMonitorInfo(IntPtr m, ref MONITORINFO mi);
  [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
  [DllImport("shcore.dll")] public static extern int GetDpiForMonitor(IntPtr m, int type, out uint x, out uint y);
  [DllImport("user32.dll")] public static extern uint SendInput(uint n, INPUT[] inputs, int size);
  [DllImport("user32.dll")] public static extern int GetSystemMetrics(int i);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetLayeredWindowAttributes(IntPtr h, out uint key, out byte alpha, out uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern bool QueryFullProcessImageName(IntPtr h, uint flags, StringBuilder s, ref int n);
  [DllImport("kernel32.dll")] public static extern void GetSystemTimePreciseAsFileTime(out long ft);
  [DllImport("advapi32.dll")] public static extern bool OpenProcessToken(IntPtr p, uint access, out IntPtr tok);
  [DllImport("advapi32.dll")] public static extern bool GetTokenInformation(IntPtr tok, int cls, out int val, int len, out int ret);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int n);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out int v, int n);
  [DllImport("msvcrt.dll", CallingConvention = CallingConvention.Cdecl)] public static extern int memcmp(byte[] a, byte[] b, UIntPtr n);

  public const int GWL_STYLE = -16, GWL_EXSTYLE = -20;
  public const int WS_CAPTION = 0x00C00000, WS_EX_TOOLWINDOW = 0x80, WS_EX_TOPMOST = 0x8, WS_EX_LAYERED = 0x80000;
  public const uint GW_OWNER = 4, GA_ROOT = 2, MONITOR_DEFAULTTONEAREST = 2;
  public const uint SWP_NOSIZE = 0x1, SWP_NOMOVE = 0x2, SWP_NOZORDER = 0x4, SWP_NOACTIVATE = 0x10;
  public const int SW_RESTORE = 9;

  // the visible frame (no invisible resize border), in physical pixels
  public static RECT Frame(IntPtr h) {
    RECT r; if (DwmGetWindowAttribute(h, 9, out r, Marshal.SizeOf(typeof(RECT))) != 0) GetWindowRect(h, out r); return r;
  }
  public static bool Cloaked(IntPtr h) { int v; return DwmGetWindowAttribute(h, 14, out v, 4) == 0 && v != 0; }
  public static double Alpha(IntPtr h) {
    if ((GetWindowLong(h, GWL_EXSTYLE) & WS_EX_LAYERED) == 0) return 1;
    uint key, flags; byte a; if (!GetLayeredWindowAttributes(h, out key, out a, out flags) || (flags & 2) == 0) return 1;
    return a / 255.0;
  }
  public static string Title(IntPtr h) { var s = new StringBuilder(512); GetWindowText(h, s, 512); return s.ToString(); }
  public static uint Pid(IntPtr h) { uint p; GetWindowThreadProcessId(h, out p); return p; }
  public static List<IntPtr> TopLevel() {   // front to back
    var l = new List<IntPtr>(); EnumWindows(delegate(IntPtr h, IntPtr x) { l.Add(h); return true; }, IntPtr.Zero); return l;
  }
  public static string ImagePath(uint pid) {
    IntPtr p = OpenProcess(0x1000, false, pid); if (p == IntPtr.Zero) return "";
    try { var s = new StringBuilder(1024); int n = s.Capacity; return QueryFullProcessImageName(p, 0, s, ref n) ? s.ToString() : ""; }
    finally { CloseHandle(p); }
  }
  public static string ExeName(uint pid) { string p = ImagePath(pid); return p == "" ? "" : Path.GetFileNameWithoutExtension(p); }
  public static string Description(string path) {
    try { var v = FileVersionInfo.GetVersionInfo(path); return (v.FileDescription ?? "").Trim(); } catch { return ""; }
  }
  // true or false when the token can be read; null when it cannot (another user's or a protected process)
  public static bool? Elevated(IntPtr process) {
    IntPtr tok; if (!OpenProcessToken(process, 8, out tok)) return null;
    try { int v, n; return GetTokenInformation(tok, 20, out v, 4, out n) ? (bool?)(v != 0) : null; } finally { CloseHandle(tok); }
  }
  public static bool? Elevated(uint pid) {
    IntPtr p = OpenProcess(0x1000, false, pid); if (p == IntPtr.Zero) return null;
    try { return Elevated(p); } finally { CloseHandle(p); }
  }
  public static double Now() { long ft; GetSystemTimePreciseAsFileTime(out ft); return (ft - 116444736000000000L) / 1e7; }
  public static bool Intersects(RECT a, RECT b) { return a.R > b.L && a.L < b.R && a.B > b.T && a.T < b.B && a.R > a.L && a.B > a.T; }
  public static RECT Intersect(RECT a, RECT b) {
    var r = new RECT { L = Math.Max(a.L, b.L), T = Math.Max(a.T, b.T), R = Math.Min(a.R, b.R), B = Math.Min(a.B, b.B) };
    if (r.R < r.L) r.R = r.L; if (r.B < r.T) r.B = r.T; return r;
  }
}

// ---------- output ----------
static class Out {
  static readonly object lk = new object();
  public static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue, RecursionLimit = 64 };
  static StreamWriter w;
  public static void Init() { w = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)); w.AutoFlush = true; }
  public static void Emit(Dictionary<string, object> o) { string s = Json.Serialize(o); lock (lk) { w.Write(s + "\n"); } }
}

// ---------- UI Automation ----------
class Node {
  public string Role = "", Uia = "", Sub = "", Url = ""; public List<string> Text = new List<string>();
  public bool HasFrame; public W.RECT Frame; public bool Password;
}
static class Ax {
  static IUIAutomation u; static IUIAutomationCacheRequest one, sub; static IUIAutomationCondition cv;
  static readonly object lk = new object();
  const int CT = 30003, NAME = 30005, RECTP = 30001, PASSWORD = 30019, FW = 30024, OFFSCREEN = 30022, VALUE = 30045, HELP = 30013;
  // UIA control types as their macOS Accessibility role names, so take scripts and recipes written for the Mac
  // version (find(/answer/, 'AXButton')) run as they are; the UIA name is in "uia"
  static readonly Dictionary<int, string[]> ROLES = new Dictionary<int, string[]> {
    {50000, new[] {"AXButton", "Button"}}, {50001, new[] {"AXGroup", "Calendar"}}, {50002, new[] {"AXCheckBox", "CheckBox"}},
    {50003, new[] {"AXComboBox", "ComboBox"}}, {50004, new[] {"AXTextField", "Edit"}}, {50005, new[] {"AXLink", "Hyperlink"}},
    {50006, new[] {"AXImage", "Image"}}, {50007, new[] {"AXRow", "ListItem"}}, {50008, new[] {"AXList", "List"}},
    {50009, new[] {"AXMenu", "Menu"}}, {50010, new[] {"AXMenuBar", "MenuBar"}}, {50011, new[] {"AXMenuItem", "MenuItem"}},
    {50012, new[] {"AXProgressIndicator", "ProgressBar"}}, {50013, new[] {"AXRadioButton", "RadioButton"}},
    {50014, new[] {"AXScrollBar", "ScrollBar"}}, {50015, new[] {"AXSlider", "Slider"}}, {50016, new[] {"AXIncrementor", "Spinner"}},
    {50017, new[] {"AXGroup", "StatusBar"}}, {50018, new[] {"AXTabGroup", "Tab"}}, {50019, new[] {"AXRadioButton", "TabItem", "AXTabButton"}},
    {50020, new[] {"AXStaticText", "Text"}}, {50021, new[] {"AXToolbar", "ToolBar"}}, {50022, new[] {"AXHelpTag", "ToolTip"}},
    {50023, new[] {"AXOutline", "Tree"}}, {50024, new[] {"AXRow", "TreeItem"}}, {50025, new[] {"AXUnknown", "Custom"}},
    {50026, new[] {"AXGroup", "Group"}}, {50027, new[] {"AXValueIndicator", "Thumb"}}, {50028, new[] {"AXTable", "DataGrid"}},
    {50029, new[] {"AXRow", "DataItem"}}, {50030, new[] {"AXWebArea", "Document"}}, {50031, new[] {"AXMenuButton", "SplitButton"}},
    {50032, new[] {"AXWindow", "Window"}}, {50033, new[] {"AXGroup", "Pane"}}, {50034, new[] {"AXGroup", "Header"}},
    {50035, new[] {"AXCell", "HeaderItem"}}, {50036, new[] {"AXTable", "Table"}}, {50037, new[] {"AXGroup", "TitleBar"}},
    {50038, new[] {"AXSplitter", "Separator"}}, {50039, new[] {"AXGroup", "SemanticZoom"}}, {50040, new[] {"AXToolbar", "AppBar"}}};

  static IUIAutomationCacheRequest Req(TreeScope scope) {
    var r = u.CreateCacheRequest();
    foreach (int p in new[] { CT, NAME, RECTP, PASSWORD, FW, OFFSCREEN, VALUE, HELP }) r.AddProperty(p);
    r.TreeScope = scope; r.TreeFilter = cv; return r;
  }
  static void Init() {
    if (u != null) return;
    u = new CUIAutomation8(); cv = u.ControlViewCondition;
    one = Req(TreeScope.TreeScope_Element); sub = Req(TreeScope.TreeScope_Subtree);
    try { var u2 = (IUIAutomation2)u; u2.ConnectionTimeout = 2000; u2.TransactionTimeout = 1500; } catch { }
  }
  static T Get<T>(Func<T> f, T dflt) { try { return f(); } catch { return dflt; } }

  class Walk {
    public List<Node> Out = new List<Node>(); public int Max; public Stopwatch Sw = Stopwatch.StartNew(); public double Secs;
    public bool Done { get { return Out.Count >= Max || Sw.Elapsed.TotalSeconds >= Secs; } }
  }
  static bool Keep(IUIAutomationElement e, int depth, W.RECT clip) {
    if (depth == 0) return true;
    if (Get(() => e.CachedIsOffscreen, 0) != 0) return false;
    var r = Get(() => e.CachedBoundingRectangle, new tagRECT());
    return W.Intersects(new W.RECT { L = r.left, T = r.top, R = r.right, B = r.bottom }, clip);
  }
  static Node Mk(IUIAutomationElement e) {
    var n = new Node(); int ct = Get(() => e.CachedControlType, 0);
    string[] role; if (ROLES.TryGetValue(ct, out role)) { n.Role = role[0]; n.Uia = role[1]; if (role.Length > 2) n.Sub = role[2]; }
    if (Get(() => e.CachedIsPassword, 0) != 0) { n.Password = true; n.Sub = "AXSecureTextField"; }
    string name = Get(() => e.CachedName, null), help = Get(() => e.CachedHelpText, null);
    string val = Get(() => e.GetCachedPropertyValue(VALUE) as string, null);
    if (ct == 50030 && val != null && Regex.IsMatch(val, "^https?://", RegexOptions.IgnoreCase)) { n.Url = val; val = null; }
    // trimmed: Qt labels can start with a space (" Meetings menu item , 2 of 12"), which would defeat /^Meetings/
    foreach (var raw in new[] { name, val, help }) { var s = raw == null ? "" : raw.Trim(); if (s != "" && !n.Text.Contains(s)) n.Text.Add(s); }
    var r = Get(() => e.CachedBoundingRectangle, new tagRECT());
    n.Frame = new W.RECT { L = r.left, T = r.top, R = r.right, B = r.bottom }; n.HasFrame = r.right > r.left && r.bottom > r.top;
    return n;
  }
  // one element, then its children; a Chrome web view (Webex's messages) in one call for its whole subtree
  static void Visit(Walk w, IUIAutomationElement e, int depth, W.RECT clip) {
    if (w.Done || !Keep(e, depth, clip)) return;
    w.Out.Add(Mk(e));
    if (depth >= 60) return;
    if (Get(() => e.CachedFrameworkId, "") == "Chrome") {
      IUIAutomationElement c = null; try { c = e.BuildUpdatedCache(sub); } catch { }
      if (c != null) { VisitCached(w, c, depth, clip); return; }
    }
    IUIAutomationElementArray kids = null; try { kids = e.FindAllBuildCache(TreeScope.TreeScope_Children, cv, one); } catch { }
    if (kids == null) return;
    for (int i = 0; i < kids.Length && !w.Done; i++) Visit(w, kids.GetElement(i), depth + 1, clip);
  }
  static void VisitCached(Walk w, IUIAutomationElement e, int depth, W.RECT clip) {   // e itself is already in the list
    if (depth >= 60) return;
    IUIAutomationElementArray kids = Get(() => e.GetCachedChildren(), null); if (kids == null) return;
    for (int i = 0; i < kids.Length && !w.Done; i++) {
      var k = kids.GetElement(i); if (!Keep(k, depth + 1, clip)) continue;
      w.Out.Add(Mk(k)); VisitCached(w, k, depth + 1, clip);
    }
  }
  // The app's windows (and their pop-ups), front to back, within node and time limits. Only elements inside `area`
  // (each window's own frame when area is null: anywhere) are read: offscreen list items are most of the tree.
  public static List<Node> WalkApp(Target t, W.RECT? area, int maxNodes = 8000, double seconds = 4) {
    lock (lk) {
      Init(); var w = new Walk { Max = maxNodes, Secs = seconds };
      foreach (var win in t.AppWindows()) {
        if (w.Done) break;
        W.RECT clip = win.F; if (area.HasValue) { if (!W.Intersects(win.F, area.Value)) continue; clip = W.Intersect(win.F, area.Value); }
        IUIAutomationElement root = null; try { root = u.ElementFromHandleBuildCache(win.H, one); } catch { }
        if (root != null) Visit(w, root, 0, clip);
      }
      return w.Out;
    }
  }
}

// ---------- sign-in guard ----------
// Sign-in screens are never recorded. Same rules as signInReason in capture/cdp.js and nativecap.swift, read from
// the app's UI Automation tree: a sign-in address in an embedded web view, a password field, an email-first step, or
// a sign-in window title. It errs toward stopping: a false alarm costs a rerun, a miss records a sign-in.
static class SignIn {
  static readonly RegexOptions I = RegexOptions.IgnoreCase;
  static readonly Regex URL = new Regex(@"^https?://((login|signin|sso|auth|accounts|idp|id|cloudsso)[.-]|[^/?#]*\.(okta|oktapreview|duosecurity|auth0)\.com(?=[/:?#]|$))|/(login|log-in|signin|sign-in|logon|authorize|saml2?|sso|adfs|as/authorization)(?=[/?#.]|$)", I);
  static readonly Regex TITLE = new Regex(@"\b(sign[ -]?in|log[ -]?in|single sign-on|verify (it's|its|your identity)|two-factor|multi-factor)\b", I);
  static readonly Regex TEXT = new Regex(@"\b(sign in|log in|single sign-on|verify your identity|enter (your|the) (password|passcode|code|email)|one-time (code|passcode)|two-factor|multi-factor)\b", I);
  static readonly Regex EMAIL = new Regex(@"e-?mail|user ?name|user id|sign[ -]?in", I);
  static string Cut(string s, int n) { return s.Length > n ? s.Substring(0, n) : s; }
  public static string Reason(Target t) {
    if (Environment.GetEnvironmentVariable("SIGNIN_GUARD") == "off") return "";
    var on = Ax.WalkApp(t, t.Win).Where(n => n.HasFrame ? n.Frame.R - n.Frame.L > 1 && n.Frame.B - n.Frame.T > 1 : n.Role == "AXWindow").ToList();
    var u = on.FirstOrDefault(n => n.Url != "" && URL.IsMatch(n.Url)); if (u != null) return "sign-in address " + u.Url.Split('?')[0];
    if (on.Any(n => n.Password)) return "password field";
    foreach (var n in on.Where(n => n.Role == "AXWindow" && n.Text.Count > 0)) if (TITLE.IsMatch(n.Text[0])) return "sign-in window title \"" + n.Text[0] + "\"";
    // the top-level window titles too (UIA names a Qt window by its title, but not every app does)
    foreach (var win in t.AppWindows()) if (W.Intersects(win.F, t.Win) && TITLE.IsMatch(win.Title)) return "sign-in window title \"" + win.Title + "\"";
    var fields = on.Where(n => n.Role == "AXTextField" || n.Role == "AXTextArea" || n.Role == "AXComboBox").ToList();
    if (fields.Count == 1) { var s = fields[0].Text.FirstOrDefault(x => EMAIL.IsMatch(x)); if (s != null) return "username or email sign-in field \"" + Cut(s, 40) + "\""; }
    if (fields.Count <= 1) {
      var s = on.Where(n => n.Role == "AXStaticText" || n.Role == "AXHeading").SelectMany(n => n.Text).FirstOrDefault(x => TEXT.IsMatch(x));
      if (s != null) return "sign-in text \"" + Cut(s, 60) + "\"";
    }
    return "";
  }
}

// ---------- the controlled app ----------
class AppWin { public IntPtr H; public W.RECT F; public string Title; public int Layer; public uint Pid; public bool Owned, Caption, Tool; }
class Target {
  public string Exe, Name, Mode; public Regex TitleRe;
  public IntPtr WinH = IntPtr.Zero; public W.RECT Win; public double Scale = 1; public uint MainPid;
  HashSet<uint> pids = new HashSet<uint>(); DateTime pidsAt = DateTime.MinValue; readonly object plk = new object();
  // corner color behind Windows 11's rounded window corners (the same as BACKGROUND in nativecap.swift)
  static readonly Color BACKGROUND = Color.FromArgb(242, 245, 249);
  static readonly bool ROUNDED = Environment.OSVersion.Version.Build >= 22000;

  public Target(string exe, string name, string mode, string title) {
    Exe = exe; Name = name; Mode = mode; if (!string.IsNullOrEmpty(title)) TitleRe = new Regex(title, RegexOptions.IgnoreCase);
  }
  public int W_ { get { return Win.R - Win.L; } }
  public int H_ { get { return Win.B - Win.T; } }
  public HashSet<uint> Pids() {
    lock (plk) {
      if ((DateTime.UtcNow - pidsAt).TotalSeconds > 2) {
        var s = new HashSet<uint>(); foreach (var p in Process.GetProcessesByName(Exe)) { s.Add((uint)p.Id); p.Dispose(); }
        pids = s; pidsAt = DateTime.UtcNow;
      }
      return pids;
    }
  }
  // every visible window of the app, front to back: the main window, and pop-ups such as an incoming-call toast
  public List<AppWin> AppWindows() {
    var ps = Pids(); var l = new List<AppWin>();
    foreach (var h in W.TopLevel()) {
      if (!W.IsWindowVisible(h) || W.IsIconic(h) || W.Cloaked(h)) continue;
      uint pid = W.Pid(h); if (!ps.Contains(pid) || W.Alpha(h) <= 0.05) continue;
      var f = W.Frame(h); if (f.R - f.L < 40 || f.B - f.T < 20) continue;
      int st = W.GetWindowLong(h, W.GWL_STYLE), ex = W.GetWindowLong(h, W.GWL_EXSTYLE);
      l.Add(new AppWin { H = h, F = f, Title = W.Title(h), Layer = (ex & W.WS_EX_TOPMOST) != 0 ? 1 : 0, Pid = pid,
                         Owned = W.GetWindow(h, W.GW_OWNER) != IntPtr.Zero, Caption = (st & W.WS_CAPTION) == W.WS_CAPTION, Tool = (ex & W.WS_EX_TOOLWINDOW) != 0 });
    }
    return l;
  }
  // the app's largest normal window: not owned by another, with a title bar, not a tool window
  AppWin MainWindow() {
    var c = AppWindows().Where(w => !w.Owned && !w.Tool && w.F.R - w.F.L >= 300 && w.F.B - w.F.T >= 200).ToList();
    if (TitleRe != null) c = c.Where(w => TitleRe.IsMatch(w.Title)).ToList();
    var best = c.Where(w => w.Caption).OrderByDescending(w => (long)(w.F.R - w.F.L) * (w.F.B - w.F.T)).FirstOrDefault();
    return best ?? c.OrderByDescending(w => (long)(w.F.R - w.F.L) * (w.F.B - w.F.T)).FirstOrDefault();
  }
  // the main window: the one already chosen while it is open, else the app's largest normal window
  public void Refresh() {
    if (WinH != IntPtr.Zero && W.IsWindow(WinH) && W.IsWindowVisible(WinH) && !W.IsIconic(WinH)) { Set(WinH); return; }
    var m = MainWindow();
    if (m == null) {   // minimized: restore it once
      foreach (var h in W.TopLevel()) if (Pids().Contains(W.Pid(h)) && W.IsIconic(h) && W.GetWindow(h, W.GW_OWNER) == IntPtr.Zero && W.IsWindowVisible(h)) { W.ShowWindow(h, W.SW_RESTORE); Thread.Sleep(600); break; }
      m = MainWindow();
    }
    if (m == null) throw new Fail(Name + " has no window on screen: open its main window and rerun" + (TitleRe != null ? " (none has a title matching \"" + TitleRe + "\")" : ""));
    Set(m.H);
  }
  // the display's scaling, not the window's: an app that is not DPI aware reports 96 everywhere
  void Set(IntPtr h) {
    WinH = h; Win = W.Frame(h); MainPid = W.Pid(h); uint dx = 0, dy;
    try { if (W.GetDpiForMonitor(W.MonitorFromWindow(h, W.MONITOR_DEFAULTTONEAREST), 0, out dx, out dy) != 0) dx = 0; } catch { dx = 0; }
    if (dx == 0) dx = W.GetDpiForWindow(h);
    Scale = dx > 0 ? dx / 96.0 : 1;
  }
  public bool IsFront() { var f = W.GetForegroundWindow(); return f != IntPtr.Zero && Pids().Contains(W.Pid(f)); }
  public void Activate() {
    Refresh(); IntPtr h = WinH;
    if (W.IsIconic(h)) W.ShowWindow(h, W.SW_RESTORE);
    if (!IsFront()) {
      // an empty input event lets this process move the focus (the foreground lock), as PowerToys does
      var none = new W.INPUT[] { new W.INPUT { type = 0 } }; W.SendInput(1, none, Marshal.SizeOf(typeof(W.INPUT)));
      W.SetForegroundWindow(h);
      if (!IsFront()) {
        uint fg = W.GetWindowThreadProcessId(W.GetForegroundWindow(), out fgPidUnused), me = W.GetCurrentThreadId();
        W.AttachThreadInput(fg, me, true); W.BringWindowToTop(h); W.SetForegroundWindow(h); W.AttachThreadInput(fg, me, false);
      }
    }
    W.SetWindowPos(h, IntPtr.Zero, 0, 0, 0, 0, W.SWP_NOMOVE | W.SWP_NOSIZE | W.SWP_NOACTIVATE);   // to the top
    Thread.Sleep(600);
  }
  uint fgPidUnused;
  W.RECT WorkArea() {
    var mi = new W.MONITORINFO { cbSize = Marshal.SizeOf(typeof(W.MONITORINFO)) };
    W.GetMonitorInfo(W.MonitorFromWindow(WinH, W.MONITOR_DEFAULTTONEAREST), ref mi); return mi.rcWork;
  }
  // place a window's visible frame (DWM bounds) at x, y with size w, h, allowing for its invisible resize border
  static void SetFrame(IntPtr h, int x, int y, int w, int hh, bool size) {
    W.RECT outer; W.GetWindowRect(h, out outer); var inner = W.Frame(h);
    int dl = inner.L - outer.L, dt = inner.T - outer.T, dr = outer.R - inner.R, db = outer.B - inner.B;
    uint fl = W.SWP_NOZORDER | W.SWP_NOACTIVATE | (size ? 0 : W.SWP_NOSIZE);
    W.SetWindowPos(h, IntPtr.Zero, x - dl, y - dt, w + dl + dr, hh + dt + db, fl);
  }
  // Bring the app to the front and size its main window to 16:9 on the display it is on, centered, or with anchor
  // "bottom-right" in the work area's bottom-right corner (where Webex opens its incoming-call toast). Sizes are in
  // points (pixels at 100% scaling), as on macOS: 1920x1080 is 2880x1620 pixels on a display at 150%.
  public Dictionary<string, object> Prep(double? w, double? h, string anchor) {
    if (anchor != "center" && anchor != "bottom-right") throw new Fail("unknown \"anchor\" \"" + anchor + "\" in job.json native: use \"center\" or \"bottom-right\"");
    Activate(); Refresh();
    bool? me = W.Elevated(W.GetCurrentProcess()), them = W.Elevated(MainPid);
    if (them == true && me != true) throw new Fail(Name + " runs as administrator, so Windows blocks the pointer and keyboard from this terminal: restart " + Name + " normally (not as administrator) and rerun");
    if (W.IsZoomed(WinH)) { W.ShowWindow(WinH, W.SW_RESTORE); Thread.Sleep(500); Refresh(); }
    var vis = WorkArea(); int vw = vis.R - vis.L, vh = vis.B - vis.T;
    var sizes = w.HasValue && h.HasValue ? new[] { new[] { w.Value, h.Value } }
      : new[] { new[] { 1920.0, 1080 }, new[] { 1600.0, 900 }, new[] { 1440.0, 810 }, new[] { 1280.0, 720 }, new[] { 1120.0, 630 } };
    var size = sizes.FirstOrDefault(s => Math.Round(s[0] * Scale) <= vw && Math.Round(s[1] * Scale) <= vh);
    if (size == null) throw new Fail("the window size " + sizes[0][0] + "x" + sizes[0][1] + " does not fit on this display (" + Math.Floor(vw / Scale) + "x" + Math.Floor(vh / Scale) + " points free at " + (Scale * 100) + "% scaling)");
    int pw = (int)Math.Round(size[0] * Scale), ph = (int)Math.Round(size[1] * Scale);
    int x = vis.L + (vw - pw) / 2, y = vis.T + (vh - ph) / 2;
    if (anchor == "bottom-right") { x = vis.R - pw; y = vis.B - ph; }
    for (int i = 0; i < 2; i++) { SetFrame(WinH, x, y, pw, ph, true); Thread.Sleep(400); }   // twice: a DPI change on the way settles too
    Refresh();
    if (Math.Abs((double)W_ / H_ - 16.0 / 9.0) > 0.01)
      throw new Fail(Name + "'s window is " + W_ + "x" + H_ + " pixels after resizing, not 16:9 (the app may have a minimum size); set \"size\" in job.json native to a size it accepts");
    return Info();
  }
  // x, y, w, h are screen pixels here (points on macOS); px is the recorded size on both
  public Dictionary<string, object> Info() {
    Ensure();
    return new Dictionary<string, object> { {"app", Name}, {"bundle", Exe + ".exe"}, {"pid", (int)MainPid}, {"mode", Mode},
      {"x", (double)Win.L}, {"y", (double)Win.T}, {"w", (double)W_}, {"h", (double)H_}, {"scale", Scale}, {"px", new[] { W_, H_ }}, {"platform", "windows"}};
  }
  // frame pixels (1920x1080) <-> screen pixels
  // before the first prep no window is chosen yet; pick it now, or frame math divides by zero
  public void Ensure() { if (WinH == IntPtr.Zero) Refresh(); }
  public W.POINT ToScreen(double x, double y) { Ensure(); return new W.POINT { X = (int)Math.Round(Win.L + x * W_ / 1920.0), Y = (int)Math.Round(Win.T + y * H_ / 1080.0) }; }
  public double[] ToFrame(W.RECT r) {
    Ensure(); double kx = 1920.0 / W_, ky = 1080.0 / H_;
    return new[] { (r.L - Win.L) * kx, (r.T - Win.T) * ky, (r.R - r.L) * kx, (r.B - r.T) * ky }.Select(v => Math.Round(v * 10) / 10).ToArray();
  }
  // what would receive a click at this point: null when it is the app, else the other app's name
  public string CoveredBy(W.POINT p) {
    IntPtr h = W.WindowFromPoint(p); if (h == IntPtr.Zero) return "nothing (the point is outside every window)";
    IntPtr root = W.GetAncestor(h, W.GA_ROOT); if (root == IntPtr.Zero) root = h;
    uint pid = W.Pid(root); if (Pids().Contains(pid)) return null;
    string exe = W.ExeName(pid); return exe == "" ? "another app" : exe;
  }
  // another app's window over the recorded area (it would be recorded in "app" mode): its program name, or ""
  public string CoveredArea() {
    var ps = Pids();
    foreach (var h in W.TopLevel()) {
      if (h == WinH) return "";   // the rest is behind the main window
      if (!W.IsWindowVisible(h) || W.IsIconic(h) || W.Cloaked(h) || W.Alpha(h) <= 0.05) continue;
      uint pid = W.Pid(h); if (ps.Contains(pid)) continue;
      var f = W.Frame(h); var i = W.Intersect(f, Win);
      if (i.R - i.L < 2 || i.B - i.T < 2) continue;
      string exe = W.ExeName(pid); return (exe == "" ? "another app" : exe) + " (a window over " + Name + ")";
    }
    return "";
  }
  public Dictionary<string, object> Place(IntPtr id, double[] box) {
    var w = AppWindows().FirstOrDefault(v => v.H == id); if (w == null) throw new Fail("no " + Name + " window with id " + id.ToInt64() + " on screen");
    double kx = W_ / 1920.0, ky = H_ / 1080.0; var b = box ?? new[] { 0.0, 0, 1920, 1080 };
    int x = (int)Math.Round(Win.L + b[0] * kx), y = (int)Math.Round(Win.T + b[1] * ky);
    bool size = b.Length == 4;
    SetFrame(id, x, y, size ? (int)Math.Round(b[2] * kx) : 0, size ? (int)Math.Round(b[3] * ky) : 0, size);
    W.SetWindowPos(id, IntPtr.Zero, 0, 0, 0, 0, W.SWP_NOMOVE | W.SWP_NOSIZE | W.SWP_NOACTIVATE);   // to the top
    Thread.Sleep(300);
    var n = AppWindows().FirstOrDefault(v => v.H == id); if (n == null) throw new Fail("the window closed while it was being moved");
    var f = ToFrame(n.F); return new Dictionary<string, object> { {"x", f[0]}, {"y", f[1]}, {"w", f[2]}, {"h", f[3]} };
  }
  public void CheckWindow() {
    // the main window by its handle, so a bigger call or meeting window opening on top does not count as a move
    if (!W.IsWindow(WinH) || !W.IsWindowVisible(WinH) || W.IsIconic(WinH)) throw new Fail(Name + "'s main window closed or was minimized");
    var f = W.Frame(WinH);
    if (Math.Abs(f.L - Win.L) > 1 || Math.Abs(f.T - Win.T) > 1 || Math.Abs((f.R - f.L) - W_) > 1)
      throw new Fail(Name + "'s window moved or changed size; run prep again (leave the window alone during a take)");
  }
  // one picture of the recorded area, W_ x H_ pixels
  public Bitmap Grab() {
    Bitmap b;
    if (Mode == "window") {
      W.RECT outer; W.GetWindowRect(WinH, out outer);
      using (var full = new Bitmap(outer.R - outer.L, outer.B - outer.T, PixelFormat.Format32bppRgb)) {
        using (var g = Graphics.FromImage(full)) { IntPtr dc = g.GetHdc(); try { W.PrintWindow(WinH, dc, 2); } finally { g.ReleaseHdc(dc); } }
        b = full.Clone(new Rectangle(Win.L - outer.L, Win.T - outer.T, W_, H_), PixelFormat.Format32bppRgb);
      }
    } else {
      b = new Bitmap(W_, H_, PixelFormat.Format32bppRgb);
      using (var g = Graphics.FromImage(b)) g.CopyFromScreen(Win.L, Win.T, 0, 0, new Size(W_, H_), CopyPixelOperation.SourceCopy);
    }
    if (ROUNDED && !W.IsZoomed(WinH)) {   // what shows behind the rounded corners
      int r = (int)Math.Round(8 * Scale); if (r > 0) {
        using (var g = Graphics.FromImage(b)) using (var path = new GraphicsPath()) {
          int d = 2 * r, w = W_, h = H_;
          path.AddArc(0, 0, d, d, 180, 90); path.AddArc(w - d, 0, d, d, 270, 90); path.AddArc(w - d, h - d, d, d, 0, 90); path.AddArc(0, h - d, d, d, 90, 90); path.CloseFigure();
          g.SetClip(path, CombineMode.Exclude); g.Clear(BACKGROUND);
        }
      }
    }
    return b;
  }
}

// ---------- recording ----------
class Recorder {
  readonly string dir; readonly long quality; readonly Target t; readonly int w, h;
  Thread cap; Thread[] enc; volatile bool run;
  readonly BlockingCollection<Tuple<byte[], int, string, double>> q = new BlockingCollection<Tuple<byte[], int, string, double>>(10);
  int n, dropped; readonly List<Dictionary<string, object>> frames = new List<Dictionary<string, object>>(); string error; readonly object lk = new object();
  static readonly ImageCodecInfo JPEG = ImageCodecInfo.GetImageEncoders().First(c => c.FormatID == ImageFormat.Jpeg.Guid);
  public Recorder(Target t, string dir, double quality) { this.t = t; this.dir = dir; this.quality = (long)Math.Round(quality); w = t.W_; h = t.H_; }
  public void Start() {
    Directory.CreateDirectory(dir);
    using (var test = t.Grab()) { }   // fails here, not in the thread, when the screen cannot be read
    run = true;
    enc = Enumerable.Range(0, Math.Max(2, Math.Min(4, Environment.ProcessorCount / 2))).Select(i => new Thread(Encode) { IsBackground = true }).ToArray();
    foreach (var e in enc) e.Start();
    cap = new Thread(Capture) { IsBackground = true, Priority = ThreadPriority.AboveNormal }; cap.Start();
  }
  void Capture() {
    var sw = Stopwatch.StartNew(); const double period = 1000.0 / 30; long k = 0; byte[] prev = null, buf = null;
    while (run) {
      double due = k * period, now = sw.Elapsed.TotalMilliseconds;
      if (due > now) Thread.Sleep((int)Math.Ceiling(due - now));
      k = Math.Max(k + 1, (long)(sw.Elapsed.TotalMilliseconds / period));   // fell behind: skip ahead, do not burst
      double ts = W.Now(); int stride;
      try {
        using (var b = t.Grab()) {
          var data = b.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format32bppRgb);
          try { stride = data.Stride; if (buf == null || buf.Length != stride * h) buf = new byte[stride * h]; Marshal.Copy(data.Scan0, buf, 0, buf.Length); }
          finally { b.UnlockBits(data); }
        }
      } catch (Exception e) { error = "the screen could not be read (" + e.Message + "; a locked screen or an administrator prompt does this)"; run = false; break; }
      if (prev != null && prev.Length == buf.Length && W.memcmp(prev, buf, (UIntPtr)buf.Length) == 0) continue;   // unchanged
      string name = n.ToString("D5") + ".jpg";
      // only the newest frames matter: when the encoders fall behind, drop this one rather than queue memory
      if (!q.TryAdd(Tuple.Create(buf, stride, name, ts))) { dropped++; continue; }
      n++; prev = buf; buf = null;
    }
  }
  void Encode() {
    var ps = new EncoderParameters(1); ps.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, quality);
    foreach (var f in q.GetConsumingEnumerable()) {
      var pin = GCHandle.Alloc(f.Item1, GCHandleType.Pinned);
      try {
        using (var b = new Bitmap(w, h, f.Item2, PixelFormat.Format32bppRgb, pin.AddrOfPinnedObject())) b.Save(Path.Combine(dir, f.Item3), JPEG, ps);
        lock (lk) frames.Add(new Dictionary<string, object> { {"f", f.Item3}, {"t", f.Item4} });
      } catch { } finally { pin.Free(); }
    }
  }
  public Dictionary<string, object> Stop() {
    run = false; if (cap != null) cap.Join(); q.CompleteAdding(); if (enc != null) foreach (var e in enc) e.Join();
    lock (lk) return new Dictionary<string, object> { {"frames", frames.OrderBy(f => (string)f["f"], StringComparer.Ordinal).ToList()}, {"dropped", dropped}, {"error", error ?? ""} };
  }
}

// ---------- input ----------
class Input {
  readonly Target t; W.POINT pos; double wheelRest, hwheelRest;
  public Input(Target t) { this.t = t; }
  static readonly Dictionary<string, ushort> KEYS = new Dictionary<string, ushort>(StringComparer.OrdinalIgnoreCase) {
    {"return", 0x0D}, {"enter", 0x0D}, {"tab", 0x09}, {"space", 0x20}, {"delete", 0x08}, {"backspace", 0x08}, {"escape", 0x1B}, {"esc", 0x1B},
    {"forwarddelete", 0x2E}, {"insert", 0x2D}, {"home", 0x24}, {"end", 0x23}, {"pageup", 0x21}, {"pagedown", 0x22},
    {"left", 0x25}, {"up", 0x26}, {"right", 0x27}, {"down", 0x28},
    {"=", 0xBB}, {"-", 0xBD}, {",", 0xBC}, {".", 0xBE}, {"/", 0xBF}, {"`", 0xC0}, {"[", 0xDB}, {"\\", 0xDC}, {"]", 0xDD}, {"'", 0xDE}, {";", 0xBA}};
  static readonly HashSet<ushort> EXTENDED = new HashSet<ushort> { 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B };
  static readonly Dictionary<string, ushort> MODS = new Dictionary<string, ushort>(StringComparer.OrdinalIgnoreCase) {
    {"ctrl", 0x11}, {"control", 0x11}, {"cmd", 0x11}, {"command", 0x11}, {"shift", 0x10}, {"alt", 0x12}, {"option", 0x12}, {"win", 0x5B}, {"windows", 0x5B}};
  static Input() {
    for (char c = 'a'; c <= 'z'; c++) KEYS[c.ToString()] = (ushort)char.ToUpperInvariant(c);
    for (char c = '0'; c <= '9'; c++) KEYS[c.ToString()] = c;
    for (int i = 1; i <= 12; i++) KEYS["f" + i] = (ushort)(0x6F + i);
  }
  static void Send(params W.INPUT[] a) { W.SendInput((uint)a.Length, a, Marshal.SizeOf(typeof(W.INPUT))); }
  static W.INPUT Mouse(uint flags, int dx = 0, int dy = 0, int data = 0) { return new W.INPUT { type = 0, u = new W.INPUTU { mi = new W.MOUSEINPUT { dx = dx, dy = dy, mouseData = data, dwFlags = flags } } }; }
  static W.INPUT Kbd(ushort vk, ushort scan, uint flags) { return new W.INPUT { type = 1, u = new W.INPUTU { ki = new W.KEYBDINPUT { wVk = vk, wScan = scan, dwFlags = flags } } }; }
  static W.INPUT Vk(ushort vk, bool down) { return Kbd(vk, (ushort)W.MapVirtualKey(vk, 0), (EXTENDED.Contains(vk) ? 1u : 0u) | (down ? 0u : 2u)); }
  void Front() { if (!t.IsFront()) throw new Fail(t.Name + " is not the front app (something else took focus); input refused"); }
  public void Move(double x, double y) {
    pos = t.ToScreen(x, y);
    int vx = W.GetSystemMetrics(76), vy = W.GetSystemMetrics(77), vw = W.GetSystemMetrics(78), vh = W.GetSystemMetrics(79);
    int nx = (int)Math.Round((pos.X - vx) * 65535.0 / Math.Max(1, vw - 1)), ny = (int)Math.Round((pos.Y - vy) * 65535.0 / Math.Max(1, vh - 1));
    Send(Mouse(0x0001 | 0x8000 | 0x4000, nx, ny));   // MOVE | ABSOLUTE | VIRTUALDESK; a held button makes it a drag
  }
  public void Button(bool down, bool right) {
    if (down) { var other = t.CoveredBy(pos); if (other != null) throw new Fail("click refused: " + other + " is in front of " + t.Name + " at that point"); t.CheckWindow(); }
    Send(Mouse(right ? (down ? 0x0008u : 0x0010u) : (down ? 0x0002u : 0x0004u)));   // Windows makes a double click from the timing
  }
  public void Type(string s) {
    if (s.Contains("\n") || s.Contains("\r")) throw new Fail("type() takes no line breaks: press keys with key('return') (or key('return', ['shift']) for a new line)");
    Front();
    foreach (char c in s) Send(Kbd(0, c, 0x0004), Kbd(0, c, 0x0004 | 0x0002));   // UNICODE down, up
  }
  public void Key(string name, List<string> mods) {
    ushort vk; if (!KEYS.TryGetValue(name, out vk)) throw new Fail("unknown key \"" + name + "\"; known: " + string.Join(" ", KEYS.Keys.OrderBy(k => k, StringComparer.Ordinal)));
    var mv = new List<ushort>();
    foreach (var m in mods) { ushort v; if (!MODS.TryGetValue(m, out v)) throw new Fail("unknown modifier \"" + m + "\" (ctrl, shift, alt, win; cmd means ctrl)"); if (!mv.Contains(v)) mv.Add(v); }
    Front();
    var seq = new List<W.INPUT>(); foreach (var m in mv) seq.Add(Vk(m, true));
    seq.Add(Vk(vk, true)); seq.Add(Vk(vk, false));
    for (int i = mv.Count - 1; i >= 0; i--) seq.Add(Vk(mv[i], false));
    Send(seq.ToArray());
  }
  // dy > 0 scrolls down (the content moves up), as page.mouse.wheel does in Chrome takes; in frame pixels, about
  // 100 screen pixels per wheel notch (120 units). Refused where another window covers the pointer, as a click is.
  public void Scroll(double dy, double dx) {
    Front();
    var other = t.CoveredBy(pos); if (other != null) throw new Fail("scroll refused: " + other + " is in front of " + t.Name + " at the pointer");
    double k = t.W_ / 1920.0 * 1.2;
    wheelRest += -dy * k; hwheelRest += dx * k;
    int v = (int)wheelRest, hz = (int)hwheelRest; wheelRest -= v; hwheelRest -= hz;
    if (v != 0) Send(Mouse(0x0800, 0, 0, v));
    if (hz != 0) Send(Mouse(0x1000, 0, 0, hz));
  }
}

// ---------- server ----------
class Worker {
  readonly BlockingCollection<Action> q = new BlockingCollection<Action>();
  public Worker() { var th = new Thread(() => { foreach (var a in q.GetConsumingEnumerable()) a(); }) { IsBackground = true }; th.SetApartmentState(ApartmentState.MTA); th.Start(); }
  public void Post(Action a) { q.Add(a); }
}

static class Program {
  static double? Num(Dictionary<string, object> m, string k) { object v; return m.TryGetValue(k, out v) && v != null && !(v is string) ? (double?)Convert.ToDouble(v, CultureInfo.InvariantCulture) : null; }
  static string Str(Dictionary<string, object> m, string k) { object v; return m.TryGetValue(k, out v) ? v as string : null; }
  static List<object> Arr(Dictionary<string, object> m, string k) { object v; return m.TryGetValue(k, out v) && v is IEnumerable && !(v is string) ? ((IEnumerable)v).Cast<object>().ToList() : null; }
  static Dictionary<string, object> D(params object[] kv) { var d = new Dictionary<string, object>(); for (int i = 0; i < kv.Length; i += 2) d[(string)kv[i]] = kv[i + 1]; return d; }
  static Dictionary<string, object> Perms() { return D("screen", true, "accessibility", true, "platform", "windows"); }

  static void Serve(Target t) {
    var input = new Input(t); Recorder rec = null;
    var cmdq = new Worker(); var axq = new Worker();   // the UI Automation walks run on their own queue so pointer moves keep flowing
    Func<Dictionary<string, object>, Dictionary<string, object>> handle = m => {
      string op = Str(m, "op") ?? "";
      if (op != "check" && op != "quit" && op != "prep") t.Ensure();   // every other op works on the main window
      switch (op) {
        case "check": return Perms();
        case "prep": return t.Prep(Num(m, "w"), Num(m, "h"), Str(m, "anchor") ?? "center");
        case "window": return t.Info();
        case "windows":
          return D("windows", t.AppWindows().Select(w => { var f = t.ToFrame(w.F);
            return (object)D("id", w.H.ToInt64(), "title", w.Title, "layer", w.Layer, "main", w.H == t.WinH, "x", f[0], "y", f[1], "w", f[2], "h", f[3]); }).ToList());
        case "place": {
          var id = Num(m, "window"); if (id == null) throw new Fail("place needs a window (its id from windows)");
          var box = Arr(m, "box"); return t.Place(new IntPtr((long)id.Value), box == null ? null : box.Select(v => Convert.ToDouble(v, CultureInfo.InvariantCulture)).ToArray());
        }
        case "activate": t.Activate(); return D();
        case "guard": {
          string moved = ""; try { t.CheckWindow(); } catch (Fail f) { moved = f.Message; }
          string covered = t.Mode == "window" ? "" : t.CoveredArea();
          return D("reason", SignIn.Reason(t), "moved", moved, "front", t.IsFront(), "covered", covered);
        }
        case "text": {
          int lim = (int)(Num(m, "max") ?? 20000); bool anywhere = m.ContainsKey("anywhere") && m["anywhere"] is bool && (bool)m["anywhere"];
          var lines = new List<string>();
          foreach (var n in Ax.WalkApp(t, anywhere ? (W.RECT?)null : t.Win)) {
            if (!n.HasFrame || n.Frame.R - n.Frame.L <= 1 || n.Frame.B - n.Frame.T <= 1) continue;
            foreach (var s in n.Text) if (lines.Count == 0 || lines[lines.Count - 1] != s) lines.Add(s);
          }
          string all = string.Join("\n", lines); return D("text", all.Length > lim ? all.Substring(all.Length - lim) : all);
        }
        case "find": {
          string pat = Str(m, "pattern"); Regex re;
          try { re = new Regex(pat, RegexOptions.IgnoreCase); } catch { throw new Fail("find needs a valid pattern"); }
          string role = Str(m, "role"); bool anywhere = m.ContainsKey("anywhere") && m["anywhere"] is bool && (bool)m["anywhere"];
          var hits = Ax.WalkApp(t, anywhere ? (W.RECT?)null : t.Win)
            .Where(n => n.HasFrame && n.Frame.R - n.Frame.L > 1 && n.Frame.B - n.Frame.T > 1)
            .Where(n => role == null || string.Equals(n.Role, role, StringComparison.OrdinalIgnoreCase) || string.Equals(n.Uia, role, StringComparison.OrdinalIgnoreCase))
            .Where(n => n.Text.Any(s => re.IsMatch(s))).Take(50)
            .Select(n => { var b = t.ToFrame(n.Frame); string txt = string.Join(" | ", n.Text);
              return (object)D("role", n.Role, "uia", n.Uia, "text", txt.Length > 200 ? txt.Substring(0, 200) : txt, "x", b[0], "y", b[1], "w", b[2], "h", b[3]); }).ToList();
          return D("hits", hits);
        }
        case "shot": {
          string path = Str(m, "path"); if (path == null) throw new Fail("shot needs a path");
          string why = SignIn.Reason(t); if (why != "") return D("refused", why);
          if (t.Mode != "window") { string c = t.CoveredArea(); if (c != "") return D("refused", "covered by " + c); }
          Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
          using (var b = t.Grab()) using (var o = new Bitmap(1920, 1080, PixelFormat.Format24bppRgb)) {
            using (var g = Graphics.FromImage(o)) { g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.PixelOffsetMode = PixelOffsetMode.HighQuality; g.DrawImage(b, 0, 0, 1920, 1080); }
            o.Save(path, ImageFormat.Png);
          }
          return D("path", path);
        }
        case "start": {
          if (rec != null) throw new Fail("already recording");
          string dir = Str(m, "dir"); if (dir == null) throw new Fail("start needs a dir");
          t.CheckWindow();
          var r = new Recorder(t, dir, Num(m, "quality") ?? 90); r.Start(); rec = r; return t.Info();
        }
        case "stop": { if (rec == null) throw new Fail("not recording"); var r = rec; rec = null; return r.Stop(); }
        case "move": input.Move(Num(m, "x") ?? 0, Num(m, "y") ?? 0); return D();
        case "down": input.Button(true, Str(m, "button") == "right"); return D();
        case "up": input.Button(false, Str(m, "button") == "right"); return D();
        case "type": input.Type(Str(m, "text") ?? ""); return D();
        case "key": { var mods = Arr(m, "mods"); input.Key(Str(m, "key") ?? "", mods == null ? new List<string>() : mods.Select(x => Convert.ToString(x)).ToList()); return D(); }
        case "scroll": input.Scroll(Num(m, "dy") ?? 0, Num(m, "dx") ?? 0); return D();
        case "quit": { if (rec != null) { try { rec.Stop(); } catch { } } object qid; m.TryGetValue("id", out qid); Out.Emit(D("id", qid ?? 0, "ok", true)); Environment.Exit(0); return D(); }
        default: throw new Fail("unknown op \"" + op + "\"");
      }
    };
    var stdin = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false)); string line;
    while ((line = stdin.ReadLine()) != null) {
      Dictionary<string, object> msg; try { msg = Out.Json.Deserialize<Dictionary<string, object>>(line); } catch { continue; }
      if (msg == null) continue;
      object id; msg.TryGetValue("id", out id); id = id ?? 0;
      string op = Str(msg, "op") ?? "";
      var mm = msg; var iid = id;
      (op == "guard" || op == "text" || op == "find" ? axq : cmdq).Post(() => {
        Dictionary<string, object> r;
        try { r = handle(mm); r["id"] = iid; r["ok"] = true; }
        catch (Fail f) { r = D("id", iid, "ok", false, "error", f.Message); }
        catch (Exception e) { r = D("id", iid, "ok", false, "error", e.GetType().Name + ": " + e.Message); }
        Out.Emit(r);
      });
    }
    cmdq.Post(() => { if (rec != null) { try { rec.Stop(); } catch { } } Environment.Exit(0); });   // stdin closed: finish writing frames, then quit
    Thread.Sleep(Timeout.Infinite);
  }

  // processes with a normal window on screen: (pid, exe name, file description, title, w, h)
  static List<Tuple<uint, string, string, string, int, int>> Apps() {
    var l = new List<Tuple<uint, string, string, string, int, int>>(); var seen = new Dictionary<uint, Tuple<string, string>>();
    uint me = (uint)Process.GetCurrentProcess().Id;
    foreach (var h in W.TopLevel()) {
      if (!W.IsWindowVisible(h) || W.IsIconic(h) || W.Cloaked(h) || W.GetWindow(h, W.GW_OWNER) != IntPtr.Zero) continue;
      if ((W.GetWindowLong(h, W.GWL_EXSTYLE) & W.WS_EX_TOOLWINDOW) != 0) continue;
      var f = W.Frame(h); if (f.R - f.L < 200 || f.B - f.T < 100) continue;
      uint pid = W.Pid(h); if (pid == me) continue;
      Tuple<string, string> info;
      if (!seen.TryGetValue(pid, out info)) { string p = W.ImagePath(pid); info = Tuple.Create(p == "" ? "" : Path.GetFileNameWithoutExtension(p), p == "" ? "" : W.Description(p)); seen[pid] = info; }
      if (info.Item1 == "") continue;
      l.Add(Tuple.Create(pid, info.Item1, info.Item2, W.Title(h), f.R - f.L, f.B - f.T));
    }
    return l;
  }
  // the app by program name, file description, or window title: exact first, then by prefix
  static Target FindApp(string q, string mode, string title) {
    var apps = Apps(); string l = q.ToLowerInvariant(); if (l.EndsWith(".exe")) l = l.Substring(0, l.Length - 4);
    var tests = new List<Func<Tuple<uint, string, string, string, int, int>, bool>> {
      a => a.Item2.ToLowerInvariant() == l, a => a.Item3.ToLowerInvariant() == l, a => a.Item4.ToLowerInvariant() == l,
      a => a.Item3.ToLowerInvariant().StartsWith(l), a => a.Item4.ToLowerInvariant().StartsWith(l), a => a.Item2.ToLowerInvariant().StartsWith(l) };
    foreach (var test in tests) {
      var a = apps.Where(test).OrderByDescending(x => (long)x.Item5 * x.Item6).FirstOrDefault();
      if (a != null) return new Target(a.Item2, a.Item3 != "" ? a.Item3 : a.Item2, mode, title);
    }
    return null;
  }

  static int Main(string[] args) {
    try { if (!W.SetProcessDpiAwarenessContext(new IntPtr(-4))) W.SetProcessDPIAware(); } catch { try { W.SetProcessDPIAware(); } catch { } }
    CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture; Thread.CurrentThread.CurrentCulture = CultureInfo.InvariantCulture;
    Out.Init();
    Func<string, string> arg = k => { int i = Array.IndexOf(args, k); return i >= 0 && i + 1 < args.Length ? args[i + 1] : null; };
    switch (args.Length > 0 ? args[0] : "") {
      case "check": Out.Emit(Perms()); return 0;
      case "list": {
        var best = new Dictionary<string, Tuple<uint, string, string, string, int, int>>();
        foreach (var a in Apps()) { Tuple<uint, string, string, string, int, int> b; if (!best.TryGetValue(a.Item2, out b) || (long)a.Item5 * a.Item6 > (long)b.Item5 * b.Item6) best[a.Item2] = a; }
        Out.Emit(D("apps", best.Values.Select(a => (object)D("app", a.Item3 != "" ? a.Item3 : a.Item2, "bundle", a.Item2, "w", (double)a.Item5, "h", (double)a.Item6)).ToList()));
        return 0;
      }
      case "serve": {
        string q = arg("--app"); Target t = q == null ? null : FindApp(q, arg("--mode") == "window" ? "window" : "app", arg("--title"));
        if (t == null) { Out.Emit(D("ok", false, "error", "app \"" + (q ?? "") + "\" is not running: open it, sign in off camera, and rerun")); return 1; }
        Serve(t); return 0;
      }
      default:
        Console.Error.WriteLine("usage: nativecap check [--prompt] | list | serve --app <name> [--mode app|window] [--title <regex>]"); return 64;
    }
  }
}
