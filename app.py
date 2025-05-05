from flask import Flask, render_template, request, send_file, redirect, url_for, session
import os
from funciones import tipo, sonificar_espirales, sonificar_elipticas
from funciones import convertir_midi_a_wav, mezclar_wavs, convertir_midi_a_wav_musescore

app = Flask(__name__)
app.secret_key = 'cambia_esto_por_una_clave_secreta_segura'

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None
    tipo_galaxia = None
    fig = None
    archivo_emision = None
    archivo_absorcion = None
    archivo_completo = None
    if request.method == 'POST':
        archivo = request.files.get('archivo')
        if archivo:
            import uuid
            session_id = session.get('id')
            if not session_id:
                session_id = str(uuid.uuid4())
                session['id'] = session_id
            carpeta_usuario = os.path.join('archivos_temporales', session_id)
            os.makedirs(carpeta_usuario, exist_ok=True)
            archivo_path = os.path.join(carpeta_usuario, 'espectro_temporal.txt')
            archivo.save(archivo_path)
            session['archivo_path'] = archivo_path
            # Calcular límites de longitud de onda
            import pandas as pd
            try:
                datos = pd.read_csv(archivo_path, sep=r"\s+|;", engine='python', comment='#', header=None)
                min_wavelength = float(datos.iloc[:,0].min())
                max_wavelength = float(datos.iloc[:,0].max())
            except Exception:
                min_wavelength = 6500
                max_wavelength = 6700
            session['min_wavelength'] = min_wavelength
            session['max_wavelength'] = max_wavelength
        else:
            archivo_path = session.get('archivo_path')
            min_wavelength = session.get('min_wavelength', 6500)
            max_wavelength = session.get('max_wavelength', 6700)
            if not archivo_path or not os.path.exists(archivo_path):
                resultado = 'Debes subir primero un archivo de espectro.'
                return render_template('index.html', resultado=resultado)
        rango_ini = int(request.form.get('rango_ini', 6500))
        rango_fin = int(request.form.get('rango_fin', 6700))
        tempo = int(request.form.get('tempo', 200))
        duracion = float(request.form.get('duracion', 0.5))
        instrumento_emision_str = request.form.get('instrumento_emision', '0')
        # Eliminar el bloqueo de generación de MIDI por la opción midi_crudo
        try:
            instrumento_emision = int(instrumento_emision_str) if instrumento_emision_str != 'midi_crudo' else 0
        except (ValueError, TypeError):
            instrumento_emision = 0
        try:
            instrumento_absorcion = int(request.form.get('instrumento_absorcion', 24))
        except (ValueError, TypeError):
            instrumento_absorcion = 24
        tipo_galaxia = request.form.get('tipo_galaxia')
        if tipo_galaxia == 'Espiral':
            nombre_archivo = os.path.basename(archivo.filename) if archivo else os.path.basename(archivo_path)
            fig = sonificar_espirales(archivo_path, rango_onda=(rango_ini, rango_fin), tempo=tempo, duracion_nota=duracion, instrumento_emision=instrumento_emision, instrumento_absorcion=instrumento_absorcion, nombre_archivo=nombre_archivo)
            archivo_emision = os.path.join(carpeta_usuario, 'salida_emision.mid')
            archivo_absorcion = os.path.join(carpeta_usuario, 'salida_absorcion.mid')
            archivo_completo = os.path.join(carpeta_usuario, 'salida_completo.mid')
        else:
            nombre_archivo = os.path.basename(archivo.filename) if archivo else os.path.basename(archivo_path)
            fig = sonificar_elipticas(archivo_path, rango_onda=(rango_ini, rango_fin), tempo=tempo, duracion_nota=duracion, instrumento_emision=instrumento_emision, instrumento_absorcion=instrumento_absorcion, nombre_archivo=nombre_archivo)
            archivo_emision = os.path.join(carpeta_usuario, 'elipticas_emision.mid')
            archivo_absorcion = os.path.join(carpeta_usuario, 'elipticas_absorcion.mid')
            archivo_completo = os.path.join(carpeta_usuario, 'salida_completo.mid')
        fig.savefig(os.path.join(carpeta_usuario, 'sonificacion.svg'), format='svg')
        resultado = "Sonificación completada. Archivos MIDI disponibles para descarga."
        session['archivo_emision'] = archivo_emision
        session['archivo_absorcion'] = archivo_absorcion
        session['archivo_completo'] = archivo_completo
        session['svg'] = os.path.join(carpeta_usuario, 'sonificacion.svg')
        # Si el usuario seleccionó midi_crudo, solo afecta la reproducción
        archivo_midi_crudo = (instrumento_emision_str == 'midi_crudo')
        return render_template('index.html', resultado=resultado, tipo_galaxia=tipo_galaxia, archivo_emision=archivo_emision, archivo_absorcion=archivo_absorcion, archivo_completo=archivo_completo, min_wavelength=min_wavelength, max_wavelength=max_wavelength, archivo_midi_crudo=archivo_midi_crudo)
    else:
        # Al cargar la página por GET, limpiar solo si no hay sesión activa
        if 'id' in session:
            carpeta_usuario = os.path.join('archivos_temporales', session['id'])
            import shutil
            if os.path.exists(carpeta_usuario):
                shutil.rmtree(carpeta_usuario)
            session.clear()
        return render_template('index.html')

@app.route('/descargar/<nombre_archivo>')
def descargar(nombre_archivo):
    carpeta_usuario = os.path.join('archivos_temporales', session.get('id',''))
    archivo_path = os.path.join(carpeta_usuario, nombre_archivo)
    if os.path.exists(archivo_path):
        return send_file(archivo_path, as_attachment=True)
    return "Archivo no encontrado", 404

@app.route('/sonificacion.svg')
def mostrar_svg():
    svg_path = session.get('svg')
    if svg_path and os.path.exists(svg_path):
        return send_file(svg_path)
    return "SVG no encontrado", 404

if __name__ == '__main__':
    app.run(debug=True)
