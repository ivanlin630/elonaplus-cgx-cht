# Build Elona+ Custom-GX from src\ with the HSP 3.4 compiler DLL.
# Must run under 32-bit PowerShell (hspcmp.dll is 32-bit):
#   C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -File A:\GDS\elona-cgx\build.ps1
param([string]$Src = "$PSScriptRoot\src", [string]$Hsp = "$PSScriptRoot\hsp34")

if ([IntPtr]::Size -ne 4) { Write-Error "Run under 32-bit PowerShell (SysWOW64)."; exit 2 }
# Which source tree to build: build-src.txt (one line, path relative to this folder) overrides the default.
$pick = Join-Path $PSScriptRoot 'build-src.txt'
if (Test-Path $pick) { $Src = Join-Path $PSScriptRoot ((Get-Content $pick -TotalCount 1).Trim()) }
Write-Host "building $Src"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class Hsc {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool SetDllDirectory(string p);
  [DllImport("hspcmp.dll", EntryPoint="_hsc_ini@16",     CallingConvention=CallingConvention.StdCall)] public static extern int ini(int bm, byte[] p1, int p2, int p3);
  [DllImport("hspcmp.dll", EntryPoint="_hsc_objname@16", CallingConvention=CallingConvention.StdCall)] public static extern int objname(int bm, byte[] p1, int p2, int p3);
  [DllImport("hspcmp.dll", EntryPoint="_hsc_compath@16", CallingConvention=CallingConvention.StdCall)] public static extern int compath(int bm, byte[] p1, int p2, int p3);
  [DllImport("hspcmp.dll", EntryPoint="_hsc_comp@16",    CallingConvention=CallingConvention.StdCall)] public static extern int comp(int p1, int p2, int p3, int p4);
  [DllImport("hspcmp.dll", EntryPoint="_hsc_getmes@16",  CallingConvention=CallingConvention.StdCall)] public static extern int getmes(byte[] buf, int p2, int p3, int p4);
  [DllImport("hspcmp.dll", EntryPoint="_hsc3_messize@16",CallingConvention=CallingConvention.StdCall)] public static extern int messize(ref int sz, int p2, int p3, int p4);
  [DllImport("hspcmp.dll", EntryPoint="_hsc3_make@16",   CallingConvention=CallingConvention.StdCall)] public static extern int make(int bm, byte[] p1, int p2, int p3);
}
"@

$sj = [System.Text.Encoding]::GetEncoding(932)
function Z([string]$s) { $b = $sj.GetBytes($s); $z = New-Object byte[] ($b.Length + 1); [Array]::Copy($b, $z, $b.Length); return $z }
function Mes() {
  $n = 0; [void][Hsc]::messize([ref]$n, 0, 0, 0)
  $buf = New-Object byte[] ([Math]::Max($n + 16, 65536)); [void][Hsc]::getmes($buf, 0, 0, 0)
  $end = [Array]::IndexOf($buf, [byte]0); if ($end -lt 0) { $end = $buf.Length }
  return $sj.GetString($buf, 0, $end)
}

[void][Hsc]::SetDllDirectory($Hsp)
Set-Location $Src
[Environment]::CurrentDirectory = (Resolve-Path $Src).Path   # native DLL uses the process cwd
[void][Hsc]::ini(0, (Z "main.hsp"), 0, 0)
[void][Hsc]::objname(0, (Z "start.ax"), 0, 0)
[void][Hsc]::compath(0, (Z "$Hsp\common\"), 0, 0)
$rc = [Hsc]::comp(0, 4, 0, 0)          # no debug info; +4 = honour #pack/#packopt
$m = Mes
$m | Out-File -Encoding utf8 "$PSScriptRoot\build-compile.log"
if ($rc -ne 0) { Write-Host "COMPILE FAILED rc=$rc"; ($m -split "`n" | Select-Object -Last 25) -join "`n"; exit 1 }
Write-Host "compile ok"

$rc = [Hsc]::make(0, (Z "$Hsp\"), 0, 0)
$m2 = Mes
$m2 | Out-File -Encoding utf8 "$PSScriptRoot\build-make.log"
if ($rc -ne 0) { Write-Host "MAKE FAILED rc=$rc"; ($m2 -split "`n" | Select-Object -Last 25) -join "`n"; exit 1 }
Get-ChildItem $Src -Filter *.exe | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name, Length, LastWriteTime | Format-Table -AutoSize | Out-String
