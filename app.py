
# app.py
import os, json, time, hashlib, secrets, datetime, sqlite3
from contextlib import closing
from flask import (
    Flask, request, session, redirect, url_for, flash,
    Response, render_template_string, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
DB_PATH = os.environ.get("DB_PATH", "nexusmed.db")

# -------------------------------------------------
# DB SETUP
# -------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(get_db()) as db:
        cur = db.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            pwd_hash TEXT NOT NULL,
            verified INTEGER DEFAULT 0,
            verify_token TEXT
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            data_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );""")
        db.commit()

def find_user_by_email(email):
    with closing(get_db()) as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
        return cur.fetchone()

def create_user(email, pwd_hash, token):
    with closing(get_db()) as db:
        cur = db.cursor()
        cur.execute("INSERT INTO users (email, pwd_hash, verify_token) VALUES (?,?,?)",
                    (email.lower(), pwd_hash, token))
        user_id = cur.lastrowid
        cur.execute("INSERT INTO profiles (user_id, data_json, updated_at) VALUES (?,?,?)",
                    (user_id, json.dumps(default_profile()), datetime.datetime.utcnow().isoformat()))
        db.commit()
        return user_id

def get_profile(user_id):
    with closing(get_db()) as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return default_profile()
        return json.loads(row["data_json"])

def save_profile(user_id, data):
    with closing(get_db()) as db:
        cur = db.cursor()
        cur.execute("UPDATE profiles SET data_json=?, updated_at=? WHERE user_id=?",
                    (json.dumps(data), datetime.datetime.utcnow().isoformat(), user_id))
        db.commit()

def verify_user_by_token(token):
    with closing(get_db()) as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE verify_token = ?", (token,))
        user = cur.fetchone()
        if not user:
            return False
        cur.execute("UPDATE users SET verified=1, verify_token=NULL WHERE id=?", (user["id"],))
        db.commit()
        return True

# -------------------------------------------------
# DOMAIN / BUSINESS
# -------------------------------------------------
def default_profile():
    # Estructura pensada para: series temporales y "últimos valores".
    # Se guardan arrays (máx 12) para graficar y comparar.
    return {
        "series": {
            "peso": [],            # kg
            "imc": [],             # calculado
            "presion": [],         # strings "120/80"
            "glucosa": [],         # mg/dL
            "colesterol": [],      # mg/dL (total o LDL)
            "sueno": [],           # horas
            "actividad": []        # min/día
        },
        "last": {                 # últimos valores para inputs rápidos
            "peso": None,
            "altura": None,       # en metros
            "presion": None,      # "120/80"
            "glucosa": None,
            "colesterol": None,
            "sueno": None,
            "actividad": None
        },
        "predicciones": {
            "diabetes": None,
            "hipertension": None,
            "cardio": None,
            "obesidad": None,
            "osteoporosis": None,
            "alzheimer": None
        }
    }

def clamp_series(arr, maxlen=12):
    if len(arr) > maxlen:
        return arr[-maxlen:]
    return arr

def parse_bp(bp_str):
    # Retorna (sistolica, diastolica) con tolerancia
    if not bp_str:
        return (None, None)
    try:
        parts = bp_str.replace(" ", "").split("/")
        if len(parts) != 2:
            return (None, None)
        s = int(''.join([c for c in parts[0] if c.isdigit()]))
        d = int(''.join([c for c in parts[1] if c.isdigit()]))
        return (s, d)
    except Exception:
        return (None, None)

def compute_imc(peso, altura):
    try:
        p = float(peso)
        a = float(altura)
        if p > 0 and a > 0:
            return round(p/(a*a), 1)
    except:
        pass
    return None

def risk_model(profile):
    """
    Modelo de riesgo heurístico, solo demostrativo.
    Usa últimos valores válidos si existen; si faltan, usa promedios simples.
    Devuelve % como strings "NN%".
    """
    last = profile["last"]
    series = profile["series"]
    def last_or_avg(key):
        lv = last.get(key)
        if lv is not None and lv != "":
            return lv
        arr = series.get(key, [])
        if arr:
            return sum([float(x) for x in arr if str(x).replace('.', '', 1).isdigit()]) / max(1, len(arr))
        return None

    peso = last_or_avg("peso")
    altura = last.get("altura")
    imc = compute_imc(peso, altura) if peso and altura else None
    glucosa = last_or_avg("glucosa")
    colesterol = last_or_avg("colesterol")
    sueno = last_or_avg("sueno")
    actividad = last_or_avg("actividad")
    sist, diast = parse_bp(last.get("presion"))

    # Heurísticas
    risk = {
        "diabetes": 15,
        "hipertension": 15,
        "cardio": 15,
        "obesidad": 15,
        "osteoporosis": 10,
        "alzheimer": 8
    }

    if imc:
        if imc >= 30: risk["obesidad"] += 50; risk["diabetes"] += 25; risk["cardio"] += 20
        elif imc >= 25: risk["obesidad"] += 25; risk["diabetes"] += 10; risk["cardio"] += 10

    if glucosa:
        g = float(glucosa)
        if g >= 126: risk["diabetes"] += 40; risk["cardio"] += 10
        elif g >= 110: risk["diabetes"] += 20

    if colesterol:
        c = float(colesterol)
        if c >= 240: risk["cardio"] += 30
        elif c >= 200: risk["cardio"] += 15

    if sist and diast:
        if sist >= 140 or diast >= 90: risk["hipertension"] += 40; risk["cardio"] += 20
        elif sist >= 130 or diast >= 85: risk["hipertension"] += 20

    if sueno is not None:
        s = float(sueno)
        if s < 6: risk["cardio"] += 10; risk["alzheimer"] += 10
        elif s < 7: risk["cardio"] += 5

    if actividad is not None:
        a = float(actividad)
        if a < 30: risk["cardio"] += 10; risk["diabetes"] += 10
        elif a < 60: risk["cardio"] += 5

    # Bound [5, 95]
    for k in risk:
        risk[k] = max(5, min(95, risk[k]))

    # Guardar en perfil
    for k, v in risk.items():
        profile["predicciones"][k] = f"{v}%"

    return profile["predicciones"]

def profile_completion(profile):
    # Progreso: cuantos "last" están completos + al menos 3 series con datos
    last = profile["last"]
    filled = sum(1 for k, v in last.items() if v not in (None, "", []))
    base = int((filled / len(last)) * 80)
    series_count = sum(1 for k, arr in profile["series"].items() if len(arr) >= 3)
    bonus = min(20, series_count * 5)
    return min(100, base + bonus)

def generate_verify_token(email):
    salt = secrets.token_hex(8)
    raw = f"{email}-{salt}-{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()

# -------------------------------------------------
# TEMPLATES (base + páginas)
# -------------------------------------------------
BASE_HEAD = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NEXUSMED</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root{
  --bg: #0b0e14; --card:#111827; --muted:#6b7280;
  --accent:#06b6d4; --accent-2:#3b82f6; --text:#e5e7eb; --danger:#ef4444; --ok:#10b981; --warn:#f59e0b;
}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI; background:var(--bg); color:var(--text);}
a{color:var(--accent-2); text-decoration:none}
.container{max-width:1100px; margin:0 auto; padding:20px;}
.nav{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:rgba(255,255,255,0.02);backdrop-filter: blur(4px); position:sticky; top:0; border-bottom:1px solid rgba(255,255,255,0.06)}
.brand{display:flex; gap:10px; align-items:center}
.logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,var(--accent),var(--accent-2)); display:flex; align-items:center; justify-content:center; font-weight:800}
h1,h2,h3{margin:0 0 10px 0}
.card{background:var(--card); border:1px solid rgba(255,255,255,0.06); border-radius:18px; padding:20px; box-shadow:0 10px 30px rgba(0,0,0,.25);}
.grid{display:grid; gap:18px}
.grid-2{grid-template-columns:1fr 1fr}
.grid-3{grid-template-columns:repeat(3,1fr)}
.btn{background:linear-gradient(135deg,var(--accent),var(--accent-2)); color:white; padding:12px 18px;border:none;border-radius:12px;cursor:pointer;font-weight:600}
.btn.secondary{background:none;border:1px solid rgba(255,255,255,0.16)}
.input{background:#0f172a;border:1px solid rgba(255,255,255,0.08); padding:12px;border-radius:10px;color:var(--text);width:100%}
.kv{display:grid; grid-template-columns:160px 1fr; gap:12px; align-items:center}
.badge{display:inline-block;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,0.08);font-size:.85rem}
.toast{position:fixed; right:20px; bottom:20px; background:#111827; border:1px solid rgba(255,255,255,0.1); padding:14px 16px; border-radius:12px; display:none}
.progress{background:#0f172a;border:1px solid rgba(255,255,255,0.1); height:12px; border-radius:999px; overflow:hidden}
.progress>span{display:block; height:100%; background:linear-gradient(90deg,var(--accent),var(--accent-2))}
footer{color:var(--muted); text-align:center; padding:30px 12px}
hr{border:none;border-top:1px solid rgba(255,255,255,0.08); margin:18px 0}
@media(max-width:900px){.grid-2,.grid-3{grid-template-columns:1fr}}
/* Splash */
.splash{position:fixed; inset:0; display:flex; align-items:center; justify-content:center; background:radial-gradient(60% 60% at 50% 40%, #0b0e14 0%, #05070a 100%); z-index:9999}
.splash .logo{width:64px;height:64px; font-size:1.1rem}
.splash h1{margin-top:12px; letter-spacing:3px}
.spinner{margin-top:16px;width:36px;height:36px;border:3px solid rgba(255,255,255,0.15);border-top-color:var(--accent); border-radius:50%; animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.alert{padding:10px 12px;border-radius:10px;margin:8px 0}
.alert.ok{background:rgba(16,185,129,.12); border:1px solid rgba(16,185,129,.4)}
.alert.warn{background:rgba(245,158,11,.12); border:1px solid rgba(245,158,11,.4)}
.alert.danger{background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.4)}
small.muted{color:var(--muted)}
.toggle{cursor:pointer}
</style>
"""

