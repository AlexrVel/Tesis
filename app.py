import streamlit as st
import os
from funciones import tipo, sonificar_espirales, sonificar_elipticas 
from funciones import convertir_midi_a_wav, mezclar_wavs, convertir_midi_a_wav_musescore

st.set_page_config(page_title="🎵 Sonificación de Galaxias", layout="centered")

st.title("🎵 Sonificación de Espectros de Galaxias")

# Subida de archivo
archivo = st.file_uploader("📂 Carga un archivo .txt del espectro", type=["txt"])

if archivo is not None:
    # Guardar archivo temporalmente
    archivo_path = os.path.join("espectro_temporal.txt")
    with open(archivo_path, "wb") as f:
        f.write(archivo.read())

    # Determinar tipo de galaxia
    st.subheader("🔍 Clasificación automática")
    tipo_galaxia = tipo(archivo_path)
    st.write(f"La galaxia fue clasificada como: **{tipo_galaxia}**")

    # Parámetros personalizables
    st.subheader("🎛 Parámetros de Sonificación")
    rango_ini, rango_fin = st.slider("Rango de longitud de onda a sonificar (Å)", 4000, 8000, (6500, 6700))
    tempo = st.slider("Tempo (BPM)", 60, 300, 200)
    duracion = st.slider("Duración por nota (segundos)", 0.1, 1.0, 0.5, step=0.1)

    # Ejecutar sonificación

    if st.button("🎶 Sonificar espectro"):
        if tipo_galaxia == "Espiral":
            fig = sonificar_espirales(archivo_path, rango_onda=(rango_ini, rango_fin), tempo=tempo, duracion_nota=duracion)
            archivo_emision = "salida_emision.mid"
            archivo_absorcion = "salida_absorcion.mid"
            archivo_completo = "salida_completo.mid"

        elif tipo_galaxia == "Eliptica":
            fig = sonificar_elipticas(archivo_path, rango_onda=(rango_ini, rango_fin), tempo=tempo, duracion_nota=duracion)
            archivo_emision = "elipticas_emision.mid"
            archivo_absorcion = "elipticas_absorcion.mid"
            archivo_completo = "salida_completo.mid"
            
        else:
            st.warning("Este tipo de galaxia es 'Irregular'. No se ha definido una función de sonificación específica.")
            st.stop()
            

        # Mostrar gráfica
        st.subheader("📈 Gráfica de la Sonificación")
        st.pyplot(fig)

        # Mostrar enlaces para descargar archivos MIDI
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇️ Descargar MIDI de Emisión", data=open(archivo_emision, "rb"), file_name=archivo_emision)
        with col2:
            st.download_button("⬇️ Descargar MIDI de Absorción", data=open(archivo_absorcion, "rb"), file_name=archivo_absorcion)

        # Convertir a WAV
        #convertir_midi_a_wav(archivo_emision, "emision.wav")
        #convertir_midi_a_wav(archivo_absorcion, "absorcion.wav")

        # Mezclar y reproducir
        #mezclar_wavs("emision.wav", "absorcion.wav", salida="mezcla.wav")
        #st.subheader("🎧 Reproductor de Sonificación Combinada")
        #st.audio("mezcla.wav", format="audio/wav")
        
        # Convertir a WAV
        convertir_midi_a_wav_musescore(archivo_emision, "emision.wav")
        convertir_midi_a_wav_musescore(archivo_absorcion, "absorcion.wav")
        convertir_midi_a_wav_musescore(archivo_completo, "completo.wav")

    # Mezclar y reproducir
        #mezclar_wavs("emision.wav", "absorcion.wav", salida="mezcla.wav")
        st.subheader("🎧 Reproductor de Sonificación")
        st.audio("completo.wav", format="audio/wav")



        # Mostrar enlaces para descargar archivos MIDI
        st.download_button("⬇️ Descargar Wav completo",data=open("completo.wav", "rb"), file_name="Sonificación del espectro.wav")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇️ Descargar MIDI de Emisión", data=open("salida_emision.mid", "rb"), file_name="salida_emision.mid")
        with col2:
            st.download_button("⬇️ Descargar MIDI de Absorción", data=open("salida_absorcion.mid", "rb"), file_name="salida_absorcion.mid")
        
        #convertir_midi_a_wav(archivo_emision, "emision.wav")
        #convertir_midi_a_wav(archivo_absorcion, "absorcion.wav")


        #mezclar_wavs("emision.wav", "absorcion.wav", salida="mezcla.wav")
        #st.audio("mezcla.wav", format="audio/wav")        
        
        st.subheader(" Gráfica de la Sonificación")
        st.pyplot(fig)
        st.success("✅ Sonificación completada. Archivos MIDI disponibles.")
