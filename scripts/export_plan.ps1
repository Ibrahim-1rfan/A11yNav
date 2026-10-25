# Requires Microsoft Word. Creates a separate hidden instance for this document.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$inputPath = Join-Path $projectRoot 'deliverables\CUA_Implementation_Plan.docx'
$outputPath = Join-Path $projectRoot 'deliverables\CUA_Implementation_Plan.pdf'
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible = $false
$wordApp.DisplayAlerts = 0
$planDoc = $null
try {
    $planDoc = $wordApp.Documents.Open($inputPath)
    Write-Host 'Opened generated plan.'
    $planDoc.Repaginate()
    if ($planDoc.TablesOfContents.Count -gt 0) { $planDoc.TablesOfContents.Item(1).Update() }
    Write-Host 'Updated contents.'
    $planDoc.ExportAsFixedFormat($outputPath, 17)
    $planDoc.Save()
    Write-Host 'Updated contents and exported the matching PDF.'
} finally {
    if ($null -ne $planDoc) { $planDoc.Close(0) }
    $wordApp.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) | Out-Null
}