LAYOUT = """
<!DOCTYPE html>
<html lang="es">
<head>
{{ head|safe }}
</head>
<body>
<div class="splash" id="splash">
  <div style="text-align:center">
    <div class="logo">NM</div>
    <h1>NEXUSMED</h1>
    <div class="spinner"></div>
    <small class="muted">Cuidando tu salud con datos</small>
  </div>
</div>

<nav class="nav">
  <div class="brand">
    <div class="logo">NM</div>
    <div>
      <strong>NEXUSMED</strong><br>
      <small class="muted">Expediente médico digital & IA</small>
    </div>
  </div>
  <div>
    {% if session.get('uid') %}
      <a class="btn secondary" href="{{ url_for('dashboard') }}">Dashboard</a>
      <a class="btn secondary" href="{{ url_for('logout') }}">Salir</a>
    {% else %}
      <a class="btn secondary" href="{{ url_for('login') }}">Entrar</a>
      <a class="btn" href="{{ url_for('register') }}">Crear cuenta</a>
    {% endif %}
  </div>
</nav>

<div class="container">
  {% with msgs = get_flashed_messages() %}
    {% if msgs %}{% for m in msgs %}
      <div class="alert ok">{{ m }}</div>
    {% endfor %}{% endif %}
  {% endwith %}
  {{ body|safe }}
</div>

<footer>
  Tus datos están cifrados en tránsito (HTTPS). Este sitio es un MVP con fines informativos.
  <br><a href="{{ url_for('legal_privacy') }}">Política de privacidad</a> • <a href="{{ url_for('legal_terms') }}">Términos</a>
</footer>

<div class="toast" id="toast"></div>

<script>
// Splash
window.addEventListener('load', ()=> {
  setTimeout(()=> document.getElementById('splash').style.display='none', 800);
});
function showToast(msg){
  const t=document.getElementById('toast'); t.textContent=msg; t.style.display='block';
  setTimeout(()=> t.style.display='none', 4200);
}
</script>
</body>
</html>
"""

