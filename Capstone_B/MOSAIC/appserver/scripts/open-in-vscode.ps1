param(
    [Parameter(Mandatory = $true)]
    [string]$ZipPath,

    [Parameter(Mandatory = $true)]
    [string]$ExtractPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ZipPath)) {
    Write-Error "Zip file not found: $ZipPath"
    exit 1
}

if (Test-Path -LiteralPath $ExtractPath) {
    Remove-Item -LiteralPath $ExtractPath -Recurse -Force
}

New-Item -ItemType Directory -Path $ExtractPath -Force | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractPath -Force

$projectRoot = $ExtractPath
$frontendPath = Join-Path $projectRoot "frontend"
$backendPath = Join-Path $projectRoot "backend"

if (-not (Test-Path -LiteralPath $frontendPath)) {
    $childDirs = Get-ChildItem -LiteralPath $ExtractPath -Directory
    foreach ($dir in $childDirs) {
        $candidateFrontend = Join-Path $dir.FullName "frontend"
        $candidateBackend = Join-Path $dir.FullName "backend"
        if ((Test-Path -LiteralPath $candidateFrontend) -and (Test-Path -LiteralPath $candidateBackend)) {
            $projectRoot = $dir.FullName
            $frontendPath = $candidateFrontend
            $backendPath = $candidateBackend
            break
        }
    }
}

if (-not (Test-Path -LiteralPath $frontendPath)) {
    Write-Error "frontend folder not found under $ExtractPath"
    exit 1
}

if (-not (Test-Path -LiteralPath $backendPath)) {
    Write-Error "backend folder not found under $ExtractPath"
    exit 1
}

$codeCmd = Get-Command code -ErrorAction SilentlyContinue
if ($codeCmd) {
    Start-Process -FilePath $codeCmd.Source -ArgumentList "`"$projectRoot`""
} else {
    Write-Warning "VS Code CLI 'code' was not found in PATH. Open the folder manually: $projectRoot"
}

$frontendCommand = "Set-Location -LiteralPath '$frontendPath'; npm run dev"
$backendCommand = "Set-Location -LiteralPath '$backendPath'; python app.py"

Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $frontendCommand
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $backendCommand

Write-Output "Opened $projectRoot in VS Code and started frontend/backend terminals."
