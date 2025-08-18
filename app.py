from flask import Flask, render_template_string, request, redirect, url_for, session
import os, random, time

app = Flask(__name__)
app.secret_key = "clave_secreta_nexusmed"

# Base de datos simulada
users = {"demo":"1234"}
medical_records = {"demo":[]}

# -------------------- Funciones --------------------
def render_with_layout(body_content):
    layout = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>NEXUSMED Premium</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; background-color:#f7f7f7; }}
            .form-card {{ margin-bottom: 15px; }}
            .card {{ background-color: #fff; padding: 15px; border-radius:10px; box-shadow:0 2px 5px rgba(0,0,0,0.1); }}
            canvas {{ max-width: 100%; height: auto; }}
            .center-screen {{ display:flex; align-items:center; justify-content:center; height:100vh; flex-direction:column; }}
            .loading-logo {{ font-size:48px; font-weight:bold; color:#0d6efd; }}
        </style>
    </head>
    <body>
        <div class="container">
            {body_content}
        </div>
    </body>
    </html>
    """
    return render_template_string(layout)

def calculate_risks(record):
    # Predicciones preventivas demo
    risks = {
        "Diabetes": min(100, int(record["glucosa"])*0.5 + int(record["peso"])*0.3 + random.randint(0,20)),
        "Hipertension": min(100, int(record["presion"].split('/')[0])*0.5 + int(record["estres"])*5 + random.randint(0,15)),
        "Cardiovascular": min(100, int(record["colesterol"])*0.4 + int(record["ejercicio"])*-3 + random.randint(0,20)),
        "Cancer": random.randint(5,60)
    }
    return risks

def radar_factors(record):
    return {
        "Alimentación": int(record["alimentacion"]),
        "Ejercicio": int(record["ejercicio"]),
        "Estrés": int(record["estres"]),
        "Sueño": int(record["sueno"])
    }

def population_comparison(value, factor):
    promedio = {"glucosa":100,"colesterol":200,"presion":120,"peso":70}
    if factor in promedio:
        return f"{'mejor' if float(value)<promedio[factor] else 'peor'} que la media de tu edad"
    return ""

# -------------------- Rutas --------------------

# --- Pantalla de carga ---
@app.route('/loading')
def loading():
    body = """
    <div class="center-screen">
        <div class="loading-logo">NEXUSMED</div>
        <div>Cargando aplicación...</div>
        <script>
            setTimeout(()=>{ window.location.href='/presentacion'; },2000);
        </script>
    </div>
    """
    return render_with_layout(body)

# --- Presentación ---
@app.route('/presentacion')
def presentacion():
    body = """
    <div class="card">
        <h2>Bienvenido a NEXUSMED Premium</h2>
        <p>NEXUSMED es tu asistente preventivo de salud. Aquí podrás registrar tu historial clínico, recibir predicciones de riesgo de enfermedades y monitorear tu salud con gráficos avanzados.</p>
        <ul>
            <li>Registra tu peso, altura, glucosa, colesterol y presión arterial.</li>
            <li>Obtén predicciones de diabetes, hipertensión, riesgos cardiovasculares y cáncer.</li>
            <li>Visualiza tus datos con gráficas dinámicas y comparaciones con población promedio.</li>
            <li>Recibe alertas y recomendaciones personalizadas basadas en IA.</li>
        </ul>
        <a href="/login" class="btn btn-primary">Comenzar</a>
    </div>
    """
    return render_with_layout(body)

# --- Login ---
@app.route('/', methods=['GET','POST'])
@app.route('/login', methods=['GET','POST'])
def login():
    alerta = ""
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users and users[username]==password:
            session['user']=username
            return redirect(url_for('dashboard'))
        else:
            alerta = "<div class='alert alert-danger'>Usuario o contraseña incorrectos</div>"
    body = f"""
    <h1>NEXUSMED Premium</h1>
    <h3>Inicia sesión</h3>
    {alerta}
    <form method="POST">
        <div class="form-card"><input type="text" name="username" placeholder="Usuario" required class="form-control"></div>
        <div class="form-card"><input type="password" name="password" placeholder="Contraseña" required class="form-control"></div>
        <button type="submit" class="btn btn-primary">Entrar</button>
    </form>
    """
    return render_with_layout(body)

# --- Dashboard ---
@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    username = session['user']
    alerta = ""
    if request.method=="POST":
        record = {
            "peso": request.form.get("peso"),
            "altura": request.form.get("altura"),
            "glucosa": request.form.get("glucosa"),
            "colesterol": request.form.get("colesterol"),
            "presion": request.form.get("presion"),
            "alimentacion": request.form.get("alimentacion"),
            "ejercicio": request.form.get("ejercicio"),
            "estres": request.form.get("estres"),
            "sueno": request.form.get("sueno"),
            "sintomas": request.form.get("sintomas"),
        }
        medical_records.setdefault(username,[]).append(record)
        alerta = "<div class='alert alert-success'>Registro guardado</div>"

    record_cards=""
    charts_script=""
    for idx, rec in enumerate(medical_records.get(username, [])):
        risks = calculate_risks(rec)
        factors = radar_factors(rec)
        record_cards += f"""
        <div class='card mb-3'>
            <strong>Registro {idx+1}</strong><br>
            Peso: {rec['peso']} kg ({population_comparison(rec['peso'],'peso')}), Glucosa: {rec['glucosa']} mg/dL ({population_comparison(rec['glucosa'],'glucosa')}), Presión: {rec['presion']} ({population_comparison(rec['presion'].split('/')[0],'presion')}), Colesterol: {rec['colesterol']} mg/dL ({population_comparison(rec['colesterol'],'colesterol')})
        </div>
        <div class='row mb-3'>
            <div class='col-md-6'><canvas id='lineChart{idx}'></canvas></div>
            <div class='col-md-6'><canvas id='radarChart{idx}'></canvas></div>
        </div>
        """
        charts_script += f"""
        <script>
        const ctxLine{idx} = document.getElementById('lineChart{idx}').getContext('2d');
        new Chart(ctxLine{idx}, {{
            type:'bar',
            data:{{labels:['Diabetes','Hipertension','Cardiovascular','Cancer'],datasets:[{{label:'Riesgo (%)',data:[{risks['Diabetes']},{risks['Hipertension']},{risks['Cardiovascular']},{risks['Cancer']}],backgroundColor:['rgba(255,99,132,0.5)','rgba(54,162,235,0.5)','rgba(255,206,86,0.5)','rgba(75,192,192,0.5)'],borderColor:['red','blue','yellow','green'],borderWidth:1}}]}},
            options:{{scales:{{y:{{beginAtZero:true,max:100}}}}}}
        }});
        const ctxRadar{idx} = document.getElementById('radarChart{idx}').getContext('2d');
        new Chart(ctxRadar{idx},{{
            type:'radar',
            data:{{labels:['Alimentación','Ejercicio','Estrés','Sueño'],datasets:[{{label:'Factores de riesgo (1-10)',data:[{factors['Alimentación']},{factors['Ejercicio']},{factors['Estrés']},{factors['Sueño']}],backgroundColor:'rgba(255,99,132,0.2)',borderColor:'rgba(255,99,132,1)',borderWidth:2}}]}},
            options:{{scales:{{r:{{beginAtZero:true,min:0,max:10}}}}}}
        }});
        </script>
        """

    form_html = """
    <form method="POST">
        <div class='form-card'><label>Peso (kg):</label><input type="number" name="peso" step="0.1" class="form-control" required></div>
        <div class='form-card'><label>Altura (cm):</label><input type="number" name="altura" step="0.1" class="form-control" required></div>
        <div class='form-card'><label>Glucosa (mg/dL):</label><input type="number" name="glucosa" class="form-control" required></div>
        <div class='form-card'><label>Colesterol (mg/dL):</label><input type="number" name="colesterol" class="form-control" required></div>
        <div class='form-card'><label>Presión arterial (ej: 120/80):</label><input type="text" name="presion" class="form-control" required></div>
        <div class='form-card'><label>Alimentación (1-10):</label><input type="number" name="alimentacion" min="1" max="10" class="form-control" required></div>
        <div class='form-card'><label>Ejercicio (1-10):</label><input type="number" name="ejercicio" min="1" max="10" class="form-control" required></div>
        <div class='form-card'><label>Estrés (1-10):</label><input type="number" name="estres" min="1" max="10" class="form-control" required></div>
        <div class='form-card'><label>Sueño (1-10):</label><input type="number" name="sueno" min="1" max="10" class="form-control" required></div>
        <div class='form-card'><label>Síntomas (coma separados):</label><input type="text" name="sintomas" class="form-control" required></div>
        <button type="submit" class="btn btn-success">Guardar Registro</button>
    </form>
    """

    body_content=f"""
    <h2>Bienvenido {username} a NEXUSMED Premium</h2>
    {form_html}
    {alerta}
    <h3>Tus registros y predicciones avanzadas</h3>
    {record_cards}
    <form method="POST" action="{url_for('logout')}"><button type="submit" class="btn btn-danger mt-3">Cerrar sesión</button></form>
    {charts_script}
    """

    return render_with_layout(body_content)

# --- Logout ---
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# -------------------- INICIO --------------------
if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=True)
