[CmdletBinding()]
param(
    [ValidateSet('VerifyPackage', 'Status', 'Install')]
    [string]$Action = 'Status',
    [switch]$Apply,
    [string]$GameRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$PackageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$ManifestPath = Join-Path $PackageRoot 'package_manifest.20260910.json'
$SealPath = Join-Path $PackageRoot 'package_seal.20260910.json'
$InstallerMutex = $null
$InstallerMutexHeld = $false
$WritesStarted = $false

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Get-Sha256 {
    param([string]$Path)
    $stream=[IO.File]::Open($Path,'Open','Read','Read')
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','') }
    finally { $sha.Dispose();$stream.Dispose() }
}

function Get-StreamRangeSha256 {
    param(
        [Parameter(Mandatory = $true)][IO.Stream]$Stream,
        [Parameter(Mandatory = $true)][int64]$Offset,
        [Parameter(Mandatory = $true)][int64]$Length
    )
    Assert-True ($Offset -ge 0 -and $Length -ge 0 -and ($Offset + $Length) -le $Stream.Length) '区段哈希范围越界'
    $Stream.Position = $Offset
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $buffer = New-Object byte[] (4MB)
        $remaining = $Length
        while ($remaining -gt 0) {
            $wanted = [int][Math]::Min([int64]$buffer.Length, $remaining)
            $read = $Stream.Read($buffer, 0, $wanted)
            Assert-True ($read -gt 0) '读取区段哈希时意外到达文件末尾'
            [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
            $remaining -= $read
        }
        $empty = New-Object byte[] 0
        [void]$sha.TransformFinalBlock($empty, 0, 0)
        return ([BitConverter]::ToString($sha.Hash)).Replace('-', '').ToUpperInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-SafePackagePath {
    param([Parameter(Mandatory = $true)][string]$Relative)
    Assert-True (-not [IO.Path]::IsPathRooted($Relative)) "包内路径不能是绝对路径：$Relative"
    $parts = @($Relative -split '[\\/]')
    Assert-True ($parts.Count -gt 0 -and -not ($parts | Where-Object { $_ -in @('', '.', '..') })) "包内路径不安全：$Relative"
    $full = [IO.Path]::GetFullPath((Join-Path $PackageRoot $Relative))
    $prefix = $PackageRoot.TrimEnd('\') + '\'
    Assert-True ($full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) "包内路径越界：$Relative"
    return $full
}

function Get-SafeTargetPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Relative
    )
    Assert-True (-not [IO.Path]::IsPathRooted($Relative)) "目标路径不能是绝对路径：$Relative"
    $parts = @($Relative -split '[\\/]')
    Assert-True ($parts.Count -gt 0 -and -not ($parts | Where-Object { $_ -in @('', '.', '..') })) "目标路径不安全：$Relative"
    $rootFull = [IO.Path]::GetFullPath($Root)
    $full = [IO.Path]::GetFullPath((Join-Path $rootFull $Relative))
    $prefix = $rootFull.TrimEnd('\') + '\'
    Assert-True ($full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) "目标路径越界：$Relative"
    return $full
}

function Read-PackageDocuments {
    Assert-True (Test-Path -LiteralPath $ManifestPath -PathType Leaf) '缺少 package_manifest.20260910.json'
    Assert-True (Test-Path -LiteralPath $SealPath -PathType Leaf) '缺少 package_seal.20260910.json'
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $seal = Get-Content -LiteralPath $SealPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($manifest.status -eq 'PASS_FULL_CLEAN_20260910_PACKAGE_SEALED') "补丁清单未通过：$($manifest.status)"
    Assert-True ($seal.package_id -eq $manifest.package_id -and $seal.status -eq 'PASS') '补丁封条无效'
    Assert-True ((Get-Sha256 $ManifestPath) -eq [string]$seal.manifest.sha256) '补丁清单哈希不符'
    Assert-True ((Get-Sha256 $PSCommandPath) -eq [string]$seal.installer.sha256) '安装程序哈希不符'
    return @{ Manifest = $manifest; Seal = $seal }
}

function Show-PackageProgress {
    param(
        [Parameter(Mandatory = $true)][int]$Checked,
        [Parameter(Mandatory = $true)][int]$Total,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $percent = [int][Math]::Floor(($Checked * 100.0) / [Math]::Max(1, $Total))
    Write-Progress -Activity '正在准备安装' -Status ("{0}/{1}  {2}%  {3}" -f $Checked, $Total, $percent, $Name) -PercentComplete $percent
    if ($Checked -eq 1 -or $Checked -eq $Total -or ($Checked % 50) -eq 0) {
        Write-Host ("校验进度：{0}/{1}（{2}%）" -f $Checked, $Total, $percent)
    }
}

function Test-PackagePayload {
    param([Parameter(Mandatory = $true)]$Manifest)
    $total = @($Manifest.archives).Count + @($Manifest.files).Count
    $checked = 0
    Write-Host ("正在准备安装，共 {0} 个文件；较慢的电脑可能需要几分钟，请勿关闭窗口。" -f $total)
    $failures = [Collections.Generic.List[string]]::new()
    $expected = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($archive in @($Manifest.archives)) {
        $checked += 1
        Show-PackageProgress $checked $total ([string]$archive.patch.path)
        $path = Get-SafePackagePath ([string]$archive.patch.path)
        [void]$expected.Add([IO.Path]::GetFullPath($path))
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $failures.Add("缺少差分文件：$($archive.patch.path)")
            continue
        }
        $item = Get-Item -LiteralPath $path
        if ([int64]$item.Length -ne [int64]$archive.patch.bytes -or (Get-Sha256 $path) -ne [string]$archive.patch.sha256) {
            $failures.Add("差分文件不一致：$($archive.patch.path)")
        }
    }
    foreach ($row in @($Manifest.files)) {
        $checked += 1
        Show-PackageProgress $checked $total ([string]$row.payload.path)
        $path = Get-SafePackagePath ([string]$row.payload.path)
        [void]$expected.Add([IO.Path]::GetFullPath($path))
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $failures.Add("缺少补丁文件：$($row.payload.path)")
            continue
        }
        $item = Get-Item -LiteralPath $path
        if ([int64]$item.Length -ne [int64]$row.payload.bytes -or (Get-Sha256 $path) -ne [string]$row.payload.sha256) {
            $failures.Add("补丁文件不一致：$($row.payload.path)")
        }
    }
    Write-Progress -Activity '正在准备安装' -Completed
    Write-Host '补丁包完整性校验完成，正在准备游戏……'
    $actual = [Collections.Generic.List[string]]::new()
    foreach ($leaf in @('patches', 'files')) {
        $dir = Join-Path $PackageRoot $leaf
        if (Test-Path -LiteralPath $dir -PathType Container) {
            foreach ($file in Get-ChildItem -LiteralPath $dir -Recurse -File -Force) { $actual.Add($file.FullName) }
        }
    }
    foreach ($path in $actual) {
        if (-not $expected.Contains([IO.Path]::GetFullPath($path))) { $failures.Add("包内存在未登记文件：$path") }
    }
    Assert-True ($actual.Count -eq [int]$Manifest.counts.package_payload_files) "包内文件数量不符：$($actual.Count)"
    Assert-True ($failures.Count -eq 0) ("补丁包校验失败：`n" + ($failures -join "`n"))
    return [ordered]@{
        status = 'PASS_PACKAGE_BYTES_EXACT_20260910'
        game = [string]$Manifest.game
        package_payload_files = $actual.Count
        patch_bytes = [int64]$Manifest.counts.patch_bytes
        final_files = [int]$Manifest.counts.final_files
    }
}

function Get-SteamLibraryRoots {
    $roots = [Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        (Join-Path ${env:ProgramFiles(x86)} 'Steam'),
        (Join-Path $env:ProgramFiles 'Steam')
    )) {
        if (-not [string]::IsNullOrWhiteSpace([string]$candidate)) { $roots.Add([string]$candidate) }
    }
    foreach ($registryPath in @(
        'Registry::HKEY_CURRENT_USER\Software\Valve\Steam',
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Valve\Steam',
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Valve\Steam'
    )) {
        try {
            $properties = Get-ItemProperty -LiteralPath $registryPath -ErrorAction Stop
            foreach ($name in @('SteamPath', 'InstallPath')) {
                $value = $properties.$name
                if ($value) { $roots.Add([string]$value) }
            }
        } catch { }
    }
    foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
        if ($drive.Root) {
            try { $roots.Add([IO.Path]::Combine([string]$drive.Root, 'Steam')) } catch { }
        }
    }
    $expanded = [Collections.Generic.List[string]]::new()
    foreach ($root in @($roots | Sort-Object -Unique)) {
        if (-not $root) { continue }
        $expanded.Add([string]$root)
        $vdf = Join-Path ([string]$root) 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf -PathType Leaf) {
            $text = Get-Content -LiteralPath $vdf -Raw -ErrorAction SilentlyContinue
            foreach ($match in [regex]::Matches([string]$text, '"path"\s+"([^"]+)"')) {
                $expanded.Add(($match.Groups[1].Value -replace '\\\\', '\'))
            }
        }
    }
    return @($expanded | Where-Object { $_ } | Sort-Object -Unique)
}

function Resolve-GameRoot {
    param([Parameter(Mandatory = $true)]$Manifest)
    $candidates = [Collections.Generic.List[string]]::new()
    if (-not [string]::IsNullOrWhiteSpace($GameRoot)) {
        $candidates.Add($GameRoot)
    } else {
        foreach ($library in Get-SteamLibraryRoots) {
            try {
                $candidates.Add([IO.Path]::Combine(
                    [string]$library,
                    'steamapps',
                    'common',
                    [string]$Manifest.install_directory
                ))
            } catch { }
        }
    }
    $found = [Collections.Generic.List[string]]::new()
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Container -ErrorAction SilentlyContinue)) { continue }
        try { $resolved = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path) } catch { continue }
        $exe = Get-SafeTargetPath $resolved ([string]$Manifest.exe)
        if ((Test-Path -LiteralPath $exe -PathType Leaf) -and $seen.Add($resolved)) { $found.Add($resolved) }
    }
    Assert-True ($found.Count -gt 0) "没有找到 $($Manifest.game_title)。请先安装 Steam 纯净版，或用 -GameRoot 指定目录。"
    Assert-True ($found.Count -eq 1) "找到了多个游戏目录，请用 -GameRoot 明确指定要安装的目录。"
    return $found[0]
}

