from datetime import date, datetime, timedelta
from pathlib import Path
import csv
import io
import json
import os
from calendar import monthrange

from flask import Flask, render_template, request, redirect, url_for, flash, make_response

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-this-secret-key')
DATA_FILE = Path(__file__).with_name('attendance.json')


def load_records():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_records(records):
    DATA_FILE.write_text(json.dumps(records, indent=2), encoding='utf-8')


def duration_minutes(time_in, time_out):
    start = datetime.strptime(time_in, '%H:%M')
    end = datetime.strptime(time_out, '%H:%M')
    minutes = (end.hour * 60 + end.minute - start.hour * 60 - start.minute) % 1440
    if minutes == 0:
        raise ValueError('Time in and time out must be different.')
    return minutes


def hhmm(minutes):
    sign = '-' if minutes < 0 else ''
    minutes = abs(minutes)
    return f'{sign}{minutes // 60:02d}:{minutes % 60:02d}'


def enrich_record(record):
    day = date.fromisoformat(record['date'])
    worked = duration_minutes(record['time_in'], record['time_out'])
    weekend = day.weekday() >= 5
    standard = 300 if weekend else 480
    overtime = max(0, worked - standard)
    shortfall = max(0, standard - worked)
    return {**record, 'day_name': day.strftime('%A'),
            'shift_type': 'Weekend' if weekend else 'Weekday',
            'worked_minutes': worked, 'worked_hhmm': hhmm(worked),
            'worked_decimal': round(worked / 60, 2),
            'standard_hours': standard // 60,
            'overtime_minutes': overtime, 'overtime_hhmm': hhmm(overtime),
            'shortfall_minutes': shortfall, 'shortfall_hhmm': hhmm(shortfall),
            'balance_minutes': worked - standard}


def selected_month():
    value = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        parsed = datetime.strptime(value, '%Y-%m').date()
        if parsed.year < 1900 or parsed.year > 9998:
            raise ValueError()
        return parsed.replace(day=1)
    except ValueError:
        return date.today().replace(day=1)


def month_shift(day, offset):
    index = day.year * 12 + day.month - 1 + offset
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def month_records(month):
    prefix = month.strftime('%Y-%m') + '-'
    return sorted((enrich_record(r) for r in load_records() if r['date'].startswith(prefix)), key=lambda r: r['date'])


@app.route('/')
def index():
    month = selected_month()
    records = month_records(month)
    total_worked = sum(r['worked_minutes'] for r in records)
    total_ot = sum(r['overtime_minutes'] for r in records)
    total_shortfall = sum(r['shortfall_minutes'] for r in records)
    today = date.today()
    default_date = today.isoformat() if today.year == month.year and today.month == month.month else month.isoformat()
    return render_template('index.html', records=records, total_worked=total_worked,
                           total_ot=total_ot, total_shortfall=total_shortfall,
                           net_balance=total_ot-total_shortfall, hhmm=hhmm,
                           default_date=default_date, selected_month=month.strftime('%Y-%m'),
                           previous_month=month_shift(month, -1), next_month=month_shift(month, 1),
                           month_name=month.strftime('%B'), year=month.year)


@app.route('/add', methods=['POST'])
def add_record():
    date_text = request.form.get('date', '').strip()
    time_in = request.form.get('time_in', '').strip()
    time_out = request.form.get('time_out', '').strip()
    month = request.form.get('month', date.today().strftime('%Y-%m'))
    try:
        day = date.fromisoformat(date_text)
        duration_minutes(time_in, time_out)
    except ValueError as exc:
        flash(str(exc) if str(exc) else 'Please enter valid date and times.', 'error')
        return redirect(url_for('index', month=month))
    records = [r for r in load_records() if r['date'] != date_text]
    records.append({'date': day.isoformat(), 'time_in': time_in, 'time_out': time_out})
    records.sort(key=lambda r: r['date'])
    save_records(records)
    flash('Attendance saved.', 'success')
    return redirect(url_for('index', month=day.strftime('%Y-%m')))


@app.route('/delete/<date_text>', methods=['POST'])
def delete_record(date_text):
    records = [r for r in load_records() if r['date'] != date_text]
    save_records(records)
    flash('Entry deleted.', 'success')
    return redirect(url_for('index', month=date_text[:7]))


@app.route('/export')
def export_csv():
    month = selected_month()
    records = month_records(month)
    output = io.StringIO()
    fields = ['Date', 'Day', 'Shift Type', 'Time In', 'Time Out', 'Total Hours Worked',
              'Total Hours (Decimal)', 'Standard Hours', 'OT in Minutes', 'OT in Hours',
              'Shortfall in Minutes', 'Shortfall in Hours', 'Net Balance (HH:MM)']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for r in records:
        writer.writerow({'Date': r['date'], 'Day': r['day_name'], 'Shift Type': r['shift_type'],
                         'Time In': r['time_in'], 'Time Out': r['time_out'],
                         'Total Hours Worked': r['worked_hhmm'],
                         'Total Hours (Decimal)': r['worked_decimal'],
                         'Standard Hours': r['standard_hours'],
                         'OT in Minutes': r['overtime_minutes'], 'OT in Hours': r['overtime_hhmm'],
                         'Shortfall in Minutes': r['shortfall_minutes'],
                         'Shortfall in Hours': r['shortfall_hhmm'],
                         'Net Balance (HH:MM)': hhmm(r['balance_minutes'])})
    worked = sum(r['worked_minutes'] for r in records)
    ot = sum(r['overtime_minutes'] for r in records)
    shortfall = sum(r['shortfall_minutes'] for r in records)
    writer.writerow({'Date': 'TOTAL', 'Total Hours Worked': hhmm(worked),
                     'Total Hours (Decimal)': round(worked / 60, 2),
                     'OT in Minutes': ot, 'OT in Hours': hhmm(ot),
                     'Shortfall in Minutes': shortfall, 'Shortfall in Hours': hhmm(shortfall),
                     'Net Balance (HH:MM)': hhmm(ot-shortfall)})
    response = make_response('\ufeff' + output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=work_hours_{month:%Y_%m}.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response


if __name__ == '__main__':
    app.run(debug=True)
