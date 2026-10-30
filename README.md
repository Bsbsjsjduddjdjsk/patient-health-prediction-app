# Patient Health Prediction Application

Flask + SQLite + Bootstrap web application. Each patient record stores full name, date of birth,
email, glucose, haemoglobin and cholesterol. When a record is saved, the values are sent to a
separate **Health Prediction API** (`health_api.py`, a REST service on port 5001) and the predicted
risk level and possible conditions are stored in **Remarks**.

## Run (two terminals, from this folder)

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt

python health_api.py           # terminal 1: Health API  -> http://127.0.0.1:5001
python app.py                  # terminal 2: web app     -> http://127.0.0.1:5000
```

If the API is not running, records still save and Remarks shows "Pending"; start the API and
press **Regenerate**.

## Health Prediction API

`POST /predict` with `{"age": 35, "glucose": 110, "haemoglobin": 13.5, "cholesterol": 210}` returns
`risk_level` (Low / Moderate / High), `risk_score`, `findings`, `possible_conditions`, `remarks`
and `source` (`"ai"` or `"rules"`). `GET /health` reports status.

* **Rule-based screening (always available):** glucose (fasting, mg/dL), haemoglobin (g/dL) and
  total cholesterol (mg/dL) are compared with adult reference ranges; findings from age 45+ carry
  extra weight.
* **External AI model (optional):** if the environment variable `ANTHROPIC_API_KEY` is set, the API
  also asks an AI model to write the remark. If the key is missing or the call fails, the
  rule-based remark is used. The key is read from the environment only; it is never stored in the code.

```powershell
$env:ANTHROPIC_API_KEY = "your-key"   # PowerShell, before: python health_api.py
```

This is a screening aid, not a diagnosis.

## Validation rules

| Field | Rule |
|---|---|
| Full Name | Required; letters, spaces, `. ' -` |
| Date of Birth | `dd/mm/yyyy` (slash separator), real calendar date, not in the future |
| Email | Valid format; unique across records |
| Glucose / Haemoglobin / Cholesterol | Numeric; glucose 20-800, haemoglobin 3-25, cholesterol 50-600 |

## Test entries

Entered exactly as given, all ten fail because the dates use `.` instead of `/`. Re-entering the
dates with `/` (all other values unchanged):

| # | Result | Reason |
|---|---|---|
| 1 | Saved | Valid |
| 2 | Rejected | `hunter@gmail` has no domain extension |
| 3 | Saved | Valid |
| 4 | Rejected | 31 November is not a real date |
| 5 | Saved | Valid |
| 6 | Rejected | Email already used by record #1 |
| 7 | Saved | Valid |
| 8 | Rejected | Date of birth in the future; email has no `@` |
| 9 | Saved | Valid |
| 10 | Saved | Valid |
