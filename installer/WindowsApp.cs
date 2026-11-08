using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class App {
    internal const string Id = "lipedevpop.TradutorSL";
    internal const string RegistryPath = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\TradutorSL";
    internal static JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 16000000 };
    internal static T Read<T>(string path) { return Json.Deserialize<T>(File.ReadAllText(path, Encoding.UTF8)); }
    internal static void Write(string path, object value) {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        File.WriteAllText(temporary, Json.Serialize(value), new UTF8Encoding(false));
        if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
    }
    internal static string Quote(string value) {
        var result = new StringBuilder("\""); int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { result.Append('\\', slashes * 2 + 1); result.Append(c); slashes = 0; continue; }
            result.Append('\\', slashes); slashes = 0; result.Append(c);
        }
        result.Append('\\', slashes * 2); return result.Append('"').ToString();
    }
    internal static string Inside(string root, string relative) {
        if (String.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative) || relative.Contains(":"))
            throw new IOException("Caminho de instalação inválido.");
        string parent = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string path = Path.GetFullPath(Path.Combine(parent, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!path.StartsWith(parent, StringComparison.OrdinalIgnoreCase)) throw new IOException("Caminho fora da pasta do aplicativo.");
        return path;
    }
    internal static void CheckTarget(string path) {
        path = Path.GetFullPath(path).TrimEnd('\\');
        string[] protectedFolders = {Path.GetPathRoot(path).TrimEnd('\\'),
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles)};
        if (protectedFolders.Any(p => String.Equals(path, p.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)))
            throw new IOException("Escolha uma pasta exclusiva para o Tradutor SL.");
        var ancestor = new DirectoryInfo(path);
        while (ancestor != null) {
            if (ancestor.Exists && (ancestor.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new IOException("Escolha uma pasta sem links ou redirecionamentos.");
            ancestor = ancestor.Parent;
        }
        if (Directory.Exists(path) && Directory.EnumerateFileSystemEntries(path).Any()) {
            string marker = Path.Combine(path, ".tradutor-install.json");
            if (!File.Exists(marker) || Read<InstallRecord>(marker).Id != Id)
                throw new IOException("Essa pasta contém outros arquivos. Escolha uma pasta vazia para o Tradutor SL.");
        }
    }
    internal static Process StartPython(string root, string arguments, bool probe) {
        string relative = File.ReadAllText(Path.Combine(root, "bootstrap-runtime.txt")).Trim();
        if (!relative.StartsWith("runtimes/", StringComparison.Ordinal)) throw new IOException("Componentes de inicialização inválidos.");
        string runtime = Inside(root, relative);
        if (probe) runtime = Path.Combine(Path.GetDirectoryName(runtime), "python.exe");
        var info = new ProcessStartInfo(runtime, arguments) { WorkingDirectory = root,
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = probe, RedirectStandardError = probe };
        info.EnvironmentVariables.Remove("PYTHONHOME"); info.EnvironmentVariables.Remove("PYTHONPATH");
        return Process.Start(info);
    }
    internal static void Launch(string root, string[] args) {
        var arguments = "-E -s " + Quote(Path.Combine(root, "iniciar.py"));
        foreach (string arg in args) arguments += " " + Quote(arg);
        StartPython(root, arguments, false);
    }
    internal static object ShellShortcut(string path) {
        object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell"));
        try { return shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path }); }
        finally { Marshal.FinalReleaseComObject(shell); }
    }
    internal static void Shortcut(string link, string target, string root) {
        Directory.CreateDirectory(Path.GetDirectoryName(link));
        object shortcut = ShellShortcut(link);
        try {
            var type = shortcut.GetType();
            foreach (var pair in new Dictionary<string, object> { {"TargetPath", target}, {"WorkingDirectory", root},
                {"IconLocation", target + ",0"}, {"Description", "Tradutor SL"} })
                type.InvokeMember(pair.Key, BindingFlags.SetProperty, null, shortcut, new object[] { pair.Value });
            type.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
        } finally { Marshal.FinalReleaseComObject(shortcut); }
    }
    internal static bool OwnShortcut(string link, string root) {
        if (!File.Exists(link)) return false;
        object shortcut = ShellShortcut(link);
        try {
            string target = (string)shortcut.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, shortcut, null);
            return String.Equals(Path.GetFullPath(target), Path.Combine(root, "Tradutor SL.exe"), StringComparison.OrdinalIgnoreCase);
        } finally { Marshal.FinalReleaseComObject(shortcut); }
    }
    internal static FileStream Lock(string root) {
        Directory.CreateDirectory(Path.Combine(root, ".updates"));
        try { return new FileStream(Path.Combine(root, ".updates", "app.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
        catch (IOException) { throw new IOException("Feche o Tradutor SL antes de instalar ou desinstalar."); }
    }
    internal static void DeleteTree(string path) {
        if (!Directory.Exists(path)) return;
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) { Directory.Delete(path); return; }
        foreach (string file in Directory.GetFiles(path)) {
            if ((File.GetAttributes(file) & FileAttributes.ReparsePoint) == 0) File.SetAttributes(file, FileAttributes.Normal);
            File.Delete(file);
        }
        foreach (string dir in Directory.GetDirectories(path)) {
            if ((File.GetAttributes(dir) & FileAttributes.ReparsePoint) != 0) Directory.Delete(dir);
            else DeleteTree(dir);
        }
        Directory.Delete(path);
    }
    internal static void Uninstall(string root, bool test) {
        root = Path.GetFullPath(root).TrimEnd('\\'); CheckTarget(root);
        string marker = Path.Combine(root, ".tradutor-install.json");
        var record = Read<InstallRecord>(marker);
        if (record.Id != Id || record.Test != test || !String.Equals(record.Root, root, StringComparison.OrdinalIgnoreCase))
            throw new IOException("A instalação não pôde ser identificada.");
        using (Lock(root)) { }
        foreach (string link in record.Shortcuts) if (OwnShortcut(link, root)) File.Delete(link);
        if (!test) {
            using (var key = Registry.CurrentUser.OpenSubKey(RegistryPath)) {
                if (key != null && String.Equals((string)key.GetValue("InstallLocation"), root, StringComparison.OrdinalIgnoreCase)) {
                    key.Close(); Registry.CurrentUser.DeleteSubKeyTree(RegistryPath, false);
                }
            }
        }
        foreach (string dir in new[] {"versions", "runtimes", ".updates", "__pycache__"}) DeleteTree(Inside(root, dir));
        foreach (string name in record.RootFiles.Concat(new[] {".active-version.json", ".previous-version.json", ".pending-update.json",
            "update-source.json", "update-preferences.json", ".tradutor-install.json"}).Distinct()) {
            string file = Inside(root, name); if (File.Exists(file)) File.Delete(file);
        }
        if (!Directory.EnumerateFileSystemEntries(root).Any()) Directory.Delete(root);
    }
    [STAThread]
    internal static int Main(string[] args) {
        AppContext.SetSwitch("Switch.System.IO.UseLegacyPathHandling", false);
        AppContext.SetSwitch("Switch.System.IO.BlockLongPaths", false);
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        try {
#if SETUP
            if (args.Length == 4 && args[0] == "--test-install") {
                Installer.Install(args[1], args[2], args[3], true, true, (p, text) => Console.WriteLine(text)); return 0;
            }
            if (args.Length == 2 && args[0] == "--test-uninstall") { Uninstall(args[1], true); return 0; }
            if (args.Length == 2 && args[0] == "--test-ui") {
                using (var form = new SetupForm()) {
                    form.Show(); Application.DoEvents();
                    using (var bitmap = new Bitmap(form.Width, form.Height)) {
                        form.DrawToBitmap(bitmap, new Rectangle(0, 0, form.Width, form.Height));
                        bitmap.Save(args[1], System.Drawing.Imaging.ImageFormat.Png);
                    }
                    form.Close();
                }
                return 0;
            }
            Application.Run(new SetupForm());
#else
            string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            if (args.Length > 0 && args[0] == "--uninstall") {
                string helper = Path.Combine(Path.GetTempPath(), "TradutorSL-Remover-" + Guid.NewGuid().ToString("N") + ".exe");
                File.Copy(Application.ExecutablePath, helper);
                Process.Start(new ProcessStartInfo(helper, "--remove-from " + Quote(root)) { UseShellExecute = false, CreateNoWindow = true }); return 0;
            }
            if (args.Length == 2 && args[0] == "--remove-from") {
                if (MessageBox.Show("Desinstalar o Tradutor SL?\n\nSuas configurações e a chave DeepL salva serão mantidas.",
                    "Tradutor SL", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes) {
                    Uninstall(args[1], false); MessageBox.Show("Tradutor SL desinstalado.", "Tradutor SL");
                }
                return 0;
            }
            Launch(root, args);
#endif
            return 0;
        } catch (Exception error) {
#if SETUP
            if (args.Length > 0) { Console.Error.WriteLine(error.ToString()); return 1; }
#endif
            MessageBox.Show(error.Message, "Tradutor SL", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1;
        }
    }
}

internal sealed class InstallRecord {
    public string Id { get; set; }
    public string Root { get; set; }
    public string Version { get; set; }
    public bool Test { get; set; }
    public string[] Shortcuts { get; set; }
    public string[] RootFiles { get; set; }
}
internal sealed class Payload {
    public string Id { get; set; }
    public string Version { get; set; }
    public Dictionary<string,string> Files { get; set; }
}

#if SETUP
internal static class Installer {
    internal static string DefaultPath() {
        using (var key = Registry.CurrentUser.OpenSubKey(App.RegistryPath)) {
            if (key != null && key.GetValue("InstallLocation") is string) return (string)key.GetValue("InstallLocation");
        }
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "TradutorSL");
    }
    internal static void Install(string target, string desktop, string menu, bool createDesktop, bool test, Action<int,string> progress) {
        if (!Environment.Is64BitOperatingSystem) throw new IOException("Esta edição requer Windows de 64 bits.");
        target = Path.GetFullPath(target).TrimEnd('\\'); App.CheckTarget(target);
        bool targetExisted = Directory.Exists(target);
        string parent = Path.GetDirectoryName(target); Directory.CreateDirectory(parent);
        string stage = Path.Combine(parent, ".TradutorSL-preparo-" + Guid.NewGuid().ToString("N"));
        string backup = Path.Combine(parent, ".TradutorSL-recuperacao-" + Guid.NewGuid().ToString("N"));
        var copied = new List<string>(); var existed = new HashSet<string>(); var createdLinks = new List<string>();
        Directory.CreateDirectory(stage); Directory.CreateDirectory(backup);
        bool success = false;
        try {
            progress(3, "Conferindo o instalador…");
            var assembly = Assembly.GetExecutingAssembly();
            using (Stream input = assembly.GetManifestResourceStream("payload.zip")) {
                string hash; using (var sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
                if (hash != BuildInfo.PayloadHash) throw new IOException("O instalador está incompleto. Baixe o arquivo novamente.");
                input.Position = 0;
                using (var zip = new ZipArchive(input, ZipArchiveMode.Read)) {
                    int count = zip.Entries.Count, index = 0;
                    if (count > 25000 || zip.Entries.Sum(e => e.Length) > 700L * 1024 * 1024) throw new IOException("Pacote inválido.");
                    foreach (var entry in zip.Entries) {
                        string destination = App.Inside(stage, entry.FullName);
                        Directory.CreateDirectory(Path.GetDirectoryName(destination));
                        using (var source = entry.Open()) using (var output = File.Create(destination)) source.CopyTo(output);
                        index++; if (index % 30 == 0) progress(5 + index * 35 / count, "Preparando os componentes…");
                    }
                }
            }
            var manifest = App.Read<Payload>(Path.Combine(stage, "payload-manifest.json"));
            if (manifest.Id != App.Id || manifest.Version != BuildInfo.Version) throw new IOException("Identificação do aplicativo inválida.");
            foreach (var file in manifest.Files) {
                string hash; using (var sha = SHA256.Create()) using (var input = File.OpenRead(App.Inside(stage, file.Key)))
                    hash = BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
                if (hash != file.Value) throw new IOException("Componente incompleto: " + file.Key);
            }
            progress(45, "Testando os componentes do tradutor…");
            using (var process = App.StartPython(stage, "-E -s " + App.Quote(Path.Combine(stage, "verificar_instalacao.py")), true)) {
                var stdout = process.StandardOutput.ReadToEndAsync(); var stderr = process.StandardError.ReadToEndAsync();
                if (!process.WaitForExit(90000)) { process.Kill(); throw new IOException("Os componentes demoraram demais para iniciar."); }
                Task.WaitAll(stdout, stderr);
                if (process.ExitCode != 0) throw new IOException("Não foi possível preparar o tradutor.\n" + stderr.Result);
            }
            Directory.CreateDirectory(target);
            using (App.Lock(target)) {
                string prior = null;
                foreach (string name in new[] {".active-version.json", ".install-version.json"})
                    if (File.Exists(Path.Combine(target, name))) { prior = File.ReadAllText(Path.Combine(target, name)); break; }
                var files = manifest.Files.Keys.Concat(new[] {"payload-manifest.json"}).ToList(); int index = 0;
                foreach (string name in files) {
                    CopyWithBackup(stage, target, backup, name, copied, existed);
                    if (++index % 30 == 0) progress(55 + index * 35 / files.Count, "Instalando o Tradutor SL…");
                }
                if (prior != null) {
                    SaveWithBackup(target, backup, ".active-version.json", prior, copied, existed);
                    SaveWithBackup(target, backup, ".updates/installer/plan.json", File.ReadAllText(Path.Combine(stage, ".install-version.json")), copied, existed);
                }
                string executable = Path.Combine(target, "Tradutor SL.exe");
                foreach (string link in new[] {Path.Combine(menu, "Tradutor SL.lnk"), createDesktop ? Path.Combine(desktop, "Tradutor SL.lnk") : null}) {
                    if (link == null) continue;
                    bool hadLink = File.Exists(link);
                    if (hadLink && !App.OwnShortcut(link, target)) throw new IOException("Já existe um atalho com esse nome para outro aplicativo: " + link);
                    App.Shortcut(link, executable, target); if (!hadLink) createdLinks.Add(link);
                }
                var record = new InstallRecord {Id = App.Id, Root = target, Version = BuildInfo.Version, Test = test,
                    Shortcuts = new[] {Path.Combine(menu, "Tradutor SL.lnk"), createDesktop ? Path.Combine(desktop, "Tradutor SL.lnk") : null}.Where(p => p != null).ToArray(),
                    RootFiles = files.Where(p => !p.Contains("/")).ToArray()};
                SaveWithBackup(target, backup, ".tradutor-install.json", App.Json.Serialize(record), copied, existed);
                if (!test) Register(target);
                success = true;
            }
            progress(100, "Instalação concluída. O ícone do Tradutor SL está pronto para usar.");
        } catch {
            foreach (string name in copied.AsEnumerable().Reverse()) {
                string destination = App.Inside(target, name);
                if (existed.Contains(name)) File.Copy(App.Inside(backup, name), destination, true);
                else if (File.Exists(destination)) File.Delete(destination);
            }
            foreach (string link in createdLinks) if (File.Exists(link)) File.Delete(link);
            if (!targetExisted && Directory.Exists(target)) App.DeleteTree(target);
            throw;
        } finally {
            if (Directory.Exists(stage)) App.DeleteTree(stage);
            if (success && Directory.Exists(backup)) App.DeleteTree(backup);
        }
    }
    private static void CopyWithBackup(string stage, string target, string backup, string name, List<string> copied, HashSet<string> existed) {
        Backup(target, backup, name, copied, existed);
        File.Copy(App.Inside(stage, name), App.Inside(target, name), true);
    }
    private static void Backup(string target, string backup, string name, List<string> copied, HashSet<string> existed) {
        string destination = App.Inside(target, name); Directory.CreateDirectory(Path.GetDirectoryName(destination));
        if (File.Exists(destination)) {
            string saved = App.Inside(backup, name); Directory.CreateDirectory(Path.GetDirectoryName(saved));
            File.Copy(destination, saved, true); existed.Add(name);
        }
        copied.Add(name);
    }
    private static void SaveWithBackup(string target, string backup, string name, string data, List<string> copied, HashSet<string> existed) {
        Backup(target, backup, name, copied, existed); File.WriteAllText(App.Inside(target, name), data, new UTF8Encoding(false));
    }
    private static void Register(string root) {
        using (var key = Registry.CurrentUser.CreateSubKey(App.RegistryPath)) {
            key.SetValue("DisplayName", "Tradutor SL"); key.SetValue("DisplayVersion", BuildInfo.Version);
            key.SetValue("Publisher", "lipedevpop"); key.SetValue("InstallLocation", root);
            key.SetValue("DisplayIcon", Path.Combine(root, "Tradutor SL.exe") + ",0");
            key.SetValue("UninstallString", App.Quote(Path.Combine(root, "Tradutor SL.exe")) + " --uninstall");
            key.SetValue("URLInfoAbout", "https://github.com/lipedevpop/Tradutor-SL");
            key.SetValue("NoModify", 1, RegistryValueKind.DWord); key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
        }
    }
}

internal sealed class SetupForm : Form {
    private TextBox path; private CheckBox desktop, launch; private Button install, close, browse;
    private ProgressBar progress; private Label status; private bool busy, done;
    internal SetupForm() {
        Text = "Instalar Tradutor SL"; ClientSize = new Size(620, 420); FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen; Font = new Font("Segoe UI", 10);
        BackColor = Color.FromArgb(250, 247, 242); Icon = System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        Image brand;
        using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("branding.png"))
            brand = new Bitmap(Image.FromStream(stream));
        Controls.Add(new PictureBox {Image = brand, SizeMode = PictureBoxSizeMode.Zoom, Location = new Point(28, 28), Size = new Size(72,72)});
        Controls.Add(new Label {Text = "Tradutor SL", Font = new Font("Segoe UI", 23, FontStyle.Bold), Location = new Point(116,27), Size = new Size(460,46)});
        Controls.Add(new Label {Text = "Conversas em outro idioma, mais simples.", Location = new Point(120,76), Size = new Size(450,27)});
        Controls.Add(new Label {Text = "O assistente instalará o aplicativo e seus componentes.\nUm atalho ficará disponível no menu Iniciar.", Location = new Point(28,125), Size = new Size(560,49)});
        Controls.Add(new Label {Text = "Pasta de instalação", Location = new Point(28,190), Size = new Size(400,25)});
        path = new TextBox {Text = Installer.DefaultPath(), Location = new Point(28,220), Size = new Size(445,28)}; Controls.Add(path);
        browse = new Button {Text = "Procurar…", Location = new Point(482,218), Size = new Size(108,31)}; Controls.Add(browse);
        browse.Click += (s,e) => {using (var dialog = new FolderBrowserDialog {SelectedPath = path.Text, Description = "Escolha uma pasta exclusiva para o Tradutor SL"}) if (dialog.ShowDialog() == DialogResult.OK) path.Text = dialog.SelectedPath;};
        desktop = new CheckBox {Text = "Criar ícone na área de trabalho", Checked = true, Location = new Point(28,264), Size = new Size(520,27)}; Controls.Add(desktop);
        launch = new CheckBox {Text = "Abrir o Tradutor SL ao concluir", Checked = true, Location = new Point(28,294), Size = new Size(520,27)}; Controls.Add(launch);
        progress = new ProgressBar {Location = new Point(28,330), Size = new Size(562,12)}; Controls.Add(progress);
        status = new Label {Text = "Versão " + BuildInfo.Version + " · Windows 64 bits", Location = new Point(28,355), Size = new Size(350,45)}; Controls.Add(status);
        install = new Button {Text = "Instalar", Location = new Point(382,364), Size = new Size(105,33), BackColor = Color.FromArgb(229,239,247)}; Controls.Add(install);
        close = new Button {Text = "Cancelar", Location = new Point(496,364), Size = new Size(94,33)}; Controls.Add(close);
        close.Click += (s,e) => Close(); install.Click += Install;
        FormClosing += (s,e) => {if (busy) e.Cancel = true;};
    }
    private async void Install(object sender, EventArgs args) {
        if (done) { if (launch.Checked) App.Launch(path.Text, new string[0]); Close(); return; }
        try {
            busy = true; install.Enabled = close.Enabled = browse.Enabled = path.Enabled = desktop.Enabled = launch.Enabled = false;
            string destination = path.Text; bool shortcut = desktop.Checked;
            var completion = new TaskCompletionSource<bool>();
            var worker = new System.Threading.Thread(() => {
                try {
                    Installer.Install(destination,
                        Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                        Environment.GetFolderPath(Environment.SpecialFolder.Programs), shortcut, false,
                        (amount,text) => BeginInvoke(new Action(() => {progress.Value = amount; status.Text = text;})));
                    completion.SetResult(true);
                } catch (Exception error) { completion.SetException(error); }
            });
            worker.SetApartmentState(System.Threading.ApartmentState.STA); worker.IsBackground = true; worker.Start();
            await completion.Task;
            done = true; install.Text = "Concluir"; launch.Enabled = true; close.Visible = false;
        } catch (Exception error) {
            MessageBox.Show(this, error.Message, "Não foi possível instalar", MessageBoxButtons.OK, MessageBoxIcon.Error);
            close.Enabled = browse.Enabled = path.Enabled = desktop.Enabled = launch.Enabled = true; status.Text = "A instalação não foi concluída.";
        } finally { busy = false; install.Enabled = true; }
    }
}
#endif
