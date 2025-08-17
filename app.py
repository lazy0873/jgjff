from flask import Flask, render_template_string, request, redirect, session, url_for
import sqlite3
import hashlib
import json
import datetime

app = Flask(__name__)
app.secret_key = "supersecreto123"
DB_NAME = "nexusmed.db"

# -------------------- BASE DE DATOS --------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        fecha TEXT,
        edad INTEGER,
        sexo TEXT,
        altura REAL,
        peso REAL,
        glucosa INTEGER,
        colesterol INTEGER,
        presion_sistolica INTEGER,
        presion_diastolica INTEGER,
        frecuencia_cardiaca INTEGER,
        alimentacion INTEGER,
        ejercicio INTEGER,
        estres INTEGER,
        sueno INTEGER,
        sintomas TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------- PREDICCIONES --------------------
def calculate_risks(record):
    risks=[]
    imc = record['peso'] / ((record['altura']/100)**2) if record['altura']>0 else 0
    # Diabetes
    if record['glucosa']>=100 or imc>=25 or "diabetes" in record['sintomas']:
        risks.append(("Diabetes tipo 2", min(100,int((record['glucosa']-90)*0.8 + (imc-25)*3))))
    # Hipertensión
    if record['presion_sistolica']>130 or record['presion_diastolica']>85:
        risks.append(("Hipertensión", min(100,int((record['presion_sistolica']-120)*1.5))))
    # Colesterol alto
    if record['colesterol']>200:
        risks.append(("Colesterol alto", min(100,int((record['colesterol']-180)*0.5))))
    # Obesidad
    if imc>=30:
        risks.append(("Obesidad", min(100,int((imc-25)*4))))
    # Estrés crónico
    if record['estres']>=8:
        risks.append(("Estrés crónico", record['estres']*10))
    # Sueño insuficiente
    if record['sueno']<=3:
        risks.append(("Insomnio / sueño insuficiente", 70))
    return risks, round(imc,1)

