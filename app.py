import os,secrets,csv,io
from datetime import datetime
from flask import Flask,request,redirect,url_for,render_template_string,session,abort,send_file
import psycopg
from psycopg.rows import dict_row

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","change-me")
DATABASE_URL=os.environ.get("DATABASE_URL")
ADMIN_PIN=os.environ.get("ADMIN_PIN","2468")

Q=[
("Logical Thinking","A process has four steps. A colleague skips step 2 because it seems unnecessary. What is the best response?",["Ignore it if the result is correct","Follow the approved process and verify whether step 2 can officially be changed","Skip it too","Only report it after a customer complains"],1),
("Logical Thinking","You notice a sudden increase in errors in today's report. What should you do first?",["Send it immediately","Delete the report","Check the data/source and identify the reason for the change","Assume the team performed badly"],2),
("Logical Thinking","Three tasks are due today: one affects a customer immediately, one affects an internal report, and one is optional. Which should normally come first?",["Optional task","Internal report","Customer-impacting urgent task","Whichever is easiest"],2),
("Logical Thinking","You receive two instructions that appear to conflict. What is the best approach?",["Choose randomly","Follow the older one","Verify the current approved instruction with the appropriate source/person","Do both without checking"],2),
("Logical Thinking","A problem keeps returning after temporary fixes. What should you focus on?",["Closing cases faster","Finding the root cause","Blaming the previous shift","Ignoring repeated cases"],1),
("Logical Thinking","A customer gives you incomplete information for an investigation. What should you do?",["Guess the missing information","Request the required information and explain why it is needed","Reject the customer immediately","Close the case"],1),
("Logical Thinking","A teammate's solution works but creates a new risk. What is the best response?",["Ignore the risk","Raise the concern professionally and suggest a safer approach","Tell the customer","Copy the solution"],1),
("Logical Thinking","You have 20 minutes left and discover an important quality issue in your work. What should you do?",["Hide it","Fix or escalate it and communicate the impact","Submit incorrect work","Wait for someone else"],1),
("Situational Judgment","Your manager gives you an urgent task while you are working on another urgent task. What should you clarify?",["Which task you like","Priority, deadline and business/customer impact","Who is more senior","Which task is shorter"],1),
("Situational Judgment","A colleague asks you to mark a task complete although it is not actually finished. What should you do?",["Agree","Decline and accurately update the status","Mark it complete and finish later without telling anyone","Ignore the request"],1),
("Situational Judgment","You make an error in a report already shared internally. What demonstrates ownership?",["Hide it","Correct it and inform relevant stakeholders","Blame the data source","Wait for a complaint"],1),
("Situational Judgment","A team member is struggling with workload and asks for help while you have capacity. What is a professional response?",["Ignore them","Help where appropriate while protecting your own priorities","Tell everyone","Take over all their work permanently"],1),
("Situational Judgment","A process change is announced but you do not understand one important part. What should you do?",["Guess","Ask for clarification and use the latest approved guidance","Continue with the old process forever","Ignore the change"],1),
("Situational Judgment","You disagree with a colleague's decision. What is the best way to handle it?",["Argue publicly","Discuss it professionally using facts/evidence","Complain to unrelated colleagues","Stop working"],1),
("Situational Judgment","A deadline is approaching but you cannot complete everything to the expected quality. What should you do?",["Submit poor-quality work silently","Communicate early, prioritize and agree on the next action","Disappear","Delete unfinished work"],1),
("Situational Judgment","You are asked to do something outside your authority. What should you do?",["Do it without checking","Verify authorization or escalate to the appropriate person","Ask a friend","Ignore company policy"],1),
("Customer & Communication","A customer is angry about a delay. What is the strongest response?",["Argue","Acknowledge the concern, explain the next step and provide a realistic update","Tell them to wait","End the interaction"],1),
("Customer & Communication","Which is the most professional sentence?",["I don't know, ask someone else.","This isn't my problem.","I'll verify that information and get back to you with an update.","You need to wait."],2),
("Customer & Communication","A customer asks for an exception that policy does not allow. What should you do?",["Promise it anyway","Explain the policy clearly and offer any permitted alternatives","Blame the company","Ignore the request"],1),
("Customer & Communication","You cannot solve an issue during the first interaction. What is important?",["Close it quickly","Set expectations, document the issue and explain the next step","Transfer without context","Ask the customer to call again"],1),
("Customer & Communication","A customer provides information that conflicts with system records. What should you do?",["Assume the customer is wrong","Verify the relevant records and ask clarifying questions","Change the record immediately","Ignore both"],1),
("Customer & Communication","Which communication style is best for a difficult customer?",["Defensive","Calm, clear, respectful and solution-focused","Sarcastic","Very informal"],1),
("Customer & Communication","A customer asks the same question twice because they did not understand. What should you do?",["Repeat the same sentence louder","Explain it more clearly using simple language","End the interaction","Blame the customer"],1),
("Customer & Communication","You discover that a previous agent gave incorrect information. What should you do?",["Hide it","Correct the information professionally and document the appropriate update","Blame the agent to the customer","Ignore it"],1),
("Data & Accuracy","A team handled 100 cases Monday and 120 Tuesday. What was the increase?",["10%","20%","25%","30%"],1),
("Data & Accuracy","500 records contain 25 errors. What percentage contain errors?",["2%","5%","10%","25%"],1),
("Data & Accuracy","Five employees each handle 20 cases. Total cases?",["50","80","100","120"],2),
("Data & Accuracy","A ₹1,000 amount is reduced by 10%. What remains?",["₹900","₹910","₹990","₹1,100"],0),
("Data & Accuracy","A report has 200 cases. 50 are pending. What percentage are pending?",["15%","20%","25%","30%"],2),
("Data & Accuracy","You completed 72 tasks out of 80. What is your completion rate?",["80%","85%","90%","95%"],2),
("Data & Accuracy","A process takes 10 minutes per case. How long for 6 cases?",["30 minutes","50 minutes","60 minutes","70 minutes"],2),
("Data & Accuracy","A team processed 150 cases and 30 required review. What percentage required review?",["10%","15%","20%","30%"],2),
("Risk & Compliance","A transaction looks unusual but you have only one data point. What is the best approach?",["Immediately label it fraud","Review relevant evidence and transaction history before deciding","Approve it automatically","Close the case"],1),
("Risk & Compliance","You see confidential customer data in an unofficial group chat. What should you do?",["Forward it","Follow the approved security/reporting process and avoid further sharing","Save it personally","Ignore it"],1),
("Risk & Compliance","A colleague asks for your login credentials to complete a task. What should you do?",["Share them","Refuse and use approved access procedures","Send a screenshot of the password","Post it privately"],1),
("Risk & Compliance","A customer claims an unauthorized transaction. What should be prioritized?",["Assume fraud","Follow the approved verification and investigation process","Refund without checks","Ignore the claim"],1),
("Risk & Compliance","Why is documentation important in investigations?",["It makes work slower","It provides an evidence trail and supports consistent decisions","It is only for managers","It replaces investigation"],1),
("Risk & Compliance","You identify a potential policy breach but are not certain. What should you do?",["Accuse the person","Document facts and escalate/verify according to the process","Delete the evidence","Ignore it"],1),
("Risk & Compliance","What best demonstrates compliance?",["Doing what seems fastest","Following approved policies and documenting exceptions appropriately","Making personal exceptions","Avoiding difficult cases"],1),
("Risk & Compliance","You notice a pattern that may indicate a recurring operational risk. What should you do?",["Ignore it","Document the pattern and raise it through the appropriate channel","Post it publicly","Change the policy yourself"],1)
]