def page(head_extra, body_html):
    return render_template_string(LAYOUT, head=BASE_HEAD + (head_extra or ""), body=body_html)

# ---------------- Landing ----------------
@app.route("/")
def landing():
    body = """
    <div class="grid grid-2">
      <div class="card">
        <h1>Tu historial médico, contigo</h1>
        <p class="muted">Centraliza consultas, laboratorios y hábitos. Obtén <strong>predicciones preventivas</strong> y <strong>alertas</strong> en tiempo real.</p>
        <div style="display:flex; gap:10px; margin-top:14px">
          <a class="btn" href="{{ url_for('register') }}">Crear cuenta</a>
          <a class="btn secondary" href="{{ url_for('login') }}">Entrar</a>
        </div>
        <hr>
        <div class="grid grid-3">
          <div><span class="badge">IA preventiva</span><br><small class="muted">Riesgos de diabetes, hipertensión y cardiovasculares</small></div>
          <div><span class="badge">Gráficas claras</span><br><small class="muted">Peso, IMC, presión, glucosa, sueño y más</small></div>
          <div><span class="badge">Privado</span><br><small class="muted">Controlado por el paciente</small></div>
        </div>
      </div>
      <div class="card">
        <h3>Vista del dashboard</h3>
        <small class="muted">Gráficas y recomendaciones personalizadas</small>
        <canvas id="preview" height="120"></canvas>
      </div>
    </div>
    <script>
      const ctx = document.getElementById('preview').getContext('2d');
      new Chart(ctx,{type:'line',data:{labels:['Ene','Feb','Mar','Abr','May','Jun'],
        datasets:[{label:'IMC',data:[26,26.3,26.1,25.9,25.7,25.4],borderWidth:2,fill:false}]},
        options:{responsive:true}});
    </script>
    """
    return page("", body)