# -------------------- HTML LAYOUT --------------------
def render_with_layout(body_content, extra_scripts=""):
    return render_template_string(f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NEXUSMED</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            * {{ box-sizing:border-box; margin:0; padding:0; }}
            body {{ font-family:'Inter', sans-serif; background:#f0f4f8; color:#333; }}
            h1,h2,h3 {{ color:#0d3b66; }}
            h1 {{ font-size:48px; text-align:center; margin-bottom:20px; }}
            h2 {{ margin-bottom:20px; text-align:center; }}
            h3 {{ margin-top:20px; }}
            .container {{ max-width: 1000px; margin:50px auto; padding:20px; }}
            input, select, button {{ font-size:16px; border-radius:10px; padding:12px; margin:8px 0; }}
            input, select {{ width:100%; border:1px solid #ccc; }}
            button {{ border:none; background: linear-gradient(90deg,#0d3b66,#07406f); color:white; font-weight:700; cursor:pointer; transition:all 0.3s ease; }}
            button:hover {{ opacity:0.9; transform:scale(1.02); }}
            a {{ color:#0d3b66; text-decoration:none; }}
            a:hover {{ text-decoration:underline; }}
            .card {{ background:white; padding:20px; border-radius:15px; margin-bottom:20px; box-shadow:0 8px 20px rgba(0,0,0,0.08); transition:transform 0.3s ease; }}
            .card:hover {{ transform:translateY(-5px); }}
            .risk {{ display:flex; justify-content:space-between; padding:15px; background:#ffebeb; border-left:6px solid #f44336; border-radius:12px; margin-bottom:15px; box-shadow:0 5px 15px rgba(0,0,0,0.05); }}
            #loader {{ position:fixed; top:0; left:0; width:100%; height:100%; background:#0d3b66; display:flex; justify-content:center; align-items:center; color:white; font-size:48px; font-weight:700; z-index:9999; transition:opacity 0.5s ease; }}
            .form-card {{ background:white; border-radius:15px; padding:20px; margin-bottom:20px; box-shadow:0 8px 20px rgba(0,0,0,0.08); }}
            @media (max-width:768px){{ h1 {{ font-size:40px; }} }}
        </style>
        <script>
            window.addEventListener('load', function(){{
                setTimeout(function(){{
                    document.getElementById('loader').style.opacity=0;
                    setTimeout(function(){{
                        document.getElementById('loader').style.display='none';
                    }},500);
                }},1000);
            }});
        </script>
    </head>
    <body>
        <div id="loader">NEXUSMED</div>
        <div class="container">
            {body_content}
        </div>
        {extra_scripts}
    </body>
    </html>
    """)

# -------------------- RUTAS --------------------
@app.route('/')
def home(): return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    error=""
    if request.method=='POST':
        username=request.form['username']
        password=hash_password(request.form['password'])
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO users(username,password) VALUES (?,?)",(username,password))
            conn.commit()
            conn.close()
            session['user']=username
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            error="<p style='color:red;'>Usuario ya existe.</p>"
    body_content=f"""
    <h2>Registro NEXUSMED</h2>
    <form method="POST">
        <input type="text" name="username" placeholder="Usuario" required>
        <input type="password" name="password" placeholder="Contraseña" required>
        <button type="submit">Registrarse</button>
    </form>
    <p>¿Ya tienes cuenta? <a href="{url_for('login')}">Inicia sesión</a></p>
    {error}
    """
    return render_with_layout(body_content)

@app.route('/login', methods=['GET','POST'])
def login():
    error=""
    if request.method=='POST':
        username=request.form['username']
        password=hash_password(request.form['password'])
        conn=sqlite3.connect(DB_NAME)
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
        user=c.fetchone()
        conn.close()
        if user:
            session['user']=username
            return redirect(url_for('dashboard'))
        else:
            error="<p style='color:red;'>Usuario o contraseña incorrectos.</p>"
    body_content=f"""
    <h2>Login NEXUSMED</h2>
    <form method="POST">
        <input type="text" name="username" placeholder="Usuario" required>
        <input type="password" name="password" placeholder="Contraseña" required>
        <button type="submit">Ingresar</button>
    </form>
    <p>¿No tienes cuenta? <a href="{url_for('register')}">Regístrate</a></p>
    {error}
    """
    return render_with_layout(body_content)

@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    username=session['user']
    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?",(username,))
    user_id=c.fetchone()[0]

    alerta=""
    if request.method=='POST':
        try:
            form_id=request.form.get('record_id')
            fecha=str(datetime.date.today())
            edad=int(request.form['edad'])
            sexo=request.form['sexo']
            altura=float(request.form['altura'])
            peso=float(request.form['peso'])
            glucosa=int(request.form['glucosa'])
            colesterol=int(request.form['colesterol'])
            presion_sistolica=int(request.form['presion_sistolica'])
            presion_diastolica=int(request.form['presion_diastolica'])
            frecuencia_cardiaca=int(request.form['frecuencia_cardiaca'])
            alimentacion=int(request.form['alimentacion'])
            ejercicio=int(request.form['ejercicio'])
            estres=int(request.form['estres'])
            sueno=int(request.form['sueno'])
            sintomas=request.form['sintomas']
            if form_id:  # Actualizar
                c.execute('''UPDATE records SET fecha=?,edad=?,sexo=?,altura=?,peso=?,glucosa=?,colesterol=?,
                             presion_sistolica=?,presion_diastolica=?,frecuencia_cardiaca=?,alimentacion=?,ejercicio=?,estres=?,sueno=?,sintomas=?
                             WHERE id=? AND user_id=?''',
                          (fecha,edad,sexo,altura,peso,glucosa,colesterol,
                           presion_sistolica,presion_diastolica,frecuencia_cardiaca,alimentacion,ejercicio,estres,sueno,sintomas,int(form_id),user_id))
            else:  # Nuevo registro
                c.execute('''INSERT INTO records(user_id,fecha,edad,sexo,altura,peso,glucosa,colesterol,
                          presion_sistolica,presion_diastolica,frecuencia_cardiaca,alimentacion,ejercicio,estres,sueno,sintomas)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (user_id,fecha,edad,sexo,altura,peso,glucosa,colesterol,
                           presion_sistolica,presion_diastolica,frecuencia_cardiaca,alimentacion,ejercicio,estres,sueno,sintomas))
            conn.commit()
        except Exception as e:
            alerta=f"<div class='risk'>Error: {str(e)}</div>"

    # Obtener registros
    c.execute("SELECT * FROM records WHERE user_id=? ORDER BY id ASC",(user_id,))
    records=c.fetchall()
    conn.close()

    record_cards=""
    data_for_charts=[]
    radar_labels=['Alimentación','Ejercicio','Estrés','Sueño']
    radar_datasets=[]
    for r in records:
        rec_dict={
            'id':r[0],'fecha':r[2],'edad':r[3],'sexo':r[4],'altura':r[5],'peso':r[6],
            'glucosa':r[7],'colesterol':r[8],'presion_sistolica':r[9],
            'presion_diastolica':r[10],'frecuencia_cardiaca':r[11],
            'alimentacion':r[12],'ejercicio':r[13],'estres':r[14],'sueno':r[15],
            'sintomas':r[16].split(',')
        }
        data_for_charts.append(rec_dict)
        radar_datasets.append([rec_dict['alimentacion'],rec_dict['ejercicio'],rec_dict['estres'],rec_dict['sueno']])
        record_cards+=f"""
        <div class='card'>
            <h4>Registro #{r[0]} ({rec_dict['fecha']})</h4>
            Edad: {rec_dict['edad']}<br>
            Sexo: {rec_dict['sexo']}<br>
            Altura: {rec_dict['altura']} cm<br>
            Peso: {rec_dict['peso']} kg<br>
            Glucosa: {rec_dict['glucosa']}<br>
            Colesterol: {rec_dict['colesterol']}<br>
            Presión: {rec_dict['presion_sistolica']}/{rec_dict['presion_diastolica']}<br>
            Frecuencia Cardíaca: {rec_dict['frecuencia_cardiaca']}<br>
            Síntomas: {', '.join(rec_dict['sintomas'])}<br>
            <form method="POST">
                <input type="hidden" name="record_id" value="{rec_dict['id']}">
                <button type="submit" style="margin-top:10px;">Editar este registro</button>
            </form>
        </div>
        """

    # Riesgos y predicciones
    all_risks=""
    for rec in data_for_charts:
        risks, imc = calculate_risks(rec)
        for rname,percent in risks:
            all_risks+=f"<div class='risk'>{rname}: {percent}% de riesgo</div>"

    data_json=json.dumps(data_for_charts)
    radar_json=json.dumps(radar_datasets)

    chart_scripts=f"""
    <h3>Evolución de tu salud</h3>
    <canvas id="healthChart"></canvas>
    <canvas id="radarChart" style="margin-top:30px;"></canvas>
    <script>
        const records={data_json};
        const labels=records.map((_,i)=>"Registro "+(i+1));
        const peso=records.map(r=>r.peso);
        const imc=records.map(r=>Math.round(r.peso/((r.altura/100)**2)*10)/10);
        const glucosa=records.map(r=>r.glucosa);
        const colesterol=records.map(r=>r.colesterol);
        const presion=records.map(r=>r.presion_sistolica);

        const ctx=document.getElementById('healthChart').getContext('2d');
        new Chart(ctx,{{
            type:'line',
            data:{{
                labels:labels,
                datasets:[
                    {{label:'Peso (kg)', data:peso, borderColor:'#0d3b66', fill:false, tension:0.3}},
                    {{label:'IMC', data:imc, borderColor:'#6a4c93', fill:false, tension:0.3}},
                    {{label:'Glucosa', data:glucosa, borderColor:'#faa613', fill:false, tension:0.3}},
                    {{label:'Colesterol', data:colesterol, borderColor:'#ff6f61', fill:false, tension:0.3}},
                    {{label:'Presión Sistólica', data:presion, borderColor:'#1982c4', fill:false, tension:0.3}}
                ]
            }},
            options:{{responsive:true,plugins:{{legend:{{position:'top'}},title:{{display:true,text:'Tendencias de Salud',font:{{size:18}}}}}}}}
        }});

        const radarData={radar_json};
        const radarCtx=document.getElementById('radarChart').getContext('2d');
        new Chart(radarCtx,{{
            type:'radar',
            data:{{
                labels:{json.dumps(radar_labels)},
                datasets:radarData.map((d,i)=>({{
                    label:'Registro '+(i+1),
                    data:d,
                    fill:true,
                    backgroundColor:'rgba(77, 144, 254,0.2)',
                    borderColor:'#4d90fe',
                    pointBackgroundColor:'#0d3b66'
                }}))
            }},
            options:{{responsive:true, plugins:{{title:{{display:true,text:'Radar de factores de riesgo'}}}}}}
        }});
    </script>
    """

    form_html=f"""
    <h3>Nuevo / Editar Registro Médico</h3>
    <form method="POST">
        <input type="hidden" name="record_id" value="">
        <div class='form-card'><label>Edad:</label><input type="number" name="edad" required></div>
        <div class='form-card'><label>Sexo:</label><select name="sexo" required>
            <option value="">Selecciona...</option><option value="Masculino">Masculino</option>
            <option value="Femenino">Femenino</option></select></div>
        <div class='form-card'><label>Altura (cm):</label><input type="number" name="altura" required></div>
        <div class='form-card'><label>Peso (kg):</label><input type="number" name="peso" required></div>
        <div class='form-card'><label>Glucosa (mg/dL):</label><input type="number" name="glucosa" required></div>
        <div class='form-card'><label>Colesterol (mg/dL):</label><input type="number" name="colesterol" required></div>
        <div class='form-card'><label>Presión Sistólica:</label><input type="number" name="presion_sistolica" required></div>
        <div class='form-card'><label>Presión Diastólica:</label><input type="number" name="presion_diastolica" required></div>
        <div class='form-card'><label>Frecuencia Cardíaca:</label><input type="number" name="frecuencia_cardiaca" required></div>
        <div class='form-card'><label>Alimentación (1-10):</label><input type="number" name="alimentacion" min="1" max="10" required></div>
        <div class='form-card'><label>Ejercicio (1-10):</label><input type="number" name="ejercicio" min="1" max="10" required></div>
        <div class='form-card'><label>Estrés (1-10):</label><input type="number" name="estres" min="1" max="10" required></div>
        <div class='form-card'><label>Sueño (1-10):</label><input type="number" name="sueno" min="1" max="10" required></div>
        <div class='form-card'><label>Síntomas (coma separados):</label><input type="text" name="sintomas" required></div>
        <button type="submit">Guardar Registro</button>
    </form>
    """

    body_content=f"""
    <h2>Bienvenido {username} a NEXUSMED</h2>
    {form_html}
    {alerta}
    {record_cards}
    <h3>Predicciones y alertas preventivas</h3>
    {all_risks}
    {chart_scripts}
    <form method="POST" action="{url_for('logout')}"><button type="submit">Cerrar sesión</button></form>
    """

    return render_with_layout(body_content)

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# -------------------- INICIO --------------------
if __name__=="__main__":
    init_db()
    app.run(debug=True)
