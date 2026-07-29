param([switch]$Dev)

python -m pip install -e ".[dev]" --quiet
if ($LASTEXITCODE -ne 0) { exit }

Push-Location canvas_app\frontend
npm install --silent
if ($Dev) {
    npm run dev
} else {
    npm run build --silent
    Pop-Location
    uvicorn vajra_gate:app --reload --port 8000
}