# ---------------- Auth ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not email or not password:
            flash("Completa todos los campos.")
            return redirect(url_for("login"))
        user = find_user_by_email(email)
        if not user or not check_password_hash(user["pwd_hash"], password):
            flash("Credenciales incorrectas.")
            return redirect(url_for("login"))
        if not user["verified"]:
            flash("Tu cuenta no está verificada. Revisa tu correo (simulado) y haz clic en el enlace.")
            return redirect(url_for("resend_verification", email=email))
        session["uid"] = user["id"]
        session["email"] = email
        flash("Bienvenido a NEXUSMED.")
        return redirect(url_for("dashboard"))

    body = """
    <div class="grid" style="max-width:520px; margin:0 auto">
      <div class="card">
        <h2>Iniciar sesión</h2>
        <form method="POST" class="grid">
          <div class="kv"><label>Correo</label><input class="input" type="email" name="email" required></div>
          <div class="kv"><label>Contraseña</label><input class="input" type="password" name="password" required></div>
          <div style="display:flex; gap:10px; justify-content:flex-end">
            <button class="btn secondary" type="button" onclick="location.href='{{ url_for('register') }}'">Crear cuenta</button>
            <button class="btn" type="submit">Entrar</button>
          </div>
        </form>
        <hr>
        <small class="muted">¿Olvidaste la contraseña? (próximamente)</small>
      </div>
    </div>
    """
    return page("", body)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        confirm = request.form.get("confirm","")
        if not email or not password:
            flash("Completa todos los campos.")
            return redirect(url_for("register"))
        if password != confirm:
            flash("Las contraseñas no coinciden.")
            return redirect(url_for("register"))
        if find_user_by_email(email):
            flash("Este correo ya está registrado.")
            return redirect(url_for("register"))
        token = generate_verify_token(email)
        create_user(email, generate_password_hash(password), token)
        verify_link = url_for("verify", token=token, _external=True)
        # Simulación de envío de email:
        print(f"[EMAIL SIMULADO] Bienvenido a NEXUSMED, {email}. Verifica tu cuenta: {verify_link}")
        flash(f"¡Registro exitoso! Te enviamos un correo de verificación (simulado). También puedes verificar aquí abajo.")
        return redirect(url_for("resend_verification", email=email))

    body = """
    <div class="grid" style="max-width:560px; margin:0 auto">
      <div class="card">
        <h2>Crear cuenta</h2>
        <form method="POST" class="grid">
          <div class="kv"><label>Correo</label><input class="input" type="email" name="email" required></div>
          <div class="kv"><label>Contraseña</label><input class="input" type="password" name="password" required></div>
          <div class="kv"><label>Confirmar</label><input class="input" type="password" name="confirm" required></div>
          <div style="display:flex; gap:10px; justify-content:flex-end">
            <button class="btn secondary" type="button" onclick="location.href='{{ url_for('login') }}'">Ya tengo cuenta</button>
            <button class="btn" type="submit">Registrarme</button>
          </div>
        </form>
        <hr>
        <small class="muted">Al registrarte aceptas los <a href="{{ url_for('legal_terms') }}">Términos</a> y la <a href="{{ url_for('legal_privacy') }}">Privacidad</a>.</small>
      </div>
    </div>
    """
    return page("", body)

