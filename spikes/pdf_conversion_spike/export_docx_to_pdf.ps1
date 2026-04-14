param(
    [Parameter(Mandatory = $true)]
    [string]$InputDocx,

    [Parameter(Mandatory = $false)]
    [string]$OutputPdf
)

$resolvedInput = (Resolve-Path -LiteralPath $InputDocx).Path
if (-not $OutputPdf) {
    $OutputPdf = [System.IO.Path]::ChangeExtension($resolvedInput, ".pdf")
}

$outputDir = Split-Path -Parent $OutputPdf
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$word = $null
$doc = $null
$createdNewApp = $false

try {
    try {
        $word = [Runtime.InteropServices.Marshal]::GetActiveObject("Word.Application")
    } catch {
        $word = New-Object -ComObject Word.Application
        $createdNewApp = $true
    }

    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($resolvedInput, $false, $true)
    $doc.ExportAsFixedFormat($OutputPdf, 17)
    $doc.Close(0)

    if ($createdNewApp) {
        $word.Quit()
    }

    [PSCustomObject]@{
        source = $resolvedInput
        pdf = $OutputPdf
        status = "ok"
    } | ConvertTo-Json -Compress
} catch {
    if ($doc) {
        try { $doc.Close(0) } catch {}
    }
    if ($createdNewApp -and $word) {
        try { $word.Quit() } catch {}
    }
    throw
}