function Assert-GameClosed {
    param([Parameter(Mandatory = $true)]$Manifest)
    $running = @(Get-Process -Name ([string]$Manifest.process_name) -ErrorAction SilentlyContinue)
    Assert-True ($running.Count -eq 0) "请先关闭 $($Manifest.game_title)，再安装或卸载。"
}

function Get-ArchiveRangeMatch {
    param([string]$Path, $Archive)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return @{before=$false;after=$false} }
    $size = [int64](Get-Item -LiteralPath $Path).Length
    $afterOk = $size -eq [int64]$Archive.after.bytes
    $beforeOk = $false
    $stream = [IO.File]::Open($Path, 'Open', 'Read', 'Read')
    try {
        $cache = @{}
        foreach ($variant in @($Archive.accepted_bases)) {
            if ($size -ne [int64]$variant.bytes) { continue }
            $ok = $true
            for ($i=0; $i -lt @($Archive.segments).Count; $i++) {
                $seg=$Archive.segments[$i]; $original=$variant.ranges[$i]
                $key="$($seg.offset):$($original.length)"
                if (-not $cache.ContainsKey($key)) { $cache[$key]=Get-StreamRangeSha256 $stream $seg.offset $original.length }
                if ($cache[$key] -ne [string]$original.sha256) { $ok=$false;break }
            }
            if ($ok) { $beforeOk=$true;break }
        }
        if ($afterOk) {
            foreach ($seg in @($Archive.segments)) {
                $key="$($seg.offset):$($seg.length)"
                if (-not $cache.ContainsKey($key)) { $cache[$key]=Get-StreamRangeSha256 $stream $seg.offset $seg.length }
                if ($cache[$key] -ne [string]$seg.sha256) { $afterOk=$false;break }
            }
        }
    } finally { $stream.Dispose() }
    return @{before=$beforeOk;after=$afterOk}
}

