// tlbconv: build step for nativecap.cs on Windows. Turns the UI Automation type library inside
// %WINDIR%\System32\UIAutomationCore.dll into an interop assembly, so the helper can use the native COM UI Automation
// client (much faster than System.Windows.Automation) without the Windows SDK's tlbimp.
// usage: tlbconv <UIAutomationCore.dll> <out: Interop.UIAutomationClient.dll>   (run with the output folder as cwd)
using System; using System.IO; using System.Reflection; using System.Runtime.InteropServices;

class Sink : ITypeLibImporterNotifySink {
  public void ReportEvent(ImporterEventKind kind, int code, string msg) { }
  public Assembly ResolveRef(object typeLib) { return null; }
}

static class TlbConv {
  [DllImport("oleaut32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
  static extern void LoadTypeLibEx(string file, int regKind, [MarshalAs(UnmanagedType.Interface)] out object typeLib);

  static int Main(string[] a) {
    if (a.Length != 2) { Console.Error.WriteLine("usage: tlbconv <UIAutomationCore.dll> <Interop.UIAutomationClient.dll>"); return 64; }
    object tl; LoadTypeLibEx(a[0], 2 /* REGKIND_NONE */, out tl);
    string outp = Path.GetFullPath(a[1]);
    var asm = new TypeLibConverter().ConvertTypeLibToAssembly(tl, outp, TypeLibImporterFlags.None, new Sink(), null, null, "UIAutomationClient", null);
    asm.Save(Path.GetFileName(outp));
    return 0;
  }
}
