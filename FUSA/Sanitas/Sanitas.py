import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import re

RUTA_SALIDA = os.path.join(os.path.expanduser("~"), "Procesamiento_Resultados")

def aplicar_reglas_de_renombrado(nombre_archivo: str) -> str:
    nombre, extension = os.path.splitext(nombre_archivo)
    extension = extension.lower()

    if extension == ".xml":
        return nombre_archivo  # No renombrar XML

    if extension == ".pdf" and nombre.startswith("FEV_P"):
        return nombre_archivo
    if extension == ".json" and re.match(r'^P[A-Z0-9]+$', nombre):
        return nombre_archivo

    partes = nombre.split(";")
    base = partes[1] if len(partes) >= 2 else nombre

    base = base.strip().replace(" ", "").upper()
    base = re.sub(r'[\\/*?:"<>|]', "", base)

    if extension == ".pdf":
        nuevo_nombre = f"FEV_P{base}"
    elif extension == ".json":
        base = base.split("_")[-1].upper()
        nuevo_nombre = f"{base}"  # Prefijo que lleva el nombre del archivo 
    else:
        nuevo_nombre = base

    return nuevo_nombre + extension

def crear_directorio_de_respaldo(nombre_carpeta_base: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    respaldo_path = os.path.join(RUTA_SALIDA, "Backups", os.path.basename(nombre_carpeta_base), f"respaldo_{timestamp}")
    os.makedirs(respaldo_path, exist_ok=True)
    return respaldo_path

def respaldar_archivo(ruta_origen: str, ruta_respaldo: str):
    os.makedirs(os.path.dirname(ruta_respaldo), exist_ok=True)
    shutil.copy2(ruta_origen, ruta_respaldo)

def generar_log(nombre_carpeta_base: str, entradas: list, renombrados: int, errores: int):
    log_dir = os.path.join(RUTA_SALIDA, "Logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"log_{os.path.basename(nombre_carpeta_base)}.txt")

    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"Registro de cambios - {datetime.now()}\n")
        log.write(f"{'-'*60}\n")
        for entrada in entradas:
            log.write(f"{entrada}\n")
        log.write(f"{'-'*60}\n")
        log.write(f"Total renombrados: {renombrados}\n")
        log.write(f"Total errores o duplicados: {errores}\n")

def recolectar_archivos_recursivamente(directorio):
    archivos = []
    for carpeta_raiz, _, archivos_en_carpeta in os.walk(directorio):
        for archivo in archivos_en_carpeta:
            archivos.append(os.path.join(carpeta_raiz, archivo))
    return archivos

def extraer_factura_desde_nombre_xml(nombre_archivo: str) -> str:
    partes = nombre_archivo.split(";")
    if len(partes) >= 2:
        return partes[1].strip().upper()
    return None

def extraer_numero_factura(nombre_archivo: str) -> str:
    nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
    for prefijo in ["FEV_P", "F-", "X-", "R-", "P"]:
        if nombre_sin_ext.startswith(prefijo):
            return nombre_sin_ext[len(prefijo):]
    return nombre_sin_ext

def procesar_archivos_en_carpeta(carpeta: str) -> tuple:
    respaldo_dir = crear_directorio_de_respaldo(carpeta)
    log_entries = []
    renombrados = 0
    errores = 0

    archivos = recolectar_archivos_recursivamente(carpeta)
    pdf_facturas = {}
    archivos_por_factura = {}

    # Renombrar y respaldar archivos
    for ruta_original in archivos:
        archivo = os.path.basename(ruta_original)
        extension = os.path.splitext(archivo)[1].lower()

        try:
            ruta_respaldo = os.path.join(respaldo_dir, os.path.relpath(ruta_original, carpeta))
            respaldar_archivo(ruta_original, ruta_respaldo)

            # Renombrar solo si no es XML
            if extension != ".xml":
                nuevo_nombre = aplicar_reglas_de_renombrado(archivo)
            else:
                nuevo_nombre = archivo

            ruta_nueva = os.path.join(os.path.dirname(ruta_original), nuevo_nombre)

            if archivo != nuevo_nombre:
                if os.path.exists(ruta_nueva):
                    log_entries.append(f"[Ya existe archivo destino] {ruta_nueva}")
                    errores += 1
                    ruta_nueva = ruta_original
                else:
                    os.rename(ruta_original, ruta_nueva)
                    log_entries.append(f"[Renombrado] {archivo} -> {nuevo_nombre}")
                    renombrados += 1
            else:
                ruta_nueva = ruta_original

            archivo_final = os.path.basename(ruta_nueva)

            if extension == ".xml":
                factura_id = extraer_factura_desde_nombre_xml(archivo_final)
            else:
                factura_id = extraer_numero_factura(archivo_final)

            if factura_id:
                archivos_por_factura.setdefault(factura_id, []).append(ruta_nueva)
                if extension == ".pdf":
                    pdf_facturas[factura_id] = ruta_nueva

        except Exception as e:
            log_entries.append(f"[ERROR] {ruta_original} - {str(e)}")
            errores += 1

    # Crear carpetas solo para PDFs
    for factura_id in pdf_facturas.keys():
        carpeta_destino = os.path.join(carpeta, factura_id)
        os.makedirs(carpeta_destino, exist_ok=True)

    # Mover PDFs y XMLs a las carpetas solo si hay PDF
    for factura_id, rutas in archivos_por_factura.items():
        if factura_id not in pdf_facturas:
            continue

        carpeta_destino = os.path.join(carpeta, factura_id)

        for ruta in rutas:
            extension = os.path.splitext(ruta)[1].lower()
            if extension not in ['.pdf', '.xml']:
                continue

            archivo = os.path.basename(ruta)
            ruta_destino = os.path.join(carpeta_destino, archivo)

            try:
                if os.path.abspath(ruta) != os.path.abspath(ruta_destino):
                    if os.path.exists(ruta_destino):
                        log_entries.append(f"[Ya existe archivo destino] {ruta_destino}")
                        errores += 1
                        continue
                    shutil.move(ruta, ruta_destino)
                    log_entries.append(f"[Movido] {ruta} -> {ruta_destino}")
            except Exception as e:
                log_entries.append(f"[ERROR al mover] {ruta} - {str(e)}")
                errores += 1

    # MOVER JSONs A CARPETAS EXISTENTES QUE CONTENGAN EL MISMO NÚMERO AL FINAL DEL NOMBRE
    carpetas = [d for d in os.listdir(carpeta) if os.path.isdir(os.path.join(carpeta, d))]
    for ruta in archivos:
        extension = os.path.splitext(ruta)[1].lower()
        if extension != ".json":
            continue
        archivo = os.path.basename(ruta)
        nombre_sin_ext = os.path.splitext(archivo)[0]

        # Extraer número al final del nombre del JSON
        match = re.search(r'(\d+)$', nombre_sin_ext)
        if not match:
            continue
        numero_json = match.group(1)

        # Buscar carpeta que contenga ese número
        carpeta_destino = None
        for carpeta_nombre in carpetas:
            if numero_json in carpeta_nombre:
                carpeta_destino = os.path.join(carpeta, carpeta_nombre)
                break

        if carpeta_destino:
            ruta_destino = os.path.join(carpeta_destino, archivo)
            try:
                if os.path.abspath(ruta) != os.path.abspath(ruta_destino):
                    if os.path.exists(ruta_destino):
                        log_entries.append(f"[Ya existe archivo destino JSON] {ruta_destino}")
                        errores += 1
                        continue
                    shutil.move(ruta, ruta_destino)
                    log_entries.append(f"[Movido JSON] {ruta} -> {ruta_destino}")
            except Exception as e:
                log_entries.append(f"[ERROR al mover JSON] {ruta} - {str(e)}")
                errores += 1

    generar_log(carpeta, log_entries, renombrados, errores)
    return renombrados, errores

# ---------------- INTERFAZ GRÁFICA ----------------

def seleccionar_carpeta_y_ejecutar():
    carpeta = filedialog.askdirectory(title="Selecciona la carpeta de archivos")
    if carpeta:
        renombrados, errores = procesar_archivos_en_carpeta(carpeta)
        mensaje = (
            f"✅ Proceso finalizado.\n\n"
            f"📁 Archivos renombrados: {renombrados}\n"
            f"⚠️ Errores o duplicados: {errores}\n\n"
            f"📦 Respaldos y logs están en:\n{RUTA_SALIDA}"
        )
        messagebox.showinfo("Resultado", mensaje)
        ventana.destroy()

# ---------------- VENTANA PRINCIPAL ----------------

ventana = tk.Tk()
ventana.title("📁 Gestor Inteligente de Archivos - ISP FUSA SANITAS")
ventana.geometry("510x300")
ventana.configure(bg="#fff9f0")
ventana.resizable(False, False)

# Colores institucionales Sanitas
COLOR_TEXTO = "#333333"
COLOR_PRINCIPAL = "#00A1E4"
COLOR_SECUNDARIO = "#555555"
COLOR_BOTON = "#00A1E4"
COLOR_BOTON_HOVER = "#0078A6"

tk.Label(ventana, text="🔧 Herramienta de respaldo y renombrado automático",
         bg=ventana["bg"], fg=COLOR_SECUNDARIO,
         font=("Helvetica", 14, "bold")).pack(pady=10)

tk.Label(ventana, text="Optimiza tu gestión documental con un solo clic",
         bg=ventana["bg"], fg=COLOR_TEXTO,
         font=("Helvetica", 11, "italic")).pack(pady=2)

tk.Label(ventana,
         text=("🗂️ Esta herramienta realiza automáticamente:\n"
               "• Respaldo seguro de tus archivos antes de renombrarlos\n"
               "• Renombrado inteligente (PDF/JSON), no XML\n"
                "📌 Ideal para manejo de facturas, reportes y documentos técnicos."),
         bg=ventana["bg"], fg=COLOR_TEXTO,
         font=("Helvetica", 10), justify="left").pack(padx=20)

tk.Button(ventana,
          text="📂 Seleccionar carpeta y procesar archivos",
          command=seleccionar_carpeta_y_ejecutar,
          bg=COLOR_BOTON, fg="white",
          font=("Helvetica", 12, "bold"),
          padx=20, pady=10,
          activebackground=COLOR_BOTON_HOVER).pack(pady=15)

tk.Label(ventana, text="© 2025 Derechos Reservados - IPS FUSA",
         bg=ventana["bg"], fg="#888",
         font=("Helvetica", 9, "italic")).pack(side="bottom", pady=10)

ventana.mainloop()