function Test-RootState {
    param($Manifest,[string]$Root)
    $allBefore=$true;$allAfter=$true
    $mismatches=[Collections.Generic.List[string]]::new()
    foreach ($archive in @($Manifest.archives)) {
        $match=Get-ArchiveRangeMatch (Get-SafeTargetPath $Root $archive.target) $archive
        if (-not $match.before -and -not $match.after) { $allBefore=$false;$mismatches.Add("游戏数据版本不匹配：$($archive.target)") }
        if (-not $match.after) { $allAfter=$false }
    }
    foreach ($row in @($Manifest.files)) {
        $target=Get-SafeTargetPath $Root $row.target
        $exists=Test-Path -LiteralPath $target -PathType Leaf
        $hash=if($exists){Get-Sha256 $target}else{''}
        $after=$exists -and $hash -eq [string]$row.payload.sha256
        if (-not $after) { $allAfter=$false }
        if ($row.category -eq 'asset') { continue }
        $known=$after
        foreach ($candidate in @($row.accepted_bases)) {
            if ((-not $exists -and -not $candidate.exists) -or ($exists -and $candidate.exists -and $hash -eq [string]$candidate.sha256)) { $known=$true }
        }
        if (-not $known) { $allBefore=$false;$mismatches.Add("游戏程序版本不匹配：$($row.target)") }
    }
    $asset=Get-SafeTargetPath $Root $Manifest.asset_root
    if (Test-Path -LiteralPath $asset) {
        # Every required asset was authenticated above; extra files are untouched.
    } else { $allAfter=$false }
    $status=if($allAfter){'INSTALLED_20260910_EXACT'}elseif($allBefore){'CLEAN_STEAM_SUPPORTED'}else{'UNSUPPORTED_OR_PARTIAL_STATE'}
    return @{status=$status;game=$Manifest.game;root=$Root;mismatches=@($mismatches)}
}

