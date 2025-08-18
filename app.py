# app.py
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime
import random
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ----------------------------
# DATABASE SIMULATION
# ----------------------------
users_db = {}  # email -> {password_hash, profile_completed, records:[], tips_seen}

# ----------------------------
# TEMPLATES
# ----------------------------
landing_template = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NEXUSMED</title>
<style>
body { font-family: Arial, sans-serif; background:#f9f9f9; margin:0; padding:0; }
header { background:#4a90e2; color:white; padding:40px; text-align:center; }
h1 { margin:0; font-size:2.5em; }
h3 { margin:10px 0 30px 0; font-weight:normal; }
.container { max-width:800px; margin:auto; padding:20px; text-align:center; }
.benefit { background:white; margin:10px; padding:20px; border-radius:10px; box-shadow:0 0 10px rgba(0,0,0,0.1); }
button { padding:15px 30px; background:#4a90e2; color:white; border:none; border-radius:5px; cursor:pointer; font-size:1em; }
button:hover { background:#357ab7; }
</style>
</head>
<body>
<header>
  <h1>NEXUSMED</h1>
  <h3>Tu historial médico digital seguro y predictivo</h3>
  <button onclick="window.location.href='/login'">Entrar</button>
</header>
<div class="container">
  <div class="benefit"><strong>Historial único:</strong> Toda tu información médica en un solo lugar.</div>
  <div class="benefit"><strong>Predicciones de salud:</strong> IA para prevenir enfermedades y crisis.</div>
  <div class="benefit"><strong>Alertas personalizadas:</strong> Recordatorios y tips diarios.</div>
  <div class="benefit"><strong>Gráficas visuales:</strong> Evolución de IMC, presión arterial, glucosa y más.</div>
</div>
</body>
</html>
"""

login_template = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login NEXUSMED</title>
<style>
body { font-family: Arial, sans-serif; background:#f2f2f2; display:flex; justify-content:center; align-items:center; height:100vh; }
form { background:white; padding:30px; border-radius:10px; box-shadow:0 0 15px rgba(0,0,0,0.2); width:100%; max-width:400px; }
input { width:100%; padding:10px; margin:10px 0; border-radius:5px; border:1px solid #ccc; }
button { padding:10px 20px; background:#4a90e2; color:white; border:none; border-radius:5px; cursor:pointer; width:100%; }
button:hover { background:#357ab7; }
.flash { color:red; text-align:center; }
</style>
</head>
<body>
<form method="POST">
  <h2 style="text-align:center;">Login NEXUSMED</h2>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for msg in messages %}
        <div class="flash">{{ msg }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  <input type="email" name="email" placeholder="Correo electrónico" required>
  <input type="password" name="password" placeholder="Contraseña" required>
  <button type="submit">Entrar</button>
  <p style="text-align:center;">¿No tienes cuenta? <a href="{{ url_for('register') }}">Registrarse</a></p>
</form>
</body>
</html>
"""

register_template = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Registro NEXUSMED</title>
<style>
body { font-family: Arial, sans-serif; background:#f2f2f2; display:flex; justify-content:center; align-items:center; height:100vh; }
form { background:white; padding:30px; border-radius:10px; box-shadow:0 0 15px rgba(0,0,0,0.2); width:100%; max-width:400px; }
input { width:100%; padding:10px; margin:10px 0; border-radius:5px; border:1px solid #ccc; }
button { padding:10px 20px; background:#4a90e2; color:white; border:none; border-radius:5px; cursor:pointer; width:100%; }
button:hover { background:#357ab7; }
.flash { color:red; text-align:center; }
</style>
</head>
<body>
<form method="POST">
  <h2 style="text-align:center;">Registro NEXUSMED</h2>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for msg in messages %}
        <div class="flash">{{ msg }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  <input type="email" name="email" placeholder="Correo electrónico" required>
  <input type="password" name="password" placeholder="Contraseña" required>
  <input type="password" name="confirm" placeholder="Confirmar contraseña" required>
  <button type="submit">Registrarse</button>
  <p style="text-align:center;">¿Ya tienes cuenta? <a href="{{ url_for('login') }}">Entrar</a></p>
</form>
</body>
</html>
"""

dashboard_template = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard NEXUSMED</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { font-family: Arial, sans-serif; background:#f9f9f9; margin:0; padding:0; }
header { background:#4a90e2; color:white; padding:20px; display:flex; justify-content:space-between; align-items:center; }
h1 { margin:0; }
.container { padding:20px; max-width:900px; margin:auto; }
.card { background:white; padding:20px; margin:10px 0; border-radius:10px; box-shadow:0 0 10px rgba(0,0,0,0.1); }
button { padding:10px 20px; background:#4a90e2; color:white; border:none; border-radius:5px; cursor:pointer; }
button:hover { background:#357ab7; }
.tip { background:#dff0d8; padding:10px; margin:10px 0; border-radius:5px; }
.progress-container { background:#e0e0e0; border-radius:20px; width:100%; margin:10px 0; }
.progress-bar { background:#4a90e2; height:20px; border-radius:20px; width:0%; color:white; text-align:center; font-size:0.9em; line-height:20px; }
.toggle { cursor:pointer; background:white; padding:5px 10px; border-radius:5px; margin-left:10px; }
</style>
</head>
<body>
<header>
  <h1>NEXUSMED Dashboard</h1>
  <div>
    <span class="toggle" onclick="toggleTheme()">Modo Oscuro/Claro</span>
    <form style="display:inline;" method="POST" action="{{ url_for('logout') }}">
      <button type="submit">Logout</button>
    </form>
  </div>
</header>
<div class="container">
  <div class="card">
    <h3>Bienvenido {{ email }}</h3>
    <p>Tu panel de predicciones y evolución médica</p>
    <div class="progress-container">
      <div class="progress-bar" style="width:{{ profile_progress }}%;">Perfil {{ profile_progress }}%</div>
    </div>
  </div>

  {% for tip in tips %}
  <div class="tip">💡 {{ tip }}</div>
  {% endfor %}

  <div class="card">
    <h3>IMC Evolución</h3>
    <canvas id="imcChart"></canvas>
  </div>
  <div class="card">
    <h3>Presión Arterial</h3>
    <canvas id="bpChart"></canvas>
  </div>
  <div class="card">
    <h3>Glucosa</h3>
    <canvas id="glucoseChart"></canvas>
  </div>
</div>

<script>
function toggleTheme(){
    document.body.style.background = document.body.style.background=='#333'?'#f9f9f9':'#333';
    document.body.style.color = document.body.style.color=='#fff'?'#000':'#fff';
}
const imcData = {
  labels: {{ imc_labels | safe }},
  datasets: [{
    label: 'IMC',
    data: {{ imc_values | safe }},
    borderColor: 'rgba(75, 192, 192, 1)',
    fill: false
  }]
};
const bpData = {
  labels: {{ bp_labels | safe }},
  datasets: [{
    label: 'Sistólica',
    data: {{ bp_sys | safe }},
    borderColor: 'rgba(255,99,132,1)',
    fill:false
  },{
    label:'Diastólica',
    data: {{ bp_dia | safe }},
    borderColor: 'rgba(54,162,235,1)',
    fill:false
  }]
};
const glucoseData = {
  labels: {{ glucose_labels | safe }},
  datasets: [{
    label:'Glucosa mg/dL',
    data: {{ glucose_values | safe }},
    borderColor:'rgba(255,206,86,1)',
    fill:false
  }]
};
new Chart(document.getElementById('imcChart'), { type:'line', data:imcData });
new Chart(document.getElementById('bpChart'), { type:'line', data:bpData });
new Chart(document.getElementById('glucoseChart'), { type:'line', data:glucoseData });
</script>
</body>
</html>
"""

# ----------------------------
# ROUTES
# ----------------------------
@app.route("/")
def index():
    return render_template_string(landing_template)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form["email"].lower()
        password = request.form["password"]
        user = users_db.get(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user"] = email
            flash("Login exitoso")
            return redirect(url_for("dashboard"))
        else:
            flash("Usuario o contraseña incorrecta")
    return render_template_string(login_template)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        email = request.form["email"].lower()
        password = request.form["password"]
        confirm = request.form["confirm"]
        if password != confirm:
            flash("Las contraseñas no coinciden")
        elif email in users_db:
            flash("Usuario ya registrado")
        else:
            users_db[email] = {
                "password_hash": generate_password_hash(password),
                "profile_completed": random.randint(40,80),
                "records": [],
                "tips_seen": []
            }
            flash("Registro exitoso, ya puedes entrar")
            return redirect(url_for("login"))
    return render_template_string(register_template)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        flash("Debes iniciar sesión primero")
        return redirect(url_for("login"))
    email = session["user"]
    user = users_db[email]

    # Simulación de datos
    labels = [(datetime.date.today()-datetime.timedelta(days=6-i)).isoformat() for i in range(7)]
    imc_values = [round(random.uniform(22,30),1) for _ in range(7)]
    bp_sys = [random.randint(110,140) for _ in range(7)]
    bp_dia = [random.randint(70,90) for _ in range(7)]
    glucose_values = [random.randint(80,120) for _ in range(7)]

    # Tips diarios
    all_tips = [
        "Bebe al menos 2 litros de agua",
        "Camina 30 minutos",
        "Controla tu glucosa mañana",
        "Incluye frutas y verduras en tu comida",
        "Evita el exceso de azúcares"
    ]
    tips = random.sample(all_tips, 2)

    return render_template_string(dashboard_template, email=email,
                                  profile_progress=user.get("profile_completed",50),
                                  tips=tips,
                                  imc_labels=labels, imc_values=imc_values,
                                  bp_labels=labels, bp_sys=bp_sys, bp_dia=bp_dia,
                                  glucose_labels=labels, glucose_values=glucose_values)

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    flash("Sesión cerrada")
    return redirect(url_for("login"))

# ----------------------------
# RUN SERVER
# ----------------------------
if __name__=="__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