@app.route("/verify/<token>")
def verify(token):
    if verify_user_by_token(token):
        flash("Cuenta verificada. Ya puedes iniciar sesión.")
        return redirect(url_for("login"))
    flash("Enlace inválido o expirado.")
    return redirect(url_for("register"))

@app.route("/resend-verification")
def resend_verification():
    email = request.args.get("email","").lower()
    user = find_user_by_email(email) if email else None
    link = None
    if user and user["verify_token"]:
        link = url_for("verify", token=user["verify_token"], _external=True)
    elif user and not user["verify_token"] and not user["verified"]:
        # genera uno nuevo
        token = generate_verify_token(email)
        with closing(get_db()) as db:
            cur = db.cursor()
            cur.execute("UPDATE users SET verify_token=? WHERE id=?", (token, user["id"]))
            db.commit()
        link = url_for("verify", token=token, _external=True)

    body = f"""
    <div class="card">
      <h2>Verifica tu cuenta</h2>
      <p>Hemos (simulado) el envío de un correo a <strong>{email}</strong> con tu enlace de verificación.</p>
      {"<p><strong>Enlace directo:</strong> <a href='"+link+"'>"+link+"</a></p>" if link else "<p>No encontramos enlace activo. Intenta registrarte de nuevo.</p>"}
      <p class="muted">*Simulación: en producción configurar SMTP o un servicio de email.</p>
      <div style="margin-top:10px">
        <a class="btn" href="{{ url_for('login') }}">Ir a iniciar sesión</a>
      </div>
    </div>
    """
    return page("", body)

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.")
    return redirect(url_for("landing"))

