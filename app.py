import os
from flask import Flask, render_template, request, redirect, url_for, g, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3

# --- CONFIGURACIÓN ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Base de Datos ---
DATABASE = 'oficios.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oficios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_oficio TEXT, 
                tipo TEXT NOT NULL,
                fecha DATE NOT NULL,
                remitente TEXT NOT NULL,
                destinatario TEXT NOT NULL,
                asunto TEXT NOT NULL,
                cuerpo TEXT NOT NULL,
                estado TEXT NOT NULL,
                observaciones TEXT,
                archivo_adjunto TEXT 
            )
        ''')
        db.commit()

# --- Rutas de la aplicación ---
@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor()
    search_query = request.args.get('q', '')

    search_clause = "AND (asunto LIKE ? OR remitente LIKE ? OR destinatario LIKE ? OR numero_oficio LIKE ?)"
    search_params = ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%')

    query_recibidos = "SELECT * FROM oficios WHERE tipo = 'recibido' "
    if search_query:
        query_recibidos += search_clause
        cursor.execute(query_recibidos + "ORDER BY fecha DESC", search_params)
    else:
        cursor.execute(query_recibidos + "ORDER BY fecha DESC")
    oficios_recibidos = cursor.fetchall()

    query_enviados = "SELECT * FROM oficios WHERE tipo = 'enviado' "
    if search_query:
        query_enviados += search_clause
        cursor.execute(query_enviados + "ORDER BY fecha DESC", search_params)
    else:
        cursor.execute(query_enviados + "ORDER BY fecha DESC")
    oficios_enviados = cursor.fetchall()
    
    total_enviados = len(oficios_enviados)
    total_recibidos = len(oficios_recibidos)
    
    return render_template('index.html', 
                           oficios_recibidos=oficios_recibidos, 
                           oficios_enviados=oficios_enviados, 
                           search_query=search_query,
                           total_enviados=total_enviados,
                           total_recibidos=total_recibidos)

@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if request.method == 'POST':
        archivos_guardados = []
        files = request.files.getlist('archivo_adjunto')
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                archivos_guardados.append(filename)
        
        nombres_de_archivos = ",".join(archivos_guardados)

        numero_oficio = request.form['numero_oficio']
        tipo = request.form['tipo']
        fecha = request.form['fecha']
        remitente = request.form['remitente']
        destinatario = request.form['destinatario']
        asunto = request.form['asunto']
        cuerpo = request.form['cuerpo']
        if tipo == 'enviado':
            estado = 'Enviado'
        else:
            estado = 'Pendiente'
        observaciones = request.form['observaciones']
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO oficios (numero_oficio, tipo, fecha, remitente, destinatario, asunto, cuerpo, estado, observaciones, archivo_adjunto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (numero_oficio, tipo, fecha, remitente, destinatario, asunto, cuerpo, estado, observaciones, nombres_de_archivos))
        db.commit()
        return redirect(url_for('index'))
    return render_template('agregar.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    db = get_db()
    cursor = db.cursor()
    if request.method == 'POST':
        archivos_actuales = request.form.get('archivos_actuales').split(',') if request.form.get('archivos_actuales') else []
        
        archivos_nuevos_guardados = []
        files = request.files.getlist('archivo_adjunto')
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                archivos_nuevos_guardados.append(filename)
        
        todos_los_archivos = [f for f in archivos_actuales if f] + archivos_nuevos_guardados
        nombres_de_archivos = ",".join(todos_los_archivos)

        numero_oficio = request.form['numero_oficio']
        tipo = request.form['tipo']
        fecha = request.form['fecha']
        remitente = request.form['remitente']
        destinatario = request.form['destinatario']
        asunto = request.form['asunto']
        cuerpo = request.form['cuerpo']
        estado = request.form['estado']
        observaciones = request.form['observaciones']
        
        cursor.execute('''
            UPDATE oficios 
            SET numero_oficio=?, tipo=?, fecha=?, remitente=?, destinatario=?, asunto=?, cuerpo=?, estado=?, observaciones=?, archivo_adjunto=?
            WHERE id=?
        ''', (numero_oficio, tipo, fecha, remitente, destinatario, asunto, cuerpo, estado, observaciones, nombres_de_archivos, id))
        db.commit()
        return redirect(url_for('index'))
    
    cursor.execute('SELECT * FROM oficios WHERE id = ?', (id,))
    oficio = cursor.fetchone()
    if oficio is None:
        return "Oficio no encontrado", 404
    return render_template('editar.html', oficio=oficio)

@app.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT archivo_adjunto FROM oficios WHERE id = ?', (id,))
    oficio = cursor.fetchone()
    if oficio and oficio['archivo_adjunto']:
        archivos_a_borrar = oficio['archivo_adjunto'].split(',')
        for filename in archivos_a_borrar:
            if filename: 
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                except OSError as e:
                    print(f"Error borrando archivo {filename}: {e.strerror}")
    
    cursor.execute('DELETE FROM oficios WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_db()
# Al final de app.py
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_db()
    # Usamos waitress para pruebas locales, Render usará gunicorn
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)