def conn():
    if not DATABASE_URL: raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL,sslmode="require",row_factory=dict_row)
def init():
    c=conn();c.execute("""CREATE TABLE IF NOT EXISTS candidates(
    id BIGSERIAL PRIMARY KEY,token TEXT UNIQUE,name TEXT,email TEXT,role TEXT,intro TEXT,
    intro_score INTEGER,mcq_correct INTEGER,mcq_score INTEGER,overall INTEGER,
    recommendation TEXT,submitted_at TEXT)""");c.commit();c.close()
init()

CSS="""<style>
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#173b57,#07111f 40%,#040a12);color:#edf6ff;font-family:Inter,system-ui,Arial}.wrap{max-width:1050px;margin:auto;padding:18px}.panel{background:#0b1b2dcc;border:1px solid #20354d;border-radius:20px;padding:25px;margin:18px 0;box-shadow:0 20px 60px #0006}.brand{font-weight:900;font-size:20px}.muted{color:#8fa3b9}.pill{display:inline-block;border:1px solid #29415a;border-radius:99px;padding:7px 10px;font-size:11px;color:#9fb2c7;font-weight:800}.hero h1{font-size:48px;line-height:1.05}.accent{color:#55ddb0}.btn{display:inline-block;padding:12px 16px;border-radius:11px;text-decoration:none;font-weight:800;border:0;cursor:pointer}.primary{background:#55ddb0;color:#06101d}.ghost{background:#12263b;color:#fff}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;color:#cbd7e4;font-size:13px;margin:10px 0}input,textarea{width:100%;padding:12px;margin-top:6px;background:#071321;border:1px solid #20354d;border-radius:10px;color:#fff}.q{padding:18px 0;border-bottom:1px solid #20354d}.option{padding:11px;border:1px solid #20354d;border-radius:10px;margin:8px 0;cursor:pointer}.section{color:#55ddb0;font-size:11px;font-weight:900}.timer{position:sticky;top:10px;background:#081522;border:1px solid #20354d;padding:12px;border-radius:10px;text-align:right;color:#55ddb0;font-weight:900}.big{font-size:70px;color:#55ddb0;font-weight:900}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{padding:17px;border:1px solid #20354d;border-radius:14px}.table{overflow:auto}table{width:100%;border-collapse:collapse;min-width:760px}th,td{text-align:left;padding:11px;border-bottom:1px solid #20354d;font-size:13px}th{color:#8fa3b9}@media(max-width:700px){.grid,.cards{grid-template-columns:1fr}.hero h1{font-size:38px}}
</style>"""

