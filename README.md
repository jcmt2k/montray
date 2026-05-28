# MonTray 📡

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-v18%2B-green.svg)](https://nodejs.org/)
[![Electron](https://img.shields.io/badge/Electron-v30.0.2-blue.svg)](https://www.electronjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-v6.4%2B-violet.svg)](https://www.riverbankcomputing.com/software/pyqt/)

**MonTray** es una aplicación de escritorio ultraligera y moderna diseñada para el monitoreo en tiempo real de servidores, sitios web, APIs y direcciones IP directamente desde la bandeja del sistema (*System Tray*). 

Este repositorio es único porque ofrece **dos implementaciones completas e independientes** de la misma aplicación, permitiéndote elegir la que mejor se adapte a tus necesidades de consumo y diseño:
1.  **Versión Electron (Web-stack):** Con una espectacular interfaz de usuario *Glassmorphism*, animaciones fluidas, mini-gráficas SVG en tiempo real y toda la potencia de las tecnologías web.
2.  **Versión Python (Nativa - PyQt6):** Optimizada para un consumo de recursos sumamente bajo (con un ejecutable portable de ~25 MB frente a los más de 80 MB de Electron), con un renderizado nativo de alto rendimiento en el canvas mediante `QPainter` y una perfecta integración con el entorno de escritorio.

---

## 📊 Tabla Comparativa de Implementaciones

| Característica | 🌐 Versión Electron | 🐍 Versión Python (PyQt6) |
| :--- | :--- | :--- |
| **Tecnología Principal** | JavaScript / Node.js / HTML / CSS | Python 3 / PyQt6 |
| **Interfaz de Usuario** | Premium *Glassmorphism* (HTML/CSS) | Diseño nativo premium adaptado |
| **Gráficos de Latencia** | Vectores SVG dinámicos reactivos | Canvas de alta velocidad (`QPainter`) |
| **Consumo de CPU/RAM** | Moderado (arquitectura Chromium) | **Sumamente bajo** (nativo C++/Python) |
| **Tamaño del Instalador** | ~80 MB (.deb / .AppImage) | **~25 MB** (.deb / ejecutable binario) |
| **Dependencias del Sistema** | Node.js para desarrollo | Python 3 + venv para desarrollo |
| **Soporte Autostart** | Configuración nativa de Linux | Registro en archivo `.desktop` |

---

## ✨ Características Comunes a Ambas Versiones

*   **Bandeja de Sistema (System Tray) Activa:** Control total en segundo plano. La aplicación se minimiza de forma nativa a la bandeja. El icono dinámico cambia de color según el estado global de tus monitores:
    *   🟢 **Verde (Online):** Todos los sitios activos responden correctamente.
    *   🔴 **Rojo (Offline):** Al menos un sitio web está caído o reporta un error de red.
    *   🟡 **Amarillo (Warning):** Un monitor HTTP responde con un código de error de servidor (>= 400).
    *   ⚫ **Gris (Idle):** El monitoreo global está en pausa o no hay sitios configurados.
*   **Doble Tipo de Monitoreo:**
    *   🌐 **Monitoreo HTTP / HTTPS:** Peticiones web para validar que el servidor web devuelva códigos exitosos (2xx/3xx). Los errores del lado del servidor se catalogan como advertencias.
    *   ⚡ **Monitoreo Ping / ICMP:** Envío de paquetes ICMP para verificar la conectividad de hosts e IPs de red con cálculo preciso de latencia en milisegundos.
*   **Notificaciones Nativas:** Alertas de escritorio flotantes e inmediatas al instante en que un monitor se cae o cuando se recupera con éxito, mostrando el tiempo de respuesta o el error reportado.
*   **Gráficos en Tiempo Real:** Mini-gráficas de barras reactivas que muestran el historial de latencia y estado de los últimos 20 chequeos en tiempo real.
*   **Intervalos Flexibles:** Configura la frecuencia de comprobación de forma global o define intervalos personalizados por sitio.
*   **Almacenamiento Local:** Configuración guardada en texto plano bajo un estándar seguro en `~/.config/montray/sites.json`.

---

## 📁 Estructura del Repositorio

El proyecto está organizado en módulos claros e independientes:

```bash
montray/
├── electron/              # Código fuente de la versión de Electron
│   ├── assets/            # Iconos locales para la versión de Electron
│   ├── src/
│   │   ├── index.html     # Dashboard principal
│   │   ├── renderer.js    # Lógica del cliente
│   │   └── styles.css     # Estilos premium CSS
│   ├── main.js            # Proceso principal de Electron
│   ├── preload.js         # Puente de comunicación seguro IPC
│   └── package.json       # Configuración y dependencias de npm
├── python/                # Código fuente de la versión de Python
│   ├── assets/            # Iconos locales para la versión de Python
│   ├── main.py            # Lógica y UI PyQt6 de la aplicación
│   ├── build.py           # Script de compilación multiplataforma y generación .deb
│   └── requirements.txt   # Dependencias de Python
├── generate_icons.py      # Script automatizado para la creación de assets de iconos
├── LICENSE                # Licencia del proyecto (MIT)
└── README.md              # Documentación principal
```

---

## 🚀 Guía de Inicio Rápido y Desarrollo

Clona primero el repositorio en tu máquina local:
```bash
git clone https://github.com/jcmt2k/montray.git
cd montray
```

### 🌐 Opción A: Ejecutar la Versión Electron

#### 1. Navegar a la carpeta y descargar dependencias
```bash
cd electron
npm install
```

#### 2. Iniciar en modo desarrollo
```bash
npm start
```

---

### 🐍 Opción B: Ejecutar la Versión Python (PyQt6)

#### 1. Navegar a la carpeta y crear el entorno virtual
```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

#### 3. Iniciar la aplicación
```bash
python main.py
```

---

## 📦 Empaquetado y Distribución para Producción

Ambas versiones cuentan con scripts automatizados de compilación optimizados para Linux (generando ejecutables portables e instaladores Debian `.deb`).

### 🌐 Empaquetado en Electron

Utiliza `electron-builder` configurado de forma nativa:
```bash
cd electron
npm run dist
```
Los instaladores resultantes se generarán en `electron/dist/`:
*   `electron/dist/MonTray-1.0.0.AppImage` (Ejecutable portable)
*   `electron/dist/montray_1.0.0_amd64.deb` (Instalador de sistema para Debian/Ubuntu)

### 🐍 Empaquetado en Python

Utiliza un script a medida (`build.py`) que automatiza la compilación con `PyInstaller` y el empaquetado nativo con `dpkg-deb`:
```bash
cd python
source .venv/bin/activate
python build.py
```
El script generará el binario compilado y el instalador en `python/dist/`:
*   `python/dist/montray` (Ejecutable portable standalone compilado a C/Python)
*   `python/dist/montray-python_1.0.0_amd64.deb` (Instalador Debian nativo de solo **~25 MB** que instala el software en `/usr/bin/montray` y configura el acceso directo `.desktop`)

---

## 🎨 Generador de Iconos Dinámico (`generate_icons.py`)

El proyecto incluye un script en Python (`generate_icons.py`) que utiliza la biblioteca `Pillow` para dibujar matemáticamente y desde cero todos los iconos de la aplicación. Esto asegura que no existan imágenes corruptas o pixeladas.

Si necesitas regenerar los iconos del proyecto con colores o formas personalizadas:

#### 1. Asegúrate de tener Pillow en tu sistema
```bash
pip install Pillow
```

#### 2. Ejecutar el generador
```bash
python generate_icons.py
```
Este script actualizará automáticamente:
*   `assets/app-icon.png`: Icono de alta resolución con un gradiente elegante de color púrpura oscuro a azul slate, y un electrocardiograma (ECG) central con triple capa de resplandor de neón (cyan/púrpura).
*   `assets/icon-idle.png`: Icono plateado para el estado de espera.
*   `assets/icon-online.png`: Icono verde esmeralda brillante para estado correcto.
*   `assets/icon-offline.png`: Icono rojo vibrante para alertar de sistemas caídos.

---

## 🔒 Seguridad en Red Integrada

El monitoreo de latencia mediante Ping/ICMP interactúa con comandos de consola del sistema operativo (`ping`). Para prevenir ataques de **inyección de comandos (Command Injection)**, ambas implementaciones integran filtros rígidos de saneamiento mediante expresiones regulares en su backend:

*   **Electron (main.js):** Sanea estrictamente la dirección IP o Hostname ingresado antes de concatenarlo en el proceso hijo de Node.js.
*   **Python (main.py):** Limpia la dirección a través de la expresión regular `re.sub(r'[^a-zA-Z0-9.-]', '', self.address)` previo a la invocación de `subprocess.Popen`, garantizando que únicamente caracteres válidos e inofensivos de red sean ejecutados a nivel de consola.

---

## ✒️ Autor y Licencia

Desarrollado con dedicación por **Julio Mejía** ([jcmt2k@gmail.com](mailto:jcmt2k@gmail.com)).

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para obtener más detalles.
