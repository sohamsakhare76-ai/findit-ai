# Contributing to FindIt AI

Thanks for your interest in contributing!

## Development setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the app with:

```powershell
python app.py
```

Run tests with:

```powershell
pytest
```

## Guidelines

- Keep changes focused and easy to review.
- Do not commit personal photos, databases, model weights, secrets, or virtual environments.
- Do not fabricate detection results or benchmarks.
- Keep privacy claims aligned with the actual implementation.
- Add or update tests when changing database/search behaviour.
- Prefer simple solutions over unnecessary infrastructure.

## Pull requests

Please describe:

1. What changed
2. Why it changed
3. How you tested it
4. Any limitations or follow-up work
