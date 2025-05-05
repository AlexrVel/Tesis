import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from midiutil import MIDIFile
from scipy.ndimage import uniform_filter1d
import os
from midi2audio import FluidSynth
import subprocess
from pydub import AudioSegment


def detectar_region_plana(archivo, ventana=100, suavizado=10, rango_central=(0.95, 1.05)):
    
    # Cargar datos
    with open(archivo, 'r') as f:
        primera_linea = f.readline().strip()
    
    # Detectar si hay encabezado
    try:
        [float(x) for x in primera_linea.split()]
        skip = 0  # No es encabezado
    except ValueError:
        skip = 1  # Es encabezado

    # Intentar leer con diferentes separadores
    try:
        datos = pd.read_csv(archivo, sep=r"\s+", comment='#', header=None, skiprows=skip, dtype={0: float, 1: float})
    except:
        datos = pd.read_csv(archivo, sep=';', comment='#', header=None, skiprows=skip, dtype={0: float, 1: float})

    
    longitudes_onda = datos.iloc[:, 0].values
    intensidades = datos.iloc[:, 1].values
    
    # Aplicar suavizado si es necesario
    if suavizado > 1:
        intensidades_suavizadas = uniform_filter1d(intensidades, size=suavizado)
    else:
        intensidades_suavizadas = intensidades
    
    # Calcular la media y desviación estándar en ventanas móviles
    medias = np.array([np.mean(intensidades_suavizadas[i:i+ventana]) for i in range(len(intensidades_suavizadas) - ventana)])
    stds = np.array([np.std(intensidades_suavizadas[i:i+ventana]) for i in range(len(intensidades_suavizadas) - ventana)])
    
    # Filtrar regiones que estén dentro del rango dado
    indices_planos = np.where((medias >= rango_central[0]) & (medias <= rango_central[1]) & (stds < np.median(stds) * 0.5))[0]
    
    if len(indices_planos) == 0:
        print("No se encontró una región plana con los criterios dados.")
        return None
    
    # Seleccionar la primera región plana detectada
    idx_mejor_region = indices_planos[0]
    mejor_media = medias[idx_mejor_region]
    mejor_std = stds[idx_mejor_region]
    region_x = longitudes_onda[idx_mejor_region:idx_mejor_region+ventana]
    region_y = intensidades[idx_mejor_region:idx_mejor_region+ventana]
    
    return mejor_media, mejor_std


