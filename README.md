# Work Hours Tracker (Flask)

Tracks attendance for any month/year, with monthly navigation and CSV exports.

## Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Rules
- Monday–Friday: 8-hour standard.
- Saturday–Sunday: 5-hour standard (preserved from original application).
- Overtime: max(0, minutes worked - standard minutes).
- Shortfall: max(0, standard minutes - minutes worked).
- Net balance: overtime - shortfall; may be negative.
- Only recorded dates are counted. Unrecorded weekdays are not automatically treated as absences.
- No unpaid break deduction; overnight shifts are supported.
- One record per date. Re-saving a date updates it.
- Data is stored in `attendance.json` in the application folder. Keep this file when updating the app.
- Export CSV exports the currently selected month.