function Copy-ExactBytes {
    param(
        [Parameter(Mandatory = $true)][IO.Stream]$InputStream,
        [Parameter(Mandatory = $true)][IO.Stream]$OutputStream,
        [Parameter(Mandatory = $true)][int64]$Length
    )
    $remaining = $Length
    $buffer = New-Object byte[] (4MB)
    while ($remaining -gt 0) {
        $wanted = [int][Math]::Min([int64]$buffer.Length, $remaining)
        $read = $InputStream.Read($buffer, 0, $wanted)
        Assert-True ($read -gt 0) '读取差分或备份数据时意外到达文件末尾'
        $OutputStream.Write($buffer, 0, $read)
        $remaining -= $read
    }
}

function Apply-ArchivePatches {
    param([Parameter(Mandatory = $true)]$Manifest, [Parameter(Mandatory = $true)][string]$Root)
    foreach ($archive in @($Manifest.archives)) {
        Write-Host "正在写入完整汉化数据：$($archive.target)"
        $targetPath = Get-SafeTargetPath $Root ([string]$archive.target)
        $patchPath = Get-SafePackagePath ([string]$archive.patch.path)
        $target = [IO.File]::Open($targetPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        $patch = [IO.File]::Open($patchPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
        try {
            foreach ($segment in @($archive.segments)) {
                $target.Position = [int64]$segment.offset
                $patch.Position = [int64]$segment.patch_offset
                Copy-ExactBytes $patch $target ([int64]$segment.length)
            }
            $target.SetLength([int64]$archive.after.bytes)
            $target.Flush($true)
        } finally {
            $patch.Dispose()
            $target.Dispose()
        }
    }
}

function Install-PackageFiles {
    param([Parameter(Mandatory = $true)]$Manifest, [Parameter(Mandatory = $true)][string]$Root)
    foreach ($row in @($Manifest.files)) {
        $target = Get-SafeTargetPath $Root ([string]$row.target)
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath (Get-SafePackagePath ([string]$row.payload.path)) -Destination $target -Force
    }
}

function Assert-NoLinks {
    param([string]$Root)
    $dir=Get-Item -LiteralPath $Root
    while ($null -ne $dir) {
        Assert-True (-not ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint)) '游戏目录不能通过链接或联接访问'
        $dir=$dir.Parent
    }
    foreach ($entry in Get-ChildItem -LiteralPath $Root -Recurse -Force) {
        Assert-True (-not ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) '游戏目录含有链接，请使用真实安装目录'
    }
}
function Assert-SteamLanguage {
    param($Manifest,[string]$Root)
    $steamapps=Split-Path -Parent (Split-Path -Parent $Root)
    $acf=Join-Path $steamapps ("appmanifest_"+$Manifest.appid+".acf")
    Assert-True (Test-Path -LiteralPath $acf -PathType Leaf) '没有找到该游戏的 Steam 安装信息，请选择 Steam 游戏目录。'
    $text=Get-Content -LiteralPath $acf -Raw -Encoding UTF8
    if (-not ('PhotonSteamKeyValues' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Text;
public sealed class PhotonSteamKeyValues {
    string input;int position;
    PhotonSteamKeyValues(string value){input=value;}
    void Space(){
        while(position<input.Length){
            if(Char.IsWhiteSpace(input[position])){position++;continue;}
            if(position+1<input.Length && input[position]=='/' && input[position+1]=='/'){
                position+=2;while(position<input.Length && input[position]!='\n')position++;continue;
            }
            break;
        }
    }
    string Quoted(){
        Space();if(position>=input.Length || input[position++]!='"')throw new FormatException("Invalid Steam manifest string");
        var value=new StringBuilder();
        while(position<input.Length){
            char c=input[position++];if(c=='"')return value.ToString();
            if(c=='\\'){
                if(position>=input.Length)throw new FormatException("Truncated Steam escape");
                c=input[position++];
                if(c=='n')c='\n';else if(c=='r')c='\r';else if(c=='t')c='\t';
                else if(c!='\\' && c!='"')throw new FormatException("Unknown Steam escape");
            }
            value.Append(c);
        }
        throw new FormatException("Unterminated Steam string");
    }
    Dictionary<string,object> Object(bool nested,int depth){
        if(depth>32)throw new FormatException("Steam nesting exceeds limit");
        var value=new Dictionary<string,object>(StringComparer.OrdinalIgnoreCase);
        while(true){
            Space();if(position==input.Length){if(nested)throw new FormatException("Unclosed Steam object");return value;}
            if(input[position]=='}'){if(!nested)throw new FormatException("Unexpected closing brace");position++;return value;}
            string key=Quoted();Space();object item;
            if(position<input.Length && input[position]=='{'){position++;item=Object(true,depth+1);}else item=Quoted();
            if(value.ContainsKey(key))throw new FormatException("Duplicate Steam field: "+key);
            value.Add(key,item);
        }
    }
    public static void Validate(string text,string appid){
        var parser=new PhotonSteamKeyValues(text);var root=parser.Object(false,0);
        if(root.Count!=1 || !root.ContainsKey("AppState"))throw new FormatException("Missing Steam AppState");
        var state=root["AppState"] as Dictionary<string,object>;
        if(state==null || !state.ContainsKey("appid") || !appid.Equals(state["appid"]))throw new FormatException("Steam appid mismatch");
        foreach(string key in new[]{"UserConfig","MountedConfig"}){
            object item;if(!state.TryGetValue(key,out item))throw new FormatException("Missing Steam "+key);
            var config=item as Dictionary<string,object>;
            if(config==null || !config.ContainsKey("language"))throw new FormatException("Steam language is missing");
            var language=config["language"] as string;
            if(language==null || !String.Equals("english",language.Trim(),StringComparison.OrdinalIgnoreCase))throw new FormatException("Steam language is not English");
        }
    }
}
'@
    }
    try { [PhotonSteamKeyValues]::Validate($text,[string]$Manifest.appid) }
    catch { throw 'Steam 安装信息不匹配。请在游戏属性中把语言设为 English，等待下载完成后重试。' }
    return @{path=$acf;sha256=(Get-Sha256 $acf)}
}

try {
    $documents = Read-PackageDocuments
    $manifest = $documents.Manifest
    if ($Action -eq 'VerifyPackage') {
        Test-PackagePayload $manifest | ConvertTo-Json -Depth 8
        exit 0
    }
    $root = Resolve-GameRoot $manifest
    if ($Action -eq 'Status') {
        $state = Test-RootState $manifest $root
        $state | ConvertTo-Json -Depth 8
        exit $(if ($state.status -eq 'INSTALLED_20260910_EXACT') { 0 } else { 2 })
    }
    Assert-True $Apply '请双击补丁程序，点击安装汉化。'
    $InstallerMutex = [Threading.Mutex]::new($false, 'Local\MuvLuvPhotonCNInstaller')
    try { $InstallerMutexHeld = $InstallerMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $InstallerMutexHeld = $true }
    Assert-True $InstallerMutexHeld '另一个补丁正在安装，请等它完成。'
    Assert-GameClosed $manifest
    Assert-NoLinks $root
    [void](Test-PackagePayload $manifest)
    $locale = Assert-SteamLanguage $manifest $root
    $before = Test-RootState $manifest $root
    if ($before.status -eq 'INSTALLED_20260910_EXACT') {
        Write-Host '已经安装此版本，可以进入游戏。'
        exit 0
    }
    Assert-True ($before.status -eq 'CLEAN_STEAM_SUPPORTED') ("当前游戏文件不匹配，请通过 Steam 重新下载游戏后安装。`n" + ($before.mismatches -join "`n"))
    Assert-True ((Get-Sha256 $locale.path) -eq $locale.sha256) 'Steam 改变了游戏配置，请重试。'
    Assert-GameClosed $manifest
    $WritesStarted = $true
    Apply-ArchivePatches $manifest $root
    Install-PackageFiles $manifest $root
    $after = Test-RootState $manifest $root
    Assert-True ($after.status -eq 'INSTALLED_20260910_EXACT') '安装后文件核对失败'
    [ordered]@{ status='PASS_INSTALLED_NO_BACKUP';game=$manifest.game;root=$root } | ConvertTo-Json -Depth 8
    exit 0
} catch {
    $message = $_.Exception.Message
    if ($WritesStarted) { $message = "安装未完成。本补丁不备份或回滚；请通过 Steam 重新下载游戏后再安装。`n" + $message }
    [Console]::Error.WriteLine($message)
    exit 1
} finally {
    if ($InstallerMutexHeld) { $InstallerMutex.ReleaseMutex() }
    if ($null -ne $InstallerMutex) { $InstallerMutex.Dispose() }
}
