# app.py
import streamlit as st
import os
from src.data_loader import load_galaxy_data, list_available_galaxies
from src.sound_mapper import map_values_to_midi_notes, map_to_velocity
from src.midi_generator import create_midi_file
import plotly.graph_objects as go
from src.midi_generator import convert_midi_to_wav

# Constantes locales
DATA_DIR = "data"
MIDI_OUTPUT = "output.mid"
WAV_OUTPUT = "output.wav"
SOUNDFONT_PATH = "FluidR3_GM.sf2"

# Streamlit le crea webs sin complique y las llama desde python
st.set_page_config(page_title="Sonificación Galáctica", layout="centered")
st.title("🌌 Sonificación de Galaxias")
st.write("Convierte datos astronómicos en música 🎶 usando MIDI")

# Paso 1: Selección de galaxia
galaxias = list_available_galaxies(DATA_DIR)
galaxia = st.selectbox("Selecciona una galaxia:", galaxias)

if galaxia:
    file_path = os.path.join(DATA_DIR, galaxia)
    data = load_galaxy_data(file_path)

    if data is not None:
        # Paso 2: Visualización
        st.subheader("🔭 Visualización de datos")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data[:, 0], y=data[:, 1], mode='lines', name=galaxia))
        fig.update_layout(title=f"Datos de {galaxia}", xaxis_title="X", yaxis_title="Y")
        st.plotly_chart(fig)

        # Paso 3: Generar MIDI
        st.subheader("🎼 Generar sonido")
        scale_range = st.slider("Rango de notas (C3 a C5)", 36, 84, (60, 72))

        midi_generado = False

        if st.button("🎹 Generar MIDI"):
            notas = map_values_to_midi_notes(data, scale=scale_range)
            velocidades = map_to_velocity(data)
            create_midi_file(notas, velocidades, output_file=MIDI_OUTPUT)
            st.info("✅ Generando un momento por favor...")

            try:
                convert_midi_to_wav(MIDI_OUTPUT, WAV_OUTPUT, SOUNDFONT_PATH)
                st.success("✅ Archivo generado con éxito")
                midi_generado = True
            except FileNotFoundError as fe:
                st.error(f"❌ Archivo no encontrado: {fe}")
            except Exception as e:
                st.error(f"❌ Error inesperado durante la conversión: {e}")

        # Paso 4: Descargar
        if os.path.exists(MIDI_OUTPUT) and midi_generado:
            with open(MIDI_OUTPUT, "rb") as f:
                st.download_button("⬇️ Descargar MIDI", f, file_name=MIDI_OUTPUT)
                if os.path.exists(WAV_OUTPUT):
                    st.subheader("🔊 Previsualizar sonido")
                    st.audio(WAV_OUTPUT, format="audio/wav")
                st.info("🎧 Consejo: Si el archivo MIDI te suena raro, intenta bajar el rango de notas o tempo.")
