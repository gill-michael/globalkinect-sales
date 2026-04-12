$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "."

Write-Host "Starting monthly Vibe Prospecting scan at $(Get-Date -Format o)"

.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region gcc --icp A1 --limit 1000
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region gcc --icp A2 --limit 500
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region gcc --icp A3 --limit 200
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region mena --icp B3 --limit 400
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region mena --icp B4 --limit 300
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region uk --icp B2 --limit 400
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region europe --icp B1 --limit 400

Write-Host "All Vibe scans complete. Running sourcing engine in live mode."

$env:SALES_ENGINE_RUN_MODE = "live"
$env:SALES_ENGINE_TRIGGERED_BY = "monthly_scan"
.\venv\Scripts\python.exe main.py

Write-Host "Monthly scan finished at $(Get-Date -Format o)"

# To schedule this in Windows Task Scheduler to run on the 1st of every month at 07:00:
#
# schtasks /create /tn "GlobalKinect Monthly Scan" /tr "powershell -File C:\dev\globalkinect\sales\scripts\run_monthly_scan.ps1" /sc monthly /d 1 /st 07:00
#
# Verify with:   schtasks /query /tn "GlobalKinect Monthly Scan"
# Remove with:   schtasks /delete /tn "GlobalKinect Monthly Scan" /f
