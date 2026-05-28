import os
import sys
import shutil
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, 'dist')
BUILD_DIR = os.path.join(PROJECT_DIR, 'build')

print("🚀 Iniciando empaquetado multiplataforma para MonTray (Python)...")

# 1. Limpieza de compilaciones previas
def clean_dir(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

print("🧹 Limpiando directorios de salida antiguos...")
clean_dir(DIST_DIR)
clean_dir(BUILD_DIR)

# 2. Configurar parámetros de PyInstaller según plataforma
print("⚙️ Configurando opciones de compilación...")
separator = ';' if sys.platform == 'win32' else ':'
add_data_flag = f"assets{separator}assets"

# Determinar icono adecuado
if sys.platform == 'win32':
    icon_file = os.path.join(PROJECT_DIR, 'assets', 'icon.ico')
else:
    icon_file = os.path.join(PROJECT_DIR, 'assets', 'app-icon.png')

# Comando base de PyInstaller
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name=montray",
    f"--add-data={add_data_flag}",
    f"--icon={icon_file}",
    "main.py"
]

print(f"📦 Ejecutando PyInstaller: {' '.join(cmd)}")
try:
    subprocess.run(cmd, check=True, cwd=PROJECT_DIR)
    print("\n✅ ¡Ejecutable standalone creado con éxito en dist/!")
except subprocess.CalledProcessError as e:
    print(f"\n❌ Error al compilar con PyInstaller: {e}")
    sys.exit(1)

# 3. Construcción del instalador Debian (.deb) si estamos en Linux
if sys.platform != 'win32':
    print("\n🐧 Sistema operativo Linux detectado. Iniciando empaquetado Debian (.deb)...")
    
    TMP_DEB_DIR = os.path.join(DIST_DIR, 'tmp-deb')
    clean_dir(TMP_DEB_DIR)
    
    # Rutas para el layout debian
    paths = {
        'debian': os.path.join(TMP_DEB_DIR, 'DEBIAN'),
        'bin': os.path.join(TMP_DEB_DIR, 'usr', 'bin'),
        'desktop': os.path.join(TMP_DEB_DIR, 'usr', 'share', 'applications'),
        'pixmaps': os.path.join(TMP_DEB_DIR, 'usr', 'share', 'pixmaps')
    }
    
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
        
    # Copiar binario compilado a /usr/bin/montray
    compiled_bin = os.path.join(DIST_DIR, 'montray')
    target_bin = os.path.join(paths['bin'], 'montray')
    print("📁 Copiando binario ejecutable...")
    shutil.copy2(compiled_bin, target_bin)
    os.chmod(target_bin, 0o755)
    
    # Escribir DEBIAN/control
    print("✍️ Escribiendo archivo de control Debian...")
    control_content = """Package: montray-python
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Julio Mejia <jcmt2k@gmail.com>
Description: Monitoreo liviano de servidores y red (Versión Python)
 MonTray es una aplicación en bandeja de sistema elegante y moderna para el
 monitoreo en tiempo real de servidores, URLs e IPs. Esta versión en Python
 está optimizada con una interfaz gráfica nativa PyQt6 de bajo consumo que no
 requiere de Electron ni de navegadores embebidos, pesando apenas 25 MB.
"""
    with open(os.path.join(paths['debian'], 'control'), 'w', encoding='utf-8') as f:
        f.write(control_content)
        
    # Escribir acceso directo de escritorio .desktop
    print("✍️ Escribiendo archivo .desktop...")
    desktop_content = """[Desktop Entry]
Name=MonTray (Python)
Comment=Monitoreo de servidores en bandeja de sistema
Exec=/usr/bin/montray --hidden
Icon=montray-py
Terminal=false
Type=Application
Categories=Network;Utility;
StartupNotify=false
"""
    with open(os.path.join(paths['desktop'], 'montray-python.desktop'), 'w', encoding='utf-8') as f:
        f.write(desktop_content)
        
    # Copiar icono de la aplicación a pixmaps
    print("🖼️ Copiando icono de la app a pixmaps...")
    shutil.copy2(
        os.path.join(PROJECT_DIR, 'assets', 'app-icon.png'),
        os.path.join(paths['pixmaps'], 'montray-py.png')
    )
    
    # Compilar el .deb usando dpkg-deb
    print("🛠️ Compilando paquete .deb con dpkg-deb...")
    deb_outfile = os.path.join(DIST_DIR, 'montray-python_1.0.0_amd64.deb')
    
    try:
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", TMP_DEB_DIR, deb_outfile],
            check=True
        )
        print(f"\n✅ ¡Instalador Debian creado con éxito!")
        print(f"📦 Ubicación: {deb_outfile}")
        stats = os.stat(deb_outfile)
        print(f"⚖️ Peso del instalador: {(stats.st_size / 1024 / 1024).toFixed(2) if hasattr(stats.st_size, 'toFixed') else stats.st_size / (1024 * 1024):.2f} MB")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al construir el paquete .deb con dpkg-deb: {e}")
        sys.exit(1)
    finally:
        # Limpiar directorio temporal
        clean_dir(TMP_DEB_DIR)

print("\n✨ ¡Proceso de empaquetado finalizado!")
