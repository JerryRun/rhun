# Test the production state decoder without focusing windows or changing IME state.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$sourcePath = Join-Path $PSScriptRoot '../../runtime/windows/wsl-window.ps1'
$source = [IO.File]::ReadAllText((Resolve-Path $sourcePath).ProviderPath)
$begin = $source.IndexOf("using System;")
$end = $source.IndexOf("'@", $begin)
if ($begin -lt 0 -or $end -lt 0) { throw 'Production C# helper not found' }
Add-Type -TypeDefinition $source.Substring($begin, $end - $begin)
$cases = @(
    @(4, 1, 1024, 1), @(4, 0, 1024, 0),
    @(4, 1, 1025, 1), @(4, 0, 1025, 0),
    @(4, 1, 1, 1), @(4, 1, 0, 0), @(4, 0, 0, 0),
    @(4, -1, 1, -1), @(4, 1, -1, -1), @(4, 0, -1, 0),
    @(9, -1, -1, 0), @(0, 1, 1, -1)
)
foreach ($case in $cases) {
    $actual = [RhunWindowArea]::DecodeHostImeState($case[0], $case[1], $case[2])
    if ($actual -ne $case[3]) { throw "Unexpected state for $case : $actual" }
}
Write-Output ('PASS: production host IME decoder, ' + $cases.Count + ' cases')
