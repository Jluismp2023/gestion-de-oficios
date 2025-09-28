import os
from flask import Flask, render_template, request, redirect, url_for, g, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import cloudinary
import cloudinary.uploader

# --- CONFIGURACIÓN DE CLOUDINARY ---
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
  api_key = os.environ.get('CLOUDINARY_API_KEY'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

app = Flask(__name__)

# (El resto de la configuración de Flask y la base de datos no cambia)
DATABASE = 'oficios.db'
def get_db():
    db = getattr(g, '_database', None)
    if db is None: db = g._database = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oficios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, numero_oficio TEXT, tipo TEXT NOT NULL,
                fecha DATE NOT NULL, remitente TEXT NOT NULL, destinatario TEXT NOT NULL,
                asunto TEXT NOT NULL, cuerpo TEXT NOT NULL, estado TEXT NOT NULL,
                observaciones TEXT, archivo_adjunto TEXT 
            )''')
        db.commit()
# (La ruta de index no cambia)
@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor()
    search_query = request.args.get('q', '')
    search_clause = "AND (asunto LIKE ? OR remitente LIKE ? OR destinatario LIKE ? OR numero_oficio LIKE ?)"
    search_params = ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%')
    query_recibidos = "SELECT * FROM oficios WHERE tipo = 'recibido' "
    if search_query: cursor.execute(query_recibidos + "ORDER BY fecha DESC", search_params)
    else: cursor.execute(query_recibidos + "ORDER BY fecha DESC")
    oficios_recibidos = cursor.fetchall()
    query_enviados = "SELECT * FROM oficios WHERE tipo = 'enviado' "
    if search_query: cursor.execute(query_enviados + "ORDER BY fecha DESC", search_params)
    else: cursor.execute(query_enviados + "ORDER BY fecha DESC")
    oficios_enviados = cursor.fetchall()
    total_enviados = len(oficios_enviados)
    total_recibidos = len(oficios_recibidos)
    return render_template('index.html', oficios_recibidos=oficios_recibidos, oficios_enviados=oficios_enviados, search_query=search_query, total_enviados=total_enviados, total_recibidos=total_recibidos)

@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if request.method == 'POST':
        # --- LÓGICA DE SUBIDA DE ARCHIVOS MODIFICADA PARA CLOUDINARY ---
        urls_guardadas = []
        files = request.files.getlist('archivo_adjunto')
        for file in files:
            if file and file.filename != '':
                # Subir a Cloudinary y obtener la URL segura
                upload_result = cloudinary.uploader.upload(file, resource_type = "auto")
                urls_guardadas.append(upload_result['secure_url'])
        
        nombres_de_archivos = ",".join(urls_guardadas)
        # (El resto de la función no cambia)
        numero_oficio = request.form['numero_oficio']; tipo = request.form['tipo']; fecha = request.form['fecha']
        remitente = request.form['remitente']; destinatario = request.form['destinatario']; asunto = request.form['asunto']
        cuerpo = request.form['cuerpo']; observaciones = request.form['observaciones']
        if tipo == 'enviado': estado = 'Enviado'
        else: estado = 'Pendiente'
        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT INTO oficios (numero_oficio, tipo, fecha, remitente, destinatario, asunto, cuerpo, estado, observaciones, archivo_adjunto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (numero_oficio, tipo, fecha, remitente, destinatario, asunto, cuerpo, estado, observaciones, nombres_de_archivos))
        db.commit()
        return redirect(url_for('index'))
    return render_template('agregar.html')

# (La ruta de editar, eliminar y el resto del código no cambian sustancialmente en su lógica, pero se adaptan para Cloudinary)
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if request.method == 'POST':
        archivos_actuales = request.form.get('archivos_actuales').split(',') if request.form.get('archivos_actuales') else []
        urls_nuevas_guardadas = []
        files = request.files.getlist('archivo_adjunto')
        for file in files:
            if file and file.filename != '':
                upload_result = cloudinary.uploader.upload(file, resource_type = "auto")
                urls_nuevas_guardadas.append(upload_result['secure_url'])
        todos_los_archivos = [f for f in archivos_actuales if f] + urls_nuevas_guardadas
        nombres_de_archivos = ",".join(todos_los_archivos)
        # (El resto de los campos)
        numero_oficio = request.form['numero_oficio']; tipo = request.form['tipo']; fecha = request.form['fecha']
        remitente = request.form['remitente']; destinatario = request.form['destinatario']; asunto = request.form['asunto']
        cuerpo = request.form['cuerpo']; estado = request.form['estado']; observaciones = request.form['observaciones']
        db = get_db()
        cursor = db.cursor()
        cursor.execute('UPDATE oficios SET numero_oficio=?, tipo=?, fecha=?, remitente=?, destinatario=?, asunto=?, cuerpo=?, estado=?, observaciones=?, archivo_adjunto=? WHERE id=?', (numero_oficio, tipo, fecha, remitente, destinatario, asunto, cuerpo, estado, observaciones, nombres_de_archivos, id))
        db.commit()
        return redirect(url_for('index'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM oficios WHERE id = ?', (id,))
    oficio = cursor.fetchone()
    return render_template('editar.html', oficio=oficio)
    
@app.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    # La lógica de borrado de archivos ya no es necesaria aquí, se gestiona en Cloudinary
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM oficios WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True)