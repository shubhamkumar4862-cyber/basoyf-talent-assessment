import os,secrets,csv,io
from datetime import datetime,timezone
from flask import Flask,request,redirect,url_for,render_template_string,session,abort,send_file
import psycopg
from psycopg.rows import dict_row

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","change-me")
DATABASE_URL=os.environ.get("DATABASE_URL")
ADMIN_PIN=os.environ.get("ADMIN_PIN","2468")
WEB_CAM_ENFORCE=os.environ.get("WEB_CAM_ENFORCE","true").lower() in ("1","true","yes")
ASSESSMENT_DURATION_MINUTES=int(os.environ.get("ASSESSMENT_DURATION_MINUTES",38))

# Full question bank (preserve existing questions). We'll use only the first 40 MCQs for the timed section.
Q=[
("Logical Thinking","A process has four steps. A colleague skips step 2 because it seems unnecessary. What is the best response?",["Ignore it if the result is correct","Follow the approved process even if it seems slow","Tell them to do whatever they want","Report them to HR"],0),
("Logical Thinking","You notice a sudden increase in errors in today's report. What should you do first?",["Send it immediately","Delete the report","Check the data/source and identify the reason before reporting","Ignore it"],2),
("Logical Thinking","Three tasks are due today: one affects a customer immediately, one affects an internal report, and one is optional. Which should normally come first?",["Optional task","Internal report","Customer-facing task","Any task chosen at random"],2),
("Logical Thinking","You receive two instructions that appear to conflict. What is the best approach?",["Choose randomly","Follow the older one","Verify the current approved instruction with the appropriate owner","Ask a colleague to decide"],2),
("Logical Thinking","A problem keeps returning after temporary fixes. What should you focus on?",["Closing cases faster","Finding the root cause","Blaming the previous shift","Ignoring repeated cases"],1),
("Logical Thinking","A customer gives you incomplete information for an investigation. What should you do?",["Guess the missing information","Request the required information and explain why it is needed","Proceed with assumptions","Close the case"],1),
("Logical Thinking","A teammate's solution works but creates a new risk. What is the best response?",["Ignore the risk","Raise the concern professionally and suggest a safer approach","Tell the customer","Hide it"],1),
("Logical Thinking","You have 20 minutes left and discover an important quality issue in your work. What should you do?",["Hide it","Fix or escalate it and communicate the impact","Submit incorrect work","Ignore it"],1),
("Situational Judgment","Your manager gives you an urgent task while you are working on another urgent task. What should you clarify?",["Which task you like","Priority, deadline and business/customer impact","Who gave the task","The color of the task"],1),
("Situational Judgment","A colleague asks you to mark a task complete although it is not actually finished. What should you do?",["Agree","Decline and accurately update the status","Mark it complete and forget about it","Hide the issue"],1),
("Situational Judgment","You make an error in a report already shared internally. What demonstrates ownership?",["Hide it","Correct it and inform relevant stakeholders","Blame the data source","Wait for someone else to notice"],1),
("Situational Judgment","A team member is struggling with workload and asks for help while you have capacity. What is a professional response?",["Ignore them","Help where appropriate while protecting key priorities","Tell them it's their problem","Do their work for them entirely"],1),
("Situational Judgment","A process change is announced but you do not understand one important part. What should you do?",["Guess","Ask for clarification and use the latest approved guidance","Ignore the change","Wait until it's too late"],1),
("Situational Judgment","You disagree with a colleague's decision. What is the best way to handle it?",["Argue publicly","Discuss it professionally using facts/evidence","Complain to unrelated people","Do nothing"],1),
("Situational Judgment","A deadline is approaching but you cannot complete everything to the expected quality. What should you do?",["Submit poor-quality work silently","Communicate early, prioritize and ask for help","Lie about progress","Ignore quality"],1),
("Situational Judgment","You are asked to do something outside your authority. What should you do?",["Do it without checking","Verify authorization or escalate to the appropriate person","Ask a friend","Refuse immediately"],1),
("Customer & Communication","A customer is angry about a delay. What is the strongest response?",["Argue","Acknowledge the concern, explain the next step and provide a realistic update","Ignore them","Promise unrealistic timelines"],1),
("Customer & Communication","Which is the most professional sentence?",["I don't know, ask someone else.","This isn't my problem.","I'll verify that information and get back to you with an update.","I don't care."],2),
("Customer & Communication","A customer asks for an exception that policy does not allow. What should you do?",["Promise it anyway","Explain the policy clearly and offer any permitted alternatives","Ignore the request","Argue with the customer"],1),
("Customer & Communication","You cannot solve an issue during the first interaction. What is important?",["Close it quickly","Set expectations, document the issue and explain the next step","Avoid follow-up","Blame the customer"],1),
("Customer & Communication","A customer provides information that conflicts with system records. What should you do?",["Assume the customer is wrong","Verify the relevant records and ask clarifying questions","Apologize immediately","Escalate without checking"],1),
("Customer & Communication","Which communication style is best for a difficult customer?",["Defensive","Calm, clear, respectful and solution-focused","Sarcastic","Very informal"],1),
("Customer & Communication","A customer asks the same question twice because they did not understand. What should you do?",["Repeat the same sentence louder","Explain it more clearly using simple language","Get annoyed","Ignore them"],1),
("Customer & Communication","You discover that a previous agent gave incorrect information. What should you do?",["Hide it","Correct the information professionally and document the appropriate update","Ignore it","Blame the other agent"],1),
("Data & Accuracy","A team handled 100 cases Monday and 120 Tuesday. What was the increase?",["10%","20%","25%","30%"],1),
("Data & Accuracy","500 records contain 25 errors. What percentage contain errors?",["2%","5%","10%","25%"],1),
("Data & Accuracy","Five employees each handle 20 cases. Total cases?",["50","80","100","120"],2),
("Data & Accuracy","A ₹1,000 amount is reduced by 10%. What remains?",["₹900","₹910","₹990","₹1,100"],0),
("Data & Accuracy","A report has 200 cases. 50 are pending. What percentage are pending?",["15%","20%","25%","30%"],2),
("Data & Accuracy","You completed 72 tasks out of 80. What is your completion rate?",["80%","85%","90%","95%"],2),
("Data & Accuracy","A process takes 10 minutes per case. How long for 6 cases?",["30 minutes","50 minutes","60 minutes","70 minutes"],2),
("Data & Accuracy","A team processed 150 cases and 30 required review. What percentage required review?",["10%","15%","20%","30%"],2),
("Risk & Compliance","A transaction looks unusual but you have only one data point. What is the best approach?",["Immediately label it fraud","Review relevant evidence and transaction history before deciding","Ignore it","Escalate without checking"],1),
("Risk & Compliance","You see confidential customer data in an unofficial group chat. What should you do?",["Forward it","Follow the approved security/reporting process and avoid further sharing","Ignore it","Share with your manager only"],1),
("Risk & Compliance","A colleague asks for your login credentials to complete a task. What should you do?",["Share them","Refuse and use approved access procedures","Send a screenshot of the password","Do it quickly"],1),
("Risk & Compliance","A customer claims an unauthorized transaction. What should be prioritized?",["Assume fraud","Follow the approved verification and investigation process","Refund without check","Ignore it"],1),
("Risk & Compliance","Why is documentation important in investigations?",["It makes work slower","It provides an evidence trail and supports consistent decisions","It is only for managers","It is optional"],1),
("Risk & Compliance","You identify a potential policy breach but are not certain. What should you do?",["Accuse the person","Document facts and escalate/verify according to the process","Delete the evidence","Ignore it"],1),
("Risk & Compliance","A pattern indicates recurring operational risk. What should you do?",["Ignore it","Document the pattern and raise it through the appropriate channel","Hide it","Complain"],1),
]