# ---------------- Dashboard ----------------
@app.route("/dashboard")
def dashboard():
    if not session.get("uid"):
        flash("Inicia sesión primero.")
        return redirect(url_for("login"))

    uid = session["uid"]
    email = session["email"]
    profile = get_profile(uid)

    # recalcular IMC si hay peso/altura recientes
    imc_val = None
    if profile["last"]["peso"] and profile["last"]["altura"]:
        imc_val = compute_imc(profile["last"]["peso"], profile["last"]["altura"])
        if imc_val:
            profile["last"]["imc"] = imc_val
            profile["series"]["imc"] = clamp_series(profile["series"]["imc"] + [imc_val])

    # predicciones
    preds = risk_model(profile)
    save_profile(uid, profile)

    # progreso
    progress = profile_completion(profile)

    # tips básicos dinámicos
    tips = []
    if imc_val and imc_val >= 25: tips.append("Ajusta tu ingesta calórica y suma 30–45 min de actividad al día.")
    if profile["last"]["glucosa"] and float(profile["last"]["glucosa"]) >= 110: tips.append("Controla azúcares simples y prioriza fibra.")
    if profile["last"]["colesterol"] and float(profile["last"]["colesterol"]) >= 200: tips.append("Prioriza grasas insaturadas y revisa con tu médico.")
    sist, diast = parse_bp(profile["last"]["presion"])
    if (sist and sist >= 130) or (diast and diast >= 85): tips.append("Reduce sodio, evita alcohol en exceso, realiza ejercicio regular.")
    if not tips: tips = ["¡Buen trabajo! Mantén hábitos saludables.", "Hidrátate bien durante el día.", "Procura 7–8 horas de sueño."]

    # construir HTML del dashboard
    head = """
    <script>
    // SSE de alertas
    document.addEventListener('DOMContentLoaded', ()=>{
      try{
        const ev = new EventSource('/alerts');
        ev.onmessage = (e)=>{
          const data = JSON.parse(e.data);
          if(data && data.msg){ showToast(data.msg); }
        }
      }catch(e){}
    });
    </script>
    """
    body = render_dashboard_html(email, profile, preds, progress, tips)
    return page(head, body)