BASE="""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>BASOYF Talent Assessment</title>"""+CSS+"""</head><body><div class='wrap'><div class='brand'>BASOYF Talent <span class='muted'>| Professional Assessment</span></div>"""

HOME=BASE+"""<div class='panel hero'><span class='pill'>MNC SCREENING • 40 MCQs + INTRODUCTION</span><h1>Assess <span class='accent'>potential</span>, not memorisation.</h1><p class='muted'>A premium, simple assessment for logical thinking, workplace judgement, customer communication, data accuracy and risk awareness.</p><p><a class='btn primary' href='/test'>Start Candidate Test</a> <a class='btn ghost' href='/admin'>Recruiter Dashboard</a></p><div class='cards'><div class='card'><b>40</b><br><span class='muted'>MCQs</span></div><div class='card'><b>100</b><br><span class='muted'>Maximum score</span></div><div class='card'><b>38m</b><br><span class='muted'>Time limit</span></div></div></div></div></body></html>"""

def candidate_html():
    qs=""
    for i,q in enumerate(Q):
        opts="".join(f"<label class='option'><input type='radio' name='q{i}' value='{j}' required> {'ABCD'[j]}. {o}</label>" for j,o in enumerate(q[2]))
        qs+=f"<div class='q'><span class='section'>{q[0]}</span><p><b>{i+1}. {q[1]}</b></p>{opts}</div>"
    return BASE+f"""<form class='panel' method='post' id='f'><div class='timer' id='t'>38:00</div><h1>Professional Assessment</h1><div class='grid'><label>Full name<input name='name' required></label><label>Email<input type='email' name='email' required></label><label>Role<input name='role'></label><label>Assessment ID<input name='assessment_id'></label></div><div class='panel'><h2>Introduction</h2><p>Introduce yourself, summarise your professional experience and strongest skills, and explain why you would be suitable for an MNC environment.</p><textarea name='intro' rows='7' required></textarea></div>{qs}<button class='btn primary' type='submit'>Submit Assessment</button></form><script>let s=2280;setInterval(()=>{{s--;let m=Math.floor(s/60),x=s%60;document.getElementById('t').textContent=String(m).padStart(2,'0')+':'+String(x).padStart(2,'0');if(s<=0)document.getElementById('f').submit()}},1000)</script></div></body></html>"""

@app.route("/")
def home(): return HOME