# Use only the first 40 MCQs for the timed assessment (preserve existing scoring logic expecting 40 questions)
Q40=Q[:40]


def conn():
    if not DATABASE_URL: raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL,sslmode="require",row_factory=dict_row)

def init():
    c=conn()
    # Use TIMESTAMPTZ for timezone-aware timestamps and set a safe integer default directly in DDL
    c.execute(f"""CREATE TABLE IF NOT EXISTS candidates(
    id BIGSERIAL PRIMARY KEY,
    token TEXT UNIQUE,
    assessment_id TEXT UNIQUE,
    recruiter_id TEXT,
    assigned_role TEXT,
    name TEXT,
    email TEXT,
    role TEXT,
    intro TEXT,
    intro_score INTEGER,
    mcq_correct INTEGER,
    mcq_score INTEGER,
    overall INTEGER,
    recommendation TEXT,
    integrity_accepted BOOLEAN DEFAULT FALSE,
    webcam_consent_accepted BOOLEAN DEFAULT FALSE,
    webcam_permission_granted BOOLEAN DEFAULT FALSE,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_minutes INTEGER DEFAULT {ASSESSMENT_DURATION_MINUTES},
    submitted_at TEXT
    )""")
    # Add any missing columns to keep compatibility with older DBs
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS assessment_id TEXT")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS recruiter_id TEXT")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS assigned_role TEXT")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS integrity_accepted BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS webcam_consent_accepted BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS webcam_permission_granted BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ")
    c.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT %s",(ASSESSMENT_DURATION_MINUTES,))
    c.commit();c.close()
