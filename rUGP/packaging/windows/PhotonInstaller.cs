using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Win32;

// One executable per game; the release builder embeds that game's ZIP only.
class PhotonInstaller : Form {
    readonly string package, title, directory, exe;
    readonly TextBox path = new TextBox();
    readonly Label status = new Label();
    readonly Button install = new Button(), browse = new Button(), restore = new Button();
    readonly ProgressBar progress = new ProgressBar();
    bool busy;
    static string Quote(string s) { return "\"" + s.Replace("\"", "") + "\""; }
    static string Engine(string package, string action, string root, string session, Action<string> report) {
        var info = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell\\v1.0\\powershell.exe"));
        info.Arguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File " + Quote(Path.Combine(package,"Install-PhotonCN.ps1")) + " -Action " + action;
        if(action == "Install" || action == "Rollback") info.Arguments += " -Apply";
        if(root != null) info.Arguments += " -GameRoot " + Quote(root);
        if(session != null) info.Arguments += " -SessionRoot " + Quote(session);
        info.UseShellExecute=false;info.CreateNoWindow=true;info.RedirectStandardOutput=true;info.RedirectStandardError=true;
        info.StandardOutputEncoding=Encoding.UTF8;info.StandardErrorEncoding=Encoding.UTF8;
        info.EnvironmentVariables["PSModulePath"]=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),"WindowsPowerShell\\v1.0\\Modules")+";"+Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"WindowsPowerShell\\Modules");
        var output=new StringBuilder();var errors=new StringBuilder();
        using(var process=new Process()) {
            process.StartInfo=info;
            process.OutputDataReceived+=(s,e)=> { if(e.Data!=null) { lock(output) output.AppendLine(e.Data);if(report!=null) report(e.Data); } };
            process.ErrorDataReceived+=(s,e)=> { if(e.Data!=null) lock(errors) errors.AppendLine(e.Data); };
            process.Start();process.BeginOutputReadLine();process.BeginErrorReadLine();process.WaitForExit();
            var logs=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MuvLuvPhotonCN","logs");Directory.CreateDirectory(logs);
            var log=Path.Combine(logs,DateTime.UtcNow.ToString("yyyyMMddTHHmmssfff")+"-"+action+".txt");
            File.WriteAllText(log,output.ToString()+errors.ToString(),Encoding.UTF8);
            if(process.ExitCode!=0) throw new Exception(errors.Length>0?errors.ToString():"安装未完成，请重试。日志："+log);
        }
        return output.ToString();
    }
    PhotonInstaller(string content) {
        package=content;
        var doc=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(package,"package_manifest.20260910.json"),Encoding.UTF8));
        title=(string)doc["game_title"];directory=(string)doc["install_directory"];exe=(string)doc["exe"];
        Text=title+" 汉化补丁 · 2026.09.10";ClientSize=new Size(590,275);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;
        Font=new Font("Microsoft YaHei UI",10);BackColor=Color.FromArgb(248,249,251);
        var heading=new Label{Text=title+"\n汉化补丁 2026.09.10",Location=new Point(25,20),Size=new Size(535,58),Font=new Font(Font.FontFamily,15,FontStyle.Bold)};Controls.Add(heading);
        var label=new Label{Text="游戏目录",Location=new Point(25,92),Size=new Size(90,25)};Controls.Add(label);
        path.SetBounds(25,122,443,29);Controls.Add(path);
        browse.Text="选择…";browse.SetBounds(480,120,83,32);browse.Click+=(s,e)=>{using(var d=new FolderBrowserDialog()){d.Description="选择 "+title+" 的安装目录";if(Directory.Exists(path.Text))d.SelectedPath=path.Text;if(d.ShowDialog(this)==DialogResult.OK)path.Text=d.SelectedPath;}};Controls.Add(browse);
        status.SetBounds(25,163,538,27);status.Text="自动备份，安装完成即可进入游戏。";Controls.Add(status);
        progress.SetBounds(25,195,538,5);progress.Visible=false;progress.Style=ProgressBarStyle.Marquee;Controls.Add(progress);
        install.Text="安装汉化";install.SetBounds(430,218,133,37);install.BackColor=Color.FromArgb(37,99,235);install.ForeColor=Color.White;install.FlatStyle=FlatStyle.Flat;install.Click+=async(s,e)=>await Run("Install");Controls.Add(install);
        restore.Text="恢复安装前";restore.SetBounds(25,220,123,32);restore.Click+=async(s,e)=>await Run("Rollback");Controls.Add(restore);
        FormClosing+=(s,e)=>{if(busy)e.Cancel=true;};
        path.Text=FindGame();
        if(path.Text.Length==0)status.Text="请选择游戏目录，然后点击安装汉化。";
    }
    string FindGame() {
        var roots=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach(var hive in new[]{Registry.CurrentUser,Registry.LocalMachine}) foreach(var key in new[]{"Software\\Valve\\Steam","SOFTWARE\\WOW6432Node\\Valve\\Steam"}) using(var r=hive.OpenSubKey(key)) {
            if(r!=null)foreach(var v in new[]{"SteamPath","InstallPath"}){var value=r.GetValue(v) as string;if(!String.IsNullOrEmpty(value))roots.Add(value);}
        }
        roots.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),"Steam"));
        var libraries=new HashSet<string>(roots,StringComparer.OrdinalIgnoreCase);
        foreach(var root in roots) {var vdf=Path.Combine(root,"steamapps","libraryfolders.vdf");if(File.Exists(vdf))foreach(Match m in Regex.Matches(File.ReadAllText(vdf),"\"path\"\\s+\"([^\"]+)\""))libraries.Add(m.Groups[1].Value.Replace("\\\\","\\"));}
        foreach(var library in libraries){var game=Path.Combine(library,"steamapps","common",directory);if(File.Exists(Path.Combine(game,exe)))return game;}
        return "";
    }
    async Task Run(string action) {
        if(!File.Exists(Path.Combine(path.Text,exe))){MessageBox.Show(this,"请选择 "+title+" 的游戏目录。","未找到游戏");return;}
        busy=true;install.Enabled=browse.Enabled=restore.Enabled=path.Enabled=false;progress.Visible=true;status.Text=action=="Install"?"正在安装，请稍候…":"正在恢复，请稍候…";
        var root=path.Text;
        try {
            await Task.Run(()=>Engine(package,action,root,null,line=> { if(!IsDisposed && line.Length>0 && !line.TrimStart().StartsWith("\"") && !line.StartsWith("{") && !line.StartsWith("}"))BeginInvoke((Action)(()=>{status.Text=line.Length>65?line.Substring(0,65)+"…":line;})); }));
            status.Text=action=="Install"?"安装完成，可以进入游戏了。":"已恢复安装前的文件。";
            MessageBox.Show(this,status.Text,"完成",MessageBoxButtons.OK,MessageBoxIcon.Information);
        } catch(Exception e) {
            status.Text="未完成：请按提示处理后重试。";
            MessageBox.Show(this,e.Message,"安装提示",MessageBoxButtons.OK,MessageBoxIcon.Information);
        } finally {busy=false;install.Enabled=browse.Enabled=restore.Enabled=path.Enabled=true;progress.Visible=false;}
    }
    static string Extract() {
        string identity;
        using(var input=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")) using(var sha=SHA256.Create()) {
            if(input==null)throw new Exception("补丁内容缺失，请重新下载。");
            identity=BitConverter.ToString(sha.ComputeHash(input)).Replace("-","");
        }
        var root=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MuvLuvPhotonCN","packages",identity);
        if(File.Exists(Path.Combine(root,".complete")))return root;
        if(Directory.Exists(root))root+="-"+Guid.NewGuid().ToString("N");
        Directory.CreateDirectory(root);
        using(var input=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")) {
            if(input==null)throw new Exception("补丁内容缺失，请重新下载。");
            using(var zip=new ZipArchive(input,ZipArchiveMode.Read)) foreach(var entry in zip.Entries) {
                var dest=Path.GetFullPath(Path.Combine(root,entry.FullName));
                if(!dest.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new Exception("补丁路径无效。");
                if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(dest);continue;}
                Directory.CreateDirectory(Path.GetDirectoryName(dest));entry.ExtractToFile(dest,false);
            }
        }
        File.WriteAllText(Path.Combine(root,".complete"),identity,Encoding.ASCII);
        return root;
    }
    [STAThread] static int Main(string[] args) {
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        try {
            string content;
            if(args.Length==2 && args[0]=="--extract") { content=Extract(); File.WriteAllText(args[1],content,Encoding.UTF8); return 0; }
            content=Extract();
            if(args.Length==2 && args[0]=="--inspect") {
                using(var form=new PhotonInstaller(content)) {
                    File.WriteAllText(args[1],new JavaScriptSerializer().Serialize(new {title=form.Text,detectedRoot=form.path.Text,controls=form.Controls.Count,package=content}),Encoding.UTF8);
                }
                return 0;
            }
            Application.Run(new PhotonInstaller(content));return 0;
        } catch(Exception e){if(args.Length==2)File.WriteAllText(args[1],e.ToString(),Encoding.UTF8);else MessageBox.Show(e.Message,"补丁无法启动");return 1;}
    }
}
