# Rust Parser Build Script
# Bu script, Rust parser'i derleyip Python .venv'e yukler.
#
# Kullanim:
#   .\scripts\build_rust.ps1
#
# Gereksinimler:
#   - Rust (rustc, cargo)
#   - maturin (uv pip install maturin)
#   - Python .venv

$ErrorActionPreference = "Stop"

Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  Rust Parser Build Script" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

# Proje root'unu bul
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $projectRoot) {
    $projectRoot = (Get-Location).Path
}

$rustDir = Join-Path $projectRoot "rust_parser"
$venvDir = Join-Path $projectRoot ".venv"

# Kontroller
Write-Host "[1/4] Kontroller yapiliyor..." -ForegroundColor Yellow

if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    Write-Host "  [HATA] Rust bulunamadi! https://rustup.rs adresinden yukleyin." -ForegroundColor Red
    exit 1
}
$rustVersion = rustc --version
Write-Host "  [OK] Rust: $rustVersion" -ForegroundColor Green

if (-not (Test-Path $venvDir)) {
    Write-Host "  [HATA] .venv bulunamadi! Once 'uv venv' ile olusturun." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] .venv mevcut" -ForegroundColor Green

# Maturin kontrol
$maturinPath = Join-Path $venvDir "Scripts\maturin.exe"
if (-not (Test-Path $maturinPath)) {
    Write-Host "  [INFO] maturin yukleniyor..." -ForegroundColor Yellow
    & (Join-Path $venvDir "Scripts\python.exe") -m pip install maturin
}
Write-Host "  [OK] maturin mevcut" -ForegroundColor Green

# Rust build
Write-Host "`n[2/4] Rust parser derleniyor (release modu)..." -ForegroundColor Yellow
Push-Location $rustDir
try {
    cargo build --release 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [HATA] Rust derleme basarisiz!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] Rust parser derlendi" -ForegroundColor Green
} finally {
    Pop-Location
}

# Maturin ile Python'a yukle
Write-Host "`n[3/4] Python'a yukleniyor (maturin develop)..." -ForegroundColor Yellow
Push-Location $rustDir
try {
    & $maturinPath develop --release 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [HATA] maturin develop basarisiz!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] rust_parser Python modulu yuklendi" -ForegroundColor Green
} finally {
    Pop-Location
}

# Dogrulama
Write-Host "`n[4/4] Dogrulama..." -ForegroundColor Yellow
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
& $pythonExe -c "import rust_parser; print(f'  [OK] rust_parser yuklu, {len(rust_parser.supported_extensions())} format destekleniyor')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [UYARI] rust_parser import edilemedi. 'maturin develop' tekrar deneyin." -ForegroundColor Yellow
} else {
    Write-Host "" 
}

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Build tamamlandi!" -ForegroundColor Green
Write-Host "======================================`n" -ForegroundColor Cyan