init()

CSS="""<style>
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#173b57,#07111f 40%,#040a12);color:#edf6ff;font-family:Inter,system-ui,Arial}.wrap{max-width:1050px;margin:auto;padding:20px}a{color:inherit}
.panel{background:rgba(255,255,255,0.03);padding:24px;border-radius:12px;margin:20px 0}
.option{display:block;padding:6px 0}
.timer{font-family:monospace;background:#001927;padding:8px;border-radius:8px;display:inline-block}
.muted{color:#9fb3c9}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
input[type=text],input[type=email],textarea{width:100%;padding:8px;border-radius:6px;border:0;background:rgba(255,255,255,0.04);color:inherit}
.btn{display:inline-block;padding:10px 16px;border-radius:8px;background:#0ea5a5;color:#012;text-decoration:none}
</style>"""

BASE="""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>BASOYF Talent Assessment</title>"""+CSS+"""</head><body><div class='wrap'>"""

HOME=BASE+"""<div class='panel hero'><span class='pill'>MNC SCREENING • 40 MCQs + INTRODUCTION</span><h1>Assess <span class='accent'>potential</span>, not memorisation.</h1><p class='muted'>A professional, privacy-first screening assessment.</p></div>"""

def candidate_entry_html():
    return BASE+f"""<form class='panel' method='post' action='/begin' id='entry'>
    <h1>Professional Assessment</h1>
    <div class='grid'><label>Full legal name<input name='name' required></label><label>Email<input type='email' name='email' required></label></div>
    <p class='muted'>We collect only your full legal name and email. By continuing you agree to the integrity declaration and webcam/privacy consent below.</p>
    <label style='display:block;margin:12px 0'><input type='checkbox' name='integrity' id='integrity'> I confirm that the work I submit will be my own and in line with the integrity policy. (Required)</label>
    <label style='display:block;margin:12px 0'><input type='checkbox' name='webcam_consent' id='webcam_consent'> I consent to in-browser webcam permission for proctoring (no recordings are stored). (Required)</label>
    <div id='cam-status' class='muted' style='margin:8px 0'></div>
    <button type='button' class='btn' id='begin'>Begin Assessment</button>
    </form>
    <script>
    const begin=document.getElementById('begin');
    begin.addEventListener('click',async ()=>{
        const integrity=document.getElementById('integrity').checked;
        const consent=document.getElementById('webcam_consent').checked;
        if(!integrity||!consent){alert('Please accept the integrity declaration and webcam consent to proceed.');return}
        const status=document.getElementById('cam-status');
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){status.textContent='Camera not available in this browser. The assessment cannot be started.';return}
        try{
            status.textContent='Requesting camera permission...';
            const stream=await navigator.mediaDevices.getUserMedia({video:true});
            // stop tracks immediately; we only need permission
            stream.getTracks().forEach(t=>t.stop());
            status.textContent='Camera permission granted. Starting assessment...';
            // submit the form with an extra hidden field to indicate permission granted
            const f=document.getElementById('entry');
            const inp=document.createElement('input');inp.type='hidden';inp.name='webcam_permission';inp.value='1';f.appendChild(inp);
            f.submit();
        }catch(e){status.textContent='Camera permission denied or unavailable. You cannot start the assessment.';alert('Camera permission is required to begin the assessment.');}
    });
    </script></div></body></html>"""