def sonificar_espirales(archivo, rango_onda=(6500, 6700), tempo=200, duracion_nota=0.5,
                        salida_midi_emision=None, salida_midi_absorcion=None, salida_midi_completo=None,
                        ventana=100, suavizado=10, rango_central=(0.95, 1.05), instrumento_emision=0, instrumento_absorcion=24, nombre_archivo=None):
    puntos_sonificados = []
    # Cargar datos
    with open(archivo, 'r') as f:
        primera_linea = f.readline().strip()
    # Detectar si hay encabezado
    try:
        [float(x) for x in primera_linea.split()]
        skip = 0  # No es encabezado
    except ValueError:
        skip = 1  # Es encabezado
    # Intentar leer con diferentes separadores
    try:
        datos = pd.read_csv(archivo, sep=r"\s+", comment='#', header=None, skiprows=skip, dtype={0: float, 1: float})
    except:
        datos = pd.read_csv(archivo, sep=';', comment='#', header=None, skiprows=skip, dtype={0: float, 1: float})
    # Extraer longitudes de onda e intensidades
    todas_wavelengths = datos.iloc[:, 0].values
    todas_intensities = datos.iloc[:, 1].values
    # Filtrar la región de interés
    mask = (datos.iloc[:, 0] >= rango_onda[0]) & (datos.iloc[:, 0] <= rango_onda[1])
    wavelengths = datos.iloc[:, 0][mask].values
    intensities = datos.iloc[:, 1][mask].values
    # Calcular estadísticas
    mean_intensity, std_intensity = detectar_region_plana(archivo, ventana, suavizado, rango_central)

    if mean_intensity is None or std_intensity is None:
        print("No se puede continuar con la sonificación sin una región plana válida.")
        return
        
    min_intensity = np.min(todas_intensities)
    max_intensity = np.max(todas_intensities)

    archivo_nombre = os.path.splitext(os.path.basename(archivo))[0]

    # Asegurar que la carpeta de destino existe para los archivos MIDI
    for path_midi in [salida_midi_emision, salida_midi_absorcion, salida_midi_completo]:
        if path_midi is not None:
            carpeta_destino = os.path.dirname(path_midi)
            if carpeta_destino and not os.path.exists(carpeta_destino):
                os.makedirs(carpeta_destino, exist_ok=True)
    
    # Definir la escala pentatónica con nombres de notas
    pentatonic_scale = [("A", 69), ("C", 72), ("D", 74), ("E", 76), ("G", 79)]
    octaves = [-24, -12, 0, 12, 24, 36, 48]  # 7 octavas desde -2 hasta +4
    full_scale = [(name, note + octave) for octave in octaves for name, note in pentatonic_scale]
    
    # Definir step_size basado en el rango de intensidades
    num_notes = len(full_scale)
    step_size = (max_intensity - min_intensity) / num_notes  # Ajustar según el rango de amplitudes
    
    # Crear archivos MIDI para emisión y absorción
    midi_emision = MIDIFile(1)
    midi_emision.addTempo(0, 0, tempo)
    # midi_emision.addProgramChange(0, 0, 0, instrumento_emision)  # Eliminado para dejar el MIDI crudo
    
    midi_absorcion = MIDIFile(1)
    midi_absorcion.addTempo(0, 0, tempo)
    # midi_absorcion.addProgramChange(0, 0, 0, instrumento_absorcion)  # Eliminado para dejar el MIDI crudo
    
    midi_completo = MIDIFile(2)  # Dos canales: 0 = emisión, 1 = absorción
    midi_completo.addTempo(0, 0, tempo)
    midi_completo.addTempo(1, 0, tempo)
    # midi_completo.addProgramChange(0, 0, 0, instrumento_emision)  # Eliminado para dejar el MIDI crudo
    # midi_completo.addProgramChange(1, 1, 0, instrumento_absorcion)  # Eliminado para dejar el MIDI crudo
    
    for i, intensity in enumerate(intensities):
        tiempo = i * duracion_nota  # Asegurar que ambos MIDI estén sincronizados
        index = int((intensity - min_intensity) / step_size)
        index = max(0, min(index, num_notes - 1))  # Asegurar índice válido
        note_name, note = full_scale[index]
        if intensity > mean_intensity:  # Emisión
            midi_emision.addNote(0, 0, note, tiempo, duracion_nota, 100)
            midi_completo.addNote(0, 0, note, tiempo, duracion_nota, 100)
            midi_absorcion.addNote(0, 0, 0, tiempo, duracion_nota, 0)  # Silencio en absorción
        else:  # Absorción
            midi_absorcion.addNote(0, 0, note, tiempo, duracion_nota, 100)
            midi_completo.addNote(1, 1, note, tiempo, duracion_nota, 100)
            midi_emision.addNote(0, 0, 0, tiempo, duracion_nota, 0)  # Silencio en emisión
        puntos_sonificados.append((wavelengths[i], intensity))
    # Guardar archivos MIDI
    with open(salida_midi_emision, "wb") as output_file:
        midi_emision.writeFile(output_file)
    print(f"Archivo MIDI de emisión guardado como '{salida_midi_emision}'")
    
    with open(salida_midi_absorcion, "wb") as output_file:
        midi_absorcion.writeFile(output_file)
    print(f"Archivo MIDI de absorción guardado como '{salida_midi_absorcion}'")

    # Crear midi_completo sumando eventos de ambos archivos
    # Leer eventos de ambos archivos y agregarlos a midi_completo
    # (Esto es redundante si ya se agregan arriba, pero se asegura integridad)
    # Si se requiere, aquí se puede implementar la suma real de eventos
    with open(salida_midi_completo, "wb") as f:
        midi_completo.writeFile(f)
    print(f"Archivo MIDI completo guardado como '{salida_midi_completo}'")
    

    # Mapeo de colores para cada nota
    note_colors = {
        "A": "blue",
        "C": "green",
        "D": "orange",
        "E": "purple",
        "G": "red"
    }

    fig, axs = plt.subplots(2, 1, figsize=(12, 12), gridspec_kw={'height_ratios': [1, 1]})
    
    # --- PRIMER GRÁFICO: Espectro completo con la región resaltada ---
    axs[0].plot(todas_wavelengths, todas_intensities, color="gray", alpha=0.7, label="Espectro completo")
    axs[0].axvspan(rango_onda[0], rango_onda[1], color='yellow', alpha=0.3, label="Región sonificada")
    # Líneas de referencia
    axs[0].axhline(y=mean_intensity, color="black", linestyle="-", linewidth=1.5, label="Media de intensidades")
    axs[0].axhline(y=mean_intensity + 1*std_intensity, color="green", linestyle="-", linewidth=1.5)
    axs[0].axhline(y=mean_intensity - 1*std_intensity, color="red", linestyle="-", linewidth=1.5)
    axs[0].set_xlabel("Longitud de onda (Å)")
    axs[0].set_ylabel("Intensidad normalizada")
    if nombre_archivo:
        axs[0].set_title(f"Espectro completo {nombre_archivo}")
    else:
        axs[0].set_title(f"Espectro completo")
    axs[0].legend()
    axs[0].grid()
    
    # --- SEGUNDO GRÁFICO: Región sonorizada con líneas de colores ---
    horizontal_lines = [min_intensity + i * step_size for i in range(num_notes)]
    
    axs[1].plot(wavelengths, intensities, label=f"Espectro normalizado {archivo_nombre}", color="blue")

    # Separar puntos de absorción y emisión
    absorcion_mask = intensities < 1
    emision_mask = intensities > 1
    
    axs[1].scatter(wavelengths[absorcion_mask], intensities[absorcion_mask], color="blue", s=20, label="Absorción (Azul)", zorder=3)
    axs[1].scatter(wavelengths[emision_mask], intensities[emision_mask], color="red", s=20, label="Emisión (Rojo)", zorder=3)
 
    
    # Agregar líneas de colores para cada nota
    for i, pos in enumerate(horizontal_lines):
        note_name, _ = full_scale[i]
        color = note_colors[note_name]  # Seleccionar color basado en la nota
        
        axs[1].axhline(y=pos, linestyle='--', color=color, alpha=0.7, linewidth=1)
        axs[1].text(max(wavelengths) + 5, pos, note_name, color=color, fontsize=10, verticalalignment='center')
    
    # Líneas de referencia
    axs[1].axhline(y=mean_intensity, color="black", linestyle="-", linewidth=1.5, label="Media de intensidades")
    axs[1].axhline(y=mean_intensity + 1*std_intensity, color="green", linestyle="-", linewidth=1.5)
    axs[1].axhline(y=mean_intensity - 1*std_intensity, color="red", linestyle="-", linewidth=1.5)
    
    axs[1].set_title("Sonorización del espectro con escala pentatónica")
    axs[1].set_xlabel("Longitud de onda (Å)")
    axs[1].set_ylabel("Intensidad normalizada")
    axs[1].grid(True)
    axs[1].legend(loc="upper left")
    axs[1].set_xlim([min(wavelengths), max(wavelengths) + 50])  # Espacio extra para la leyenda
    
    plt.tight_layout()  # Ajustar diseño para evitar solapamientos
    return fig