def render_dashboard_html(email, profile, preds, progress, tips):
    # Utilidades para inyectar series con fallback
    def js_arr(key, fallback):
        arr = profile["series"].get(key) or []
        if not arr:
            arr = fallback
        return json.dumps(arr)

    def js_bp_sistolica():
        arr = profile["series"].get("presion") or []
        if not arr:
            arr = ["120/80","124/82","132/86","128/84","125/83"]
        # convertir a sistólica
        vals = []
        for p in arr:
            s, d = parse_bp(p)
            if s is not None: vals.append(s)
        if not vals:
            vals = [120,124,132,128,125]
        return json.dumps(vals)

    # última altura
    altura = profile["last"].get("altura") or ""

    preds_list = [
        ("Diabetes", preds.get("diabetes","-")),
        ("Hipertensión", preds.get("hipertension","-")),
        ("Cardiovascular", preds.get("cardio","-")),
        ("Obesidad", preds.get("obesidad","-")),
        ("Osteoporosis", preds.get("osteoporosis","-")),
        ("Alzheimer", preds.get("alzheimer","-"))
    ]

    risks_for_radar = [int(preds.get(k,"%0").strip("%") or 0) for k in ["diabetes","hipertension","cardio","obesidad","osteoporosis","alzheimer"]]
    risks_for_radar = [max(5,min(95,x)) for x in risks_for_radar]

    html = f"""
    <div class="grid grid-2">
      <div class="card">
        <h2>Hola, {email}</h2>
        <div class="kv"><label>Progreso de perfil</label>
          <div class="progress" style="width:100%"><span style="width:{progress}%"></span></div>
        </div>
        <small class="muted">Completa y actualiza tus datos para predicciones más precisas.</small>
      </div>

      <div class="card">
        <h3>Predicciones preventivas</h3>
        <div class="grid grid-3">
          {''.join([f"<div><span class='badge'>{k}</span><br><strong>{v}</strong></div>" for k,v in preds_list])}
        </div>
        <hr>
        <canvas id="radarRisk" height="120"></canvas>
      </div>
    </div>

    <div class="card">
      <h3>Actualizar datos</h3>
      <form method="POST" action="{url_for('update_medical')}" class="grid grid-3">
        <div><label>Peso (kg)</label><input class="input" type="number" step="0.1" name="peso" value="{profile['last'].get('peso') or ''}"></div>
        <div><label>Altura (m)</label><input class="input" type="number" step="0.01" name="altura" value="{altura}"></div>
        <div><label>Presión (mmHg)</label><input class="input" type="text" name="presion" placeholder="120/80" value="{profile['last'].get('presion') or ''}"></div>
        <div><label>Glucosa (mg/dL)</label><input class="input" type="number" name="glucosa" value="{profile['last'].get('glucosa') or ''}"></div>
        <div><label>Colesterol (mg/dL)</label><input class="input" type="number" name="colesterol" value="{profile['last'].get('colesterol') or ''}"></div>
        <div><label>Sueño (h)</label><input class="input" type="number" name="sueno" value="{profile['last'].get('sueno') or ''}"></div>
        <div><label>Actividad (min/día)</label><input class="input" type="number" name="actividad" value="{profile['last'].get('actividad') or ''}"></div>
        <div style="grid-column:1/-1; display:flex; gap:10px; justify-content:flex-end">
          <button class="btn secondary" type="button" onclick="location.reload()">Cancelar</button>
          <button class="btn" type="submit">Guardar</button>
        </div>
      </form>
      <small class="muted">* Los datos no sustituyen la consulta médica.</small>
    </div>

    <div class="grid grid-2">
      <div class="card">
        <h3>Evolución personal</h3>
        <canvas id="pesoChart" height="100"></canvas>
        <canvas id="bpChart" height="100"></canvas>
        <canvas id="glucosaChart" height="100"></canvas>
      </div>
      <div class="card">
        <h3>Hábitos & laboratorio</h3>
        <canvas id="colChart" height="100"></canvas>
        <canvas id="suenoChart" height="100"></canvas>
        <canvas id="actChart" height="100"></canvas>
      </div>
    </div>

    <div class="card">
      <h3>Tips personalizados</h3>
      <ul>
        {''.join([f"<li>{t}</li>" for t in tips])}
      </ul>
    </div>

    <script>
    // Radar de riesgos
    new Chart(document.getElementById('radarRisk').getContext('2d'), {{
      type:'radar',
      data: {{
        labels: ['Diabetes','HTA','Cardio','Obesidad','Osteoporosis','Alzheimer'],
        datasets: [{{ label:'Riesgo %', data:{json.dumps(risks_for_radar)}, borderWidth:1, fill:true }}]
      }},
      options: {{ responsive:true, scales: {{ r: {{ suggestedMin:0, suggestedMax:100 }} }} }}
    }});

    // Series (con fallback)
    const peso = {js_arr('peso', [70,71,71.5,72,71,70.5])};
    const imc  = {js_arr('imc', [26.4,26.2,26.0,25.8,25.7,25.5])};
    const bp_sis = {js_bp_sistolica()};
    const gluc = {js_arr('glucosa', [95,98,102,96,93,90])};
    const col  = {js_arr('colesterol', [185,190,210,198,192,188])};
    const zz   = (x)=>({{labels:['Ene','Feb','Mar','Abr','May','Jun'].slice(-x.length), datasets:[{{label:'Valor', data:x, borderWidth:2, fill:false}}]}});
    const makeLine = (id, data, lbl) => new Chart(document.getElementById(id).getContext('2d'), {{type:'line', data: zz(data), options:{{plugins:{{legend:{{display:true}}}}}}}});
    makeLine('pesoChart', peso, 'Peso');
    makeLine('bpChart', bp_sis, 'Presión sistólica');
    makeLine('glucosaChart', gluc, 'Glucosa');
    makeLine('colChart', col, 'Colesterol');
    makeLine('suenoChart', {js_arr('sueno', [7,6.5,7.2,7.8,7.0,6.9])}, 'Sueño');
    makeLine('actChart', {js_arr('actividad', [35,40,55,60,45,50])}, 'Actividad');

    </script>
    """
    return html