@app.route("/test",methods=["GET","POST"])
def test():
    if request.method=="GET": return candidate_html()
    name=request.form["name"].strip();email=request.form["email"].strip();role=request.form.get("role","").strip() or "Not specified";intro=request.form["intro"].strip()
    correct=sum(1 for i,q in enumerate(Q) if request.form.get(f"q{i}") and int(request.form[f"q{i}"])==q[3])
    words=len(intro.split()); intro_score=20 if 100<=words<=220 else 15 if words>=60 else 10 if words>=30 else 5
    mcq_score=round(correct/40*80);overall=mcq_score+intro_score;rec="Strong Candidate" if overall>=80 else "Potential Candidate" if overall>=65 else "Needs Further Review";token=secrets.token_urlsafe(10)
    c=conn();c.execute("""INSERT INTO candidates(token,name,email,role,intro,intro_score,mcq_correct,mcq_score,overall,recommendation,submitted_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(token,name,email,role,intro,intro_score,correct,mcq_score,overall,rec,datetime.now().strftime("%Y-%m-%d %H:%M:%S")));c.commit();c.close()
    return redirect("/result/"+token)

@app.route("/result/<token>")
def result(token):
    c=conn();r=c.execute("SELECT * FROM candidates WHERE token=%s",(token,)).fetchone();c.close()
    if not r: abort(404)
    return BASE+f"""<div class='panel' style='text-align:center'><span class='pill'>ASSESSMENT COMPLETE</span><h1>{r['name']}</h1><div class='big'>{r['overall']}/100</div><h2>{r['recommendation']}</h2><div class='cards'><div class='card'><b>{r['mcq_correct']}/40</b><br><span class='muted'>MCQ Correct</span></div><div class='card'><b>{r['mcq_score']}/80</b><br><span class='muted'>MCQ Score</span></div><div class='card'><b>{r['intro_score']}/20</b><br><span class='muted'>Introduction</span></div></div><p class='muted'>Your assessment has been submitted successfully.</p><a class='btn primary' href='/'>Finish</a></div></div></body></html>"""

@app.route("/admin",methods=["GET","POST"])
def admin():
    if request.method=="POST":
        if request.form.get("pin")==ADMIN_PIN: session["admin"]=True
        else: return BASE+"<div class='panel'><h2>Incorrect PIN</h2><a href='/admin'>Try again</a></div></div></body></html>"
    if not session.get("admin"): return BASE+"<div class='panel'><h1>Recruiter Login</h1><p class='muted'>Enter your private recruiter PIN.</p><form method='post'><input type='password' name='pin' required><br><br><button class='btn primary'>Open Dashboard</button></form></div></div></body></html>"
    c=conn();rows=c.execute("SELECT * FROM candidates ORDER BY id DESC").fetchall();c.close();avg=round(sum(x["overall"] for x in rows)/len(rows)) if rows else 0;strong=sum(x["overall"]>=80 for x in rows)
    tr="".join(f"<tr><td>{x['name']}<br><small>{x['email']}</small></td><td>{x['role']}</td><td>{x['mcq_correct']}/40</td><td>{x['intro_score']}/20</td><td><b>{x['overall']}/100</b></td><td>{x['recommendation']}</td><td>{x['submitted_at']}</td></tr>" for x in rows)
    return BASE+f"""<div class='panel'><h1>Recruiter Dashboard</h1><div class='cards'><div class='card'><b>{len(rows)}</b><br><span class='muted'>Assessments</span></div><div class='card'><b>{strong}</b><br><span class='muted'>Strong Candidates</span></div><div class='card'><b>{avg}</b><br><span class='muted'>Average Score</span></div></div><p><a class='btn primary' href='/export.csv'>Export CSV</a></p><div class='table'><table><tr><th>Candidate</th><th>Role</th><th>MCQ</th><th>Intro</th><th>Overall</th><th>Recommendation</th><th>Date</th></tr>{tr}</table></div></div></div></body></html>"""

@app.route("/export.csv")
def export():
    if not session.get("admin"): abort(403)
    c=conn();rows=c.execute("SELECT name,email,role,submitted_at,mcq_correct,mcq_score,intro_score,overall,recommendation FROM candidates ORDER BY id DESC").fetchall();c.close()
    out=io.StringIO();w=csv.writer(out);w.writerow(["Candidate","Email","Role","Submitted","MCQ Correct","MCQ Score","Introduction","Overall","Recommendation"])
    for r in rows:w.writerow(list(r.values()))
    b=io.BytesIO(out.getvalue().encode());b.seek(0);return send_file(b,mimetype="text/csv",as_attachment=True,download_name="basoyf_candidates.csv")

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