def take_assessment_html(token,start_time_iso):
    qs=""
    for i,q in enumerate(Q40):
        opts="".join(f"<label class='option'><input type='radio' name='q{i}' value='{j}' required> {'ABCD'[j]}. {o}</label>" for j,o in enumerate(q[2]))
        qs+=f"<div class='q'><span class='section'>{q[0]}</span><p><b>{i+1}. {q[1]}</b></p>{opts}</div>"
    # calculate remaining time on client start using server-provided start_time (ISO) to prevent tampering
    return BASE+f"""<form class='panel' method='post' action='/submit/{token}' id='f'>
    <div style='display:flex;justify-content:space-between;align-items:center'><h1>Assessment — 40 MCQs</h1><div class='timer' id='t'>38:00</div></div>
    <input type='hidden' id='server_start' value='{start_time_iso}'>
    {qs}
    <div style='margin-top:12px'><label>Introduction (optional)<textarea name='intro' rows=4 placeholder='Introduce yourself in 60-220 words'></textarea></label></div>
    <button type='submit' class='btn'>Submit Assessment</button>
    </form>
    <script>
    // Timer logic: compute elapsed based on server_start
    const serverStart=document.getElementById('server_start').value;
    const start=new Date(serverStart);
    const durationMinutes={ASSESSMENT_DURATION_MINUTES};
    function updateTimer(){
        const now=new Date();
        const elapsed=Math.floor((now-start)/1000);
        const rem=Math.max(0,durationMinutes*60 - elapsed);
        const mm=String(Math.floor(rem/60)).padStart(2,'0');
        const ss=String(rem%60).padStart(2,'0');
        document.getElementById('t').textContent=mm+':'+ss;
        if(rem<=0){alert('Time is up. The assessment will be submitted.');document.getElementById('f').submit();}
    }
    updateTimer();setInterval(updateTimer,1000);
    </script></div></body></html>"""


@app.route("/")
def home(): return HOME

@app.route("/test",methods=["GET"])
def test():
    return candidate_entry_html()