def sonificar_elipticas(archivo, rango_onda=(6500, 6700), tempo=200, duracion_nota=0.5,
                        salida_midi_emision=None, salida_midi_absorcion=None, salida_midi_completo=None,
                        ventana=100, suavizado=10, rango_central=(0.95, 1.05), instrumento_emision=0, instrumento_absorcion=24, nombre_archivo=None):
    # Cargar datos
    with open(archivo, 'r') as f:
        primera_linea = f.readline().strip()
    # Detectar si hay encabezado
    try:
        [float(x) for x in primera_linea.split()]
        skip = 0  # No es encabezado
    except ValueError:
        skip = 1  # Es encabezado
    # Intentar leer con diferentes separadores
    try:
        datos = pd.read_csv(archivo, sep=r"\s+", comment='#', header=None, skiprows=skip, dtype={0: float, 1: float})
    except:
        datos = pd.read_csv(archivo, sep=';', comment='#', header=None, skiprows=skip, dtype={0: float, 1: float})
    # Extraer longitudes de onda e intensidades
    todas_wavelengths = datos.iloc[:, 0].values
    todas_intensities = datos.iloc[:, 1].values
    # Filtrar la región de interés
    mask = (datos.iloc[:, 0] >= rango_onda[0]) & (datos.iloc[:, 0] <= rango_onda[1])
    wavelengths = datos.iloc[:, 0][mask].values
    intensities = datos.iloc[:, 1][mask].values
    mean_intensity, std_intensity = detectar_region_plana(archivo, ventana, suavizado, rango_central)

    if mean_intensity is None or std_intensity is None:
        print("No se puede continuar con la sonificación sin una región plana válida.")
        return
    
    min_intensity = np.min(todas_intensities)
    max_intensity = np.max(todas_intensities)
    archivo_nombre = os.path.splitext(os.path.basename(archivo))[0]
    # Definir nombres de salida personalizados si no se pasan explícitamente
    if salida_midi_emision is None:
        salida_midi_emision = f"{archivo_nombre}_emisión.mid"
    if salida_midi_absorcion is None:
        salida_midi_absorcion = f"{archivo_nombre}_absorción.mid"
    if salida_midi_completo is None:
        salida_midi_completo = f"{archivo_nombre}.mid"
    # Definir la escala pentatónica con nombres de notas
    pentatonic_scale = [("A", 69), ("C", 72), ("D", 74), ("E", 76), ("G", 79)]
    octaves = [-24, -12, 0, 12, 24, 36]  # 6 octavas desde -2 hasta +3
    # Expandir la escala a múltiples octavas con nombres
    full_scale = [(name, note + octave) for octave in octaves for name, note in pentatonic_scale]
    num_notes = len(full_scale)
    step_size = 1.05 / num_notes  # Ajustar según el rango de amplitudes (0 a 2)
    # Crear archivos MIDI separados para emisión y absorción
    midi_emision = MIDIFile(1)
    midi_absorcion = MIDIFile(1)
    midi_emision.addTempo(0, 0, tempo)
    midi_absorcion.addTempo(0, 0, tempo)
    midi_completo = MIDIFile(2)  # Dos canales: 0 = emisión, 1 = absorción
    midi_completo.addTempo(0, 0, tempo)
    midi_completo.addTempo(1, 0, tempo)
    puntos_sonificados = []
    for i, intensity in enumerate(intensities):
        index = int((intensity - min_intensity) / step_size)
        index = max(0, min(index, num_notes - 1))  # Asegurar índice válido
        note_name, note = full_scale[index]
        tiempo = i * duracion_nota
        if intensity >= 1:  # Emisión
            midi_emision.addNote(0, 0, note + 12, tiempo, duracion_nota, 100)  # Octava más alta
            midi_completo.addNote(0, 0, note, tiempo, duracion_nota, 100)
            midi_absorcion.addNote(0, 0, 0, tiempo, duracion_nota, 0)  # Silencio en absorción
        else:  # Absorción
            midi_absorcion.addNote(0, 0, note - 12, tiempo, duracion_nota, 100)  # Octava más baja
            midi_completo.addNote(1, 1, note, tiempo, duracion_nota, 100)
            midi_emision.addNote(0, 0, 0, tiempo, duracion_nota, 0)  # Silencio en emisión
        puntos_sonificados.append((wavelengths[i], intensity))
    # Guardar archivos MIDI
    with open(salida_midi_emision, "wb") as output_file:
        midi_emision.writeFile(output_file)
    with open(salida_midi_absorcion, "wb") as output_file:
        midi_absorcion.writeFile(output_file)
    with open(salida_midi_completo, "wb") as f:
        midi_completo.writeFile(f)
    print(f"Archivo MIDI de absorción guardado como '{salida_midi_completo}'")
    
    print(f"Archivos MIDI guardados como '{salida_midi_emision}' y '{salida_midi_absorcion}'")
    
    # Mapeo de colores para cada nota
    note_colors = {
        "A": "blue",
        "C": "green",
        "D": "orange",
        "E": "purple",
        "G": "red"
    }

    fig, axs = plt.subplots(2, 1, figsize=(12, 12), gridspec_kw={'height_ratios': [1, 1]})
    
    # --- PRIMER GRÁFICO: Espectro completo con la región resaltada ---
    axs[0].plot(todas_wavelengths, todas_intensities, color="gray", alpha=0.7, label="Espectro completo")
    axs[0].axvspan(rango_onda[0], rango_onda[1], color='yellow', alpha=0.3, label="Región sonificada")
    
    # Líneas de referencia
    axs[0].axhline(y=mean_intensity, color="black", linestyle="-", linewidth=1.5, label="Media de intensidades")
    axs[0].axhline(y=mean_intensity + 1*std_intensity, color="green", linestyle="-", linewidth=1.5)
    axs[0].axhline(y=mean_intensity - 1*std_intensity, color="red", linestyle="-", linewidth=1.5)
    
    axs[0].set_xlabel("Longitud de onda (Å)")
    axs[0].set_ylabel("Intensidad normalizada")
    axs[0].set_title(f"Espectro completo {archivo_nombre}")
    axs[0].legend()
    axs[0].grid()
    
    # --- SEGUNDO GRÁFICO: Región sonorizada con líneas de colores ---
    horizontal_lines = [min_intensity + i * step_size for i in range(num_notes)]
    
    axs[1].plot(wavelengths, intensities, label=f"Espectro normalizado {archivo_nombre}", color="blue")
    
    # Separar puntos de absorción y emisión
    absorcion_mask = intensities < 1
    emision_mask = intensities > 1
    
    axs[1].scatter(wavelengths[absorcion_mask], intensities[absorcion_mask], color="blue", s=20, label="Absorción (Azul)", zorder=3)
    axs[1].scatter(wavelengths[emision_mask], intensities[emision_mask], color="red", s=20, label="Emisión (Rojo)", zorder=3)

    
    # Agregar líneas de colores para cada nota
    for i, pos in enumerate(horizontal_lines):
        note_name, _ = full_scale[i]
        color = note_colors[note_name]  # Seleccionar color basado en la nota
        
        axs[1].axhline(y=pos, linestyle='--', color=color, alpha=0.7, linewidth=1)
        axs[1].text(max(wavelengths) + 5, pos, note_name, color=color, fontsize=10, verticalalignment='center')
    
    # Líneas de referencia
    axs[1].axhline(y=mean_intensity, color="black", linestyle="-", linewidth=1.5, label="Media de intensidades")
    axs[1].axhline(y=mean_intensity + 1*std_intensity, color="green", linestyle="-", linewidth=1.5)
    axs[1].axhline(y=mean_intensity - 1*std_intensity, color="red", linestyle="-", linewidth=1.5)
    
    axs[1].set_title("Sonorización del espectro con escala pentatónica")
    axs[1].set_xlabel("Longitud de onda (Å)")
    axs[1].set_ylabel("Intensidad normalizada")
    axs[1].grid(True)
    axs[1].legend(loc="upper left")
    axs[1].set_xlim([min(wavelengths), max(wavelengths) + 50])  # Espacio extra para la leyenda
    
    plt.tight_layout()  # Ajustar diseño para evitar solapamientos
    return fig


