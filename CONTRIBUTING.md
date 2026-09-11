# Contributing to SatQuery AI

Thanks for taking the time to contribute. This project is an SIH-grade working
prototype, and a few ground rules keep the demo trustworthy:

## Project principles

1. **Never fake a model result.** If a specialist model (TEOChat, Open-CD, SamGeo,
   TerraMind, SAR/U-Net, LRS-VQA) is not connected, fall back honestly and surface
   a warning. Do not label a heuristic as a semantic/model-backed result.
2. **Provenance everywhere.** Every analysis must keep tracking the actual method,
   model, fallback status and source scenes/dates/CRS/resolution.
3. **Evidence over claims.** Operational confidence is a UI aid, never a calibrated
   scientific probability.
4. **Safety guards stay conservative.** Requests for forecasting, live alerting or
   population/economic impact are rejected instead of producing fabricated answers.

## Development workflow

1. Fork the repository and create a feature branch from `main`.
2. Make focused changes with clear commit messages.
3. Run the validation suite before pushing:

   ```bash
   python scripts/test_natural_language.py
   python scripts/smoke_test.py
   python scripts/test_trust_contract.py
   python scripts/test_e2e_matrix.py
   ```

   And for the frontend:

   ```bash
   cd frontend
   npm run lint
   npm run build
   ```

4. Update the relevant docs (`FEATURE_MATRIX.md`, `FIXES_IMPLEMENTED.md`,
   `TEST_REPORT_V4.md`) if behavior or coverage changes.
5. Open a pull request describing what changed and why.

## Environment

- Backend dependencies: `pip install -r backend/requirements.txt`
- Optional model service: `pip install -r backend/requirements-ml.txt` (heavy)
- Frontend dependencies: `npm install` in `frontend/`
- Never commit `.env`, `backend/data/`, `frontend/dist/`, `.venv/`, model weights
  or downloaded scenes.

## Reporting issues

Provide the exact query, the selected datasets (filenames + modality), the backend
version and the full execution trace/error so the failure is reproducible offline.