# -------- Update Medical --------
@app.route("/update-medical", methods=["POST"])
def update_medical():
    if not session.get("uid"):
        return redirect(url_for("login"))
    uid = session["uid"]
    profile = get_profile(uid)

    fields = ["peso","altura","presion","glucosa","colesterol","sueno","actividad"]
    for f in fields:
        val = request.form.get(f, "").strip()
        if val != "":
            # normalizar claves
            key = "sueno" if f == "sueno" else f
            profile["last"][key] = val

            # actualizar series si aplica (no altura/presión? presión también serie)
            if key in ["peso","glucosa","colesterol","sueno","actividad"]:
                try:
                    profile["series"][key] = clamp_series(profile["series"].get(key, []) + [float(val)])
                except:
                    pass
            elif key == "presion":
                profile["series"]["presion"] = clamp_series(profile["series"].get("presion", []) + [val])

    # recalcular IMC y serie
    if profile["last"]["peso"] and profile["last"]["altura"]:
        imc_val = compute_imc(profile["last"]["peso"], profile["last"]["altura"])
        if imc_val:
            profile["series"]["imc"] = clamp_series(profile["series"]["imc"] + [imc_val])
            profile["last"]["imc"] = imc_val

    save_profile(uid, profile)
    flash("Datos médicos actualizados.")
    return redirect(url_for("dashboard"))

# -------- SSE Alerts --------
@app.route("/alerts")
def alerts():
    if not session.get("uid"):
        abort(401)
    uid = session["uid"]
    def stream():
        # En un MVP, empuja una alerta inmediata según últimos datos
        profile = get_profile(uid)
        msg = None
        sist, diast = parse_bp(profile["last"].get("presion"))
        if sist and (sist >= 140 or (diast and diast >= 90)):
            msg = "Alerta: Tu presión arterial está en rango alto. Considera medirla nuevamente y consultar a tu médico."
        elif profile["last"].get("glucosa") and float(profile["last"]["glucosa"]) >= 126:
            msg = "Alerta: Glucosa en ayunas elevada (≥126 mg/dL). Revisa con tu médico."
        elif profile["last"].get("colesterol") and float(profile["last"]["colesterol"]) >= 240:
            msg = "Alerta: Colesterol total alto (≥240 mg/dL). Considera intervención nutricional/médica."
        elif profile["last"].get("sueno") and float(profile["last"]["sueno"]) < 6:
            msg = "Nota: Sueño insuficiente (<6 h). Prioriza higiene del sueño."
        if msg:
            yield f"data: {json.dumps({'msg': msg})}\n\n"
        # Mantener la conexión viva (ping cada 20s)
        for _ in range(30):
            time.sleep(20)
            yield f"data: {json.dumps({'msg': ''})}\n\n"
    return Response(stream(), mimetype='text/event-stream')

# -------- Legal --------
@app.route("/legal/privacy")
def legal_privacy():
    body = """
    <div class="card">
      <h2>Política de privacidad</h2>
      <p>Protegemos tu información y no la compartimos sin tu consentimiento. Este MVP almacena datos localmente en SQLite.</p>
      <p>En producción, se aplicaría cifrado en reposo, segregación de datos y auditorías.</p>
    </div>
    """
    return page("", body)

@app.route("/legal/terms")
def legal_terms():
    body = """
    <div class="card">
      <h2>Términos de uso</h2>
      <p>Este servicio no sustituye la consulta médica profesional. Las predicciones son estimaciones basadas en datos ingresados por el usuario.</p>
    </div>
    """
    return page("", body)

# aliases cortos
legal_privacy = legal_privacy
legal_terms = legal_terms

# -------------------------------------------------
# MAIN
# -------------------------------------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