def tipo(archivo, rango_onda=(3800, 4200)):
    # Cargar datos
    datos = pd.read_csv(archivo, sep=';')
    
    # Filtrar datos dentro del rango de longitud de onda
    mask = (datos.iloc[:, 0] >= rango_onda[0]) & (datos.iloc[:, 0] <= rango_onda[1])
    wavelengths = datos.iloc[:, 0][mask].values
    intensities = datos.iloc[:, 1][mask].values

    media = np.mean(intensities)

    if media>2:
        tipo = "Irregular"
    if media <2 and media>1:
        tipo = "Espiral"
    if media<1:
        tipo = "Eliptica"


    print(f"Galaxia es {tipo}, con media {media}")
    return(tipo)


def convertir_midi_a_wav(nombre_midi, nombre_wav):
    sf2 = "default.sf2"  # soundfont (asegúrate de tenerlo)
    FluidSynth(sound_font=sf2).midi_to_audio(nombre_midi, nombre_wav)
    
def convertir_midi_a_wav_musescore(midi_file, wav_file, musescore_path="C:/Program Files/MuseScore 4/bin/MuseScore4.exe"):
    """
    Convierte un archivo MIDI a WAV usando MuseScore 4.
    """
    if not os.path.isfile(musescore_path):
        raise FileNotFoundError("MuseScore no se encontró en la ruta indicada.")

    subprocess.run([musescore_path, midi_file, "-o", wav_file], check=True)
    
def mezclar_wavs(wav1, wav2, salida="mezcla.wav"):
    audio1 = AudioSegment.from_wav(wav1)
    audio2 = AudioSegment.from_wav(wav2)
    mezcla = audio1.overlay(audio2)
    mezcla.export(salida, format="wav")

