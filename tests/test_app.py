import sys
import types
import json
import pytest
from datetime import datetime,timezone,timedelta

# Build a fake psycopg module before importing the app so the module-level init() in app.py uses the fake.
class FakeDB:
    def __init__(self):
        # store rows keyed by token
        self.rows = {}
        self.last_query = None
        self.last_params = None
        self._last_result = None

    def connect(self, *a, **k):
        return self

    # emulate cursor/connection execute returning self (so .fetchone() works)
    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        q = query.lower()
        # simple handling for our test cases
        if 'insert into candidates' in q:
            # params order based on app.py INSERT in begin()
            # (token,assessment_id,name,email,True,True,webcam_granted,now,ASSESSMENT_DURATION_MINUTES)
            token = params[0]
            assessment_id = params[1]
            name = params[2]
            email = params[3]
            integrity = params[4]
            webcam_consent = params[5]
            webcam_granted = params[6]
            start_time = params[7]
            duration = params[8]
            self.rows[token] = {
                'token': token,
                'assessment_id': assessment_id,
                'name': name,
                'email': email,
                'integrity_accepted': integrity,
                'webcam_consent_accepted': webcam_consent,
                'webcam_permission_granted': webcam_granted,
                'start_time': start_time,
                'duration_minutes': duration,
                'intro_score': None,
                'mcq_correct': None,
                'mcq_score': None,
                'overall': None,
                'recommendation': None,
                'submitted_at': None,
                'end_time': None,
            }
            self._last_result = None
            return self
        if 'select * from candidates where token=%s' in q:
            token = params[0]
            row = self.rows.get(token)
            # return a dict-like object
            self._last_result = row
            return self
        if q.strip().startswith('update candidates set'):
            # last param is token
            token = params[-1]
            row = self.rows.get(token)
            if not row:
                self._last_result = None
                return self
            # map fields in the UPDATE used in submit()
            # UPDATE candidates SET intro=%s,intro_score=%s,mcq_correct=%s,mcq_score=%s,overall=%s,recommendation=%s,end_time=%s,submitted_at=%s WHERE token=%s
            row['intro'] = params[0]
            row['intro_score'] = params[1]
            row['mcq_correct'] = params[2]
            row['mcq_score'] = params[3]
            row['overall'] = params[4]
            row['recommendation'] = params[5]
            row['end_time'] = params[6]
            row['submitted_at'] = params[7]
            self.rows[token] = row
            self._last_result = None
            return self
        if 'update candidates set end_time=%s,submitted_at=%s where token=%s' in q:
            token = params[2]
            row = self.rows.get(token)
            if row:
                row['end_time'] = params[0]
                row['submitted_at'] = params[1]
                self.rows[token] = row
            self._last_result = None
            return self
        if 'select assessment_id,name,email,assigned_role' in q or 'select * from candidates order by id desc' in q:
            # return all rows
            self._last_result = list(self.rows.values())
            return self
        self._last_result = None
        return self

    def fetchone(self):
        return self._last_result

    def fetchall(self):
        return self._last_result or list(self.rows.values())

    def commit(self):
        pass

    def close(self):
        pass

# Insert fake psycopg into sys.modules before importing app
fake_psycopg = types.ModuleType('psycopg')
_db = FakeDB()
fake_psycopg.connect = _db.connect
# minimal rows namespace used in app
fake_rows = types.SimpleNamespace(dict_row=dict)
fake_psycopg.rows = fake_rows
sys.modules['psycopg'] = fake_psycopg

import importlib
# import the app module after installing fake psycopg
app = importlib.import_module('app')

@pytest.fixture(autouse=True)
def client(monkeypatch):
    # ensure the app uses our fake DB by patching app.conn to return the singleton _db
    monkeypatch.setattr(app, 'conn', lambda: _db)
    return app.test_client()


def test_begin_requires_integrity_and_consent(client):
    rv = client.post('/begin', data={'name': 'Alice','email':'a@example.com'})
    assert rv.status_code == 400
    assert b'Integrity declaration' in rv.data


def test_begin_requires_webcam_permission_when_enforced(client, monkeypatch):
    # ensure WEB_CAM_ENFORCE is True
    monkeypatch.setenv('WEB_CAM_ENFORCE', 'true')
    rv = client.post('/begin', data={'name':'Bob','email':'b@example.com','integrity':'on','webcam_consent':'on'})
    assert rv.status_code == 400
    assert b'Camera permission is required' in rv.data


def test_begin_creates_candidate_with_permission(client):
    # simulate webcam permission provided
    rv = client.post('/begin', data={'name':'Carol','email':'c@example.com','integrity':'on','webcam_consent':'on','webcam_permission':'1'}, follow_redirects=False)
    # should redirect to /take/<token>
    assert rv.status_code in (302, 303)
    loc = rv.headers.get('Location')
    assert loc and '/take/' in loc
    token = loc.split('/')[-1]
    # confirm candidate saved in fake DB
    row = _db.rows.get(token)
    assert row is not None
    assert row['webcam_permission_granted'] is True


def test_submit_time_exceeded(client, monkeypatch):
    # create a candidate with start_time far in the past
    token = 'tok-exceeded'
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=AS_MINUTES:=int(app.ASSESSMENT_DURATION_MINUTES) + 5)
    _db.rows[token] = {'token':token,'assessment_id':'ASMT-XXX','name':'Old','email':'old@example.com','integrity_accepted':True,'webcam_consent_accepted':True,'webcam_permission_granted':True,'start_time':past,'duration_minutes':app.ASSESSMENT_DURATION_MINUTES}
    rv = client.post(f'/submit/{token}', data={})
    assert rv.status_code == 400
    assert b'Time limit exceeded' in rv.data


def test_submit_within_time_scores(client):
    # create candidate within time
    token = 'tok-ok'
    now = datetime.now(timezone.utc)
    _db.rows[token] = {'token':token,'assessment_id':'ASMT-OK','name':'Now','email':'now@example.com','integrity_accepted':True,'webcam_consent_accepted':True,'webcam_permission_granted':True,'start_time':now,'duration_minutes':app.ASSESSMENT_DURATION_MINUTES}
    # submit with all correct answers for Q40
    data = {}
    for i in range(len(app.Q40)):
        data[f'q{i}'] = str(app.Q40[i][3])
    data['intro'] = 'word ' * 120
    rv = client.post(f'/submit/{token}', data=data, follow_redirects=False)
    # should redirect to result
    assert rv.status_code in (302,303)
    # verify row updated
    row = _db.rows.get(token)
    assert row['mcq_correct'] == len(app.Q40)
    assert row['intro_score'] == 20
    assert row['overall'] is not None