@app.route('/begin',methods=['POST'])
def begin():
    name=request.form.get('name','').strip()
    email=request.form.get('email','').strip()
    integrity=request.form.get('integrity')
    webcam_consent=request.form.get('webcam_consent')
    webcam_permission=request.form.get('webcam_permission')
    if not name or not email: return "Name and email are required",400
    if not integrity or not webcam_consent: return "Integrity declaration and webcam consent are required",400
    # enforce webcam permission if configured
    if WEB_CAM_ENFORCE and not webcam_permission:
        return "Camera permission is required to begin the assessment.",400
    # create candidate row and set start_time
    token=secrets.token_urlsafe(16)
    assessment_id=f"ASMT-{secrets.token_hex(3).upper()}"
    now=datetime.now(timezone.utc)
    webcam_granted = True if webcam_permission else False
    c=conn()
    c.execute("""INSERT INTO candidates(token,assessment_id,name,email,integrity_accepted,webcam_consent_accepted,webcam_permission_granted,start_time,duration_minutes)
                 VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(token,assessment_id,name,email,True,True,webcam_granted,now,ASSESSMENT_DURATION_MINUTES))
    c.commit();c.close()
    return redirect(url_for('take',token=token))

@app.route('/take/<token>',methods=['GET'])
def take(token):
    c=conn();r=c.execute("SELECT * FROM candidates WHERE token=%s",(token,)).fetchone();c.close()
    if not r: abort(404)
    if not r.get('start_time'):
        abort(400)
    return take_assessment_html(token,r['start_time'].isoformat())

@app.route('/submit/<token>',methods=['POST'])
def submit(token):
    c=conn();r=c.execute("SELECT * FROM candidates WHERE token=%s",(token,)).fetchone()
    if not r: c.close();abort(404)
    # enforce server-side timer
    start=r.get('start_time')
    if not start:
        c.close();return "Assessment has not been started properly.",400
    now=datetime.now(timezone.utc)
    elapsed=(now - start).total_seconds()
    if elapsed > (r.get('duration_minutes') or ASSESSMENT_DURATION_MINUTES)*60:
        # record end_time and submitted_at but reject scoring
        c.execute("UPDATE candidates SET end_time=%s,submitted_at=%s WHERE token=%s",(now,now.isoformat(),token))
        c.commit();c.close()
        return "Time limit exceeded. Answers submitted after the allowed duration are not accepted.",400
    # score answers
    correct=sum(1 for i,q in enumerate(Q40) if request.form.get(f"q{i}") and int(request.form[f"q{i}"])==q[3])
    words=len(request.form.get('intro','').split())
    intro_score=20 if 100<=words<=220 else 15 if words>=60 else 10 if words>=30 else 5
    mcq_score=round(correct/len(Q40)*80)
    overall=mcq_score+intro_score
    rec="Strong Candidate" if overall>=80 else "Potential Candidate" if overall>=65 else "Needs Further Review"
    tok=token
    c.execute("""UPDATE candidates SET intro=%s,intro_score=%s,mcq_correct=%s,mcq_score=%s,overall=%s,recommendation=%s,end_time=%s,submitted_at=%s
                 WHERE token=%s""",(request.form.get('intro','').strip(),intro_score,correct,mcq_score,overall,rec,now,now.isoformat(),tok))
    c.commit();c.close()
    return redirect(url_for('result',token=tok))

@app.route("/result/<token>")
def result(token):
    c=conn();r=c.execute("SELECT * FROM candidates WHERE token=%s",(token,)).fetchone();c.close()
    if not r: abort(404)
    return BASE+f"""<div class='panel' style='text-align:center'><span class='pill'>ASSESSMENT COMPLETE</span><h1>{r['name']}</h1><div class='big'>{r.get('overall','N/A')}/100</div><h2>{r.get('recommendation','')}</h2><p class='muted'>Assessment ID: {r.get('assessment_id')}</p></div></div></body></html>"""

@app.route("/admin",methods=["GET","POST"]) 
def admin():
    if request.method=="POST":
        if request.form.get("pin")==ADMIN_PIN: session["admin"]=True
        else: return BASE+"<div class='panel'><h2>Incorrect PIN</h2><a href='/admin'>Try again</a></div></div></body></html>"
    if not session.get("admin"): return BASE+"<div class='panel'><h1>Recruiter Login</h1><p class='muted'>Enter your private recruiter PIN.</p><form method='post'><input type='password' name='pin'><button class='btn' type='submit'>Login</button></form></div></div></body></html>"
    c=conn();rows=c.execute("SELECT * FROM candidates ORDER BY id DESC").fetchall();c.close();avg=round(sum(x['overall'] for x in rows)/len(rows)) if rows else 0;strong=sum(x['overall']>=80 for x in rows) if rows else 0
    tr="".join(f"<tr><td>{x.get('name')}<br><small>{x.get('email')}</small></td><td>{x.get('assessment_id')}<br><small>{x.get('assigned_role') or x.get('role') or ''}</small></td><td>{x.get('mcq_correct')}/40</td><td>{x.get('intro_score')}/20</td><td><b>{x.get('overall')}/100</b></td><td>{'Yes' if x.get('integrity_accepted') else 'No'}/{ 'Yes' if x.get('webcam_consent_accepted') else 'No'}</td><td>{x.get('submitted_at')}</td></tr>" for x in rows)
    return BASE+f"""<div class='panel'><h1>Recruiter Dashboard</h1><div class='cards'><div class='card'><b>{len(rows)}</b><br><span class='muted'>Assessments</span></div><div class='card'><b>{str(avg)}</b><br><span class='muted'>Average Score</span></div><div class='card'><b>{strong}</b><br><span class='muted'>Strong</span></div></div><table style='width:100%;margin-top:12px;border-collapse:collapse'> <thead><tr><th>Candidate</th><th>Assessment / Role</th><th>MCQ</th><th>Intro</th><th>Overall</th><th>Integrity/Webcam</th><th>Submitted</th></tr></thead><tbody>{tr}</tbody></table><p style="margin-top:12px"><a href='/export.csv' class='btn'>Export CSV</a></p></div></div></body></html>"""

@app.route("/export.csv")
def export():
    if not session.get("admin"): abort(403)
    c=conn();rows=c.execute("SELECT assessment_id,name,email,assigned_role,integrity_accepted,webcam_consent_accepted,webcam_permission_granted,start_time,end_time,submitted_at,mcq_correct,mcq_score,intro_score,overall,recommendation FROM candidates ORDER BY id DESC").fetchall();c.close()
    out=io.StringIO();w=csv.writer(out);w.writerow(["Assessment ID","Candidate","Email","Assigned Role","Integrity Accepted","Webcam Consent","Webcam Permission","Start Time","End Time","Submitted","MCQ Correct","MCQ Score","Introduction","Overall","Recommendation"])
    for r in rows:
        w.writerow([r.get('assessment_id'),r.get('name'),r.get('email'),r.get('assigned_role') or r.get('role'),r.get('integrity_accepted'),r.get('webcam_consent_accepted'),r.get('webcam_permission_granted'),r.get('start_time'),r.get('end_time'),r.get('submitted_at'),r.get('mcq_correct'),r.get('mcq_score'),r.get('intro_score'),r.get('overall'),r.get('recommendation')])
    b=io.BytesIO(out.getvalue().encode());b.seek(0);return send_file(b,mimetype="text/csv",as_attachment=True,download_name="basoyf_candidates.csv")

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
