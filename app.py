from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3, os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ----------------- DB -----------------
def init_db():
    conn = sqlite3.connect("nexusmed.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    password TEXT,
                    name TEXT,
                    age INTEGER,
                    condition TEXT
                )""")
    conn.commit()
    conn.close()

# ----------------- Layout -----------------
def render_with_layout(content):
    layout = f"""
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <title>NEXUSMED</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin:0; padding:0; background:#f9fafb; color:#333; }}
            header {{ background:#2563eb; color:white; padding:1rem; text-align:center; }}
            nav a {{ margin:0 10px; color:white; text-decoration:none; font-weight:bold; }}
            .container {{ max-width:900px; margin:2rem auto; padding:2rem; background:white; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.1); }}
            .hero {{ text-align:center; padding:3rem 1rem; }}
            .hero h1 {{ font-size:2.5rem; margin-bottom:1rem; }}
            .hero p {{ font-size:1.2rem; margin-bottom:2rem; }}
            .btn {{ display:inline-block; padding:0.7rem 1.2rem; margin:0.5rem; border-radius:8px; text-decoration:none; font-weight:bold; }}
            .btn-primary {{ background:#2563eb; color:white; }}
            .btn-secondary {{ background:#e5e7eb; color:#111; }}
            .benefits {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(250px,1fr)); gap:1rem; margin-top:2rem; }}
            .card {{ padding:1rem; border:1px solid #ddd; border-radius:10px; background:#fefefe; }}
            footer {{ background:#111; color:#ccc; text-align:center; padding:1rem; margin-top:2rem; font-size:0.9rem; }}
            .flash {{ padding:0.5rem 1rem; border-radius:6px; margin-bottom:1rem; }}
            .flash-success {{ background:#d1fae5; color:#065f46; }}
            .flash-error {{ background:#fee2e2; color:#991b1b; }}
        </style>
    </head>
    <body>
        <header>
            <h2>NEXUSMED</h2>
            <nav>
                <a href="/">Inicio</a>
                <a href="/login">Acceder</a>
                <a href="/register">Registro</a>
            </nav>
        </header>
        <div class="container">
            {content}
        </div>
        <footer>
            <p>🔒 Tus datos están seguros y privados. | <a href="#">Política de Privacidad</a> | <a href="#">Términos de uso</a></p>
        </footer>
    </body>
    </html>
    """
    return layout

# ----------------- Rutas -----------------
@app.route("/")
def landing():
    content = """
    <div class="hero">
        <h1>Tu historial médico inteligente</h1>
        <p>Guarda tu información de salud, recibe predicciones y controla tu bienestar en un solo lugar.</p>
        <a class="btn btn-primary" href="/register">Regístrate ahora</a>
        <a class="btn btn-secondary" href="/login">Inicia sesión</a>
    </div>
    <div class="benefits">
        <div class="card"><h3>🔒 Seguridad</h3><p>Tus datos médicos están cifrados y protegidos.</p></div>
        <div class="card"><h3>📊 Predicciones</h3><p>Obtén análisis de riesgos y proyecciones personalizadas.</p></div>
        <div class="card"><h3>⚡ Acceso rápido</h3><p>Consulta tu expediente en cualquier momento, desde cualquier lugar.</p></div>
    </div>
    """
    return render_with_layout(content)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        name = request.form["name"]
        try:
            conn = sqlite3.connect("nexusmed.db")
            c = conn.cursor()
            c.execute("INSERT INTO users (email,password,name) VALUES (?,?,?)",(email,password,name))
            conn.commit()
            conn.close()
            flash("Registro exitoso, ya puedes iniciar sesión", "success")
            return redirect(url_for("login"))
        except:
            flash("El correo ya está registrado", "error")
    content = """
    <h2>Registro</h2>
    <form method="post">
        <input name="name" placeholder="Nombre completo" required><br><br>
        <input name="email" type="email" placeholder="Correo electrónico" required><br><br>
        <input name="password" type="password" placeholder="Contraseña" required><br><br>
        <button class="btn btn-primary" type="submit">Registrarme</button>
    </form>
    """
    return render_with_layout(content)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        conn = sqlite3.connect("nexusmed.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?",(email,password))
        user = c.fetchone()
        conn.close()
        if user:
            session["user"] = user[0]
            flash("Bienvenido de nuevo!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Credenciales incorrectas", "error")
    content = """
    <h2>Iniciar sesión</h2>
    <form method="post">
        <input name="email" type="email" placeholder="Correo" required><br><br>
        <input name="password" type="password" placeholder="Contraseña" required><br><br>
        <button class="btn btn-primary" type="submit">Entrar</button>
    </form>
    <p>¿No tienes cuenta? <a href="/register">Regístrate aquí</a></p>
    """
    return render_with_layout(content)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    uid = session["user"]
    conn = sqlite3.connect("nexusmed.db")
    c = conn.cursor()
    c.execute("SELECT name, age, condition FROM users WHERE id=?",(uid,))
    user = c.fetchone()
    conn.close()
    name, age, condition = user if user else ("","", "")
    content = f"""
    <h2>Bienvenido, {name}</h2>
    <p>Edad: {age if age else 'No registrada'}</p>
    <p>Condición: {condition if condition else 'No registrada'}</p>
    <a class="btn btn-secondary" href="/edit">Actualizar datos médicos</a>
    <hr>
    <h3>📊 Ejemplo de predicción</h3>
    <p>Tu IMC está dentro del rango saludable. Riesgo de hipertensión: <b>15%</b>.</p>
    <form method="post" action="/logout">
        <button class="btn btn-primary" type="submit">Cerrar sesión</button>
    </form>
    """
    return render_with_layout(content)

@app.route("/edit", methods=["GET","POST"])
def edit():
    if "user" not in session:
        return redirect(url_for("login"))
    uid = session["user"]
    if request.method=="POST":
        age = request.form["age"]
        condition = request.form["condition"]
        conn = sqlite3.connect("nexusmed.db")
        c = conn.cursor()
        c.execute("UPDATE users SET age=?, condition=? WHERE id=?",(age,condition,uid))
        conn.commit()
        conn.close()
        flash("Datos actualizados correctamente", "success")
        return redirect(url_for("dashboard"))
    content = """
    <h2>Actualizar datos médicos</h2>
    <form method="post">
        <input name="age" type="number" placeholder="Edad"><br><br>
        <input name="condition" placeholder="Condición médica"><br><br>
        <button class="btn btn-primary" type="submit">Guardar</button>
    </form>
    """
    return render_with_layout(content)

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ----------------- Iniciar -----------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
