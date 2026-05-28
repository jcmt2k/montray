# MonTray 📡

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-v18%2B-green.svg)](https://nodejs.org/)
[![Electron](https://img.shields.io/badge/Electron-v30.0.2-blue.svg)](https://www.electronjs.org/)

**MonTray** es una aplicación de escritorio ultraligera y moderna diseñada para el monitoreo en tiempo real de servidores, sitios web, APIs y direcciones IP directamente desde la bandeja del sistema (*System Tray*). Desarrollada con Electron y optimizada con una interfaz *Glassmorphism* elegante y reactiva, es la herramienta perfecta para desarrolladores y administradores de sistemas que necesitan supervisar la disponibilidad de su infraestructura sin consumir recursos de fondo significativos.

---

## ✨ Características Principales

*   **Bandeja de Sistema (System Tray) Activa:** Control total en segundo plano. La aplicación se minimiza de forma nativa a la bandeja. El icono dinámico cambia de color según el estado global de tus monitores:
    *   🟢 **Verde (Online):** Todos los sitios activos responden correctamente.
    *   🔴 **Rojo (Offline / Advertencia):** Al menos un sitio web está caído o reporta un código de error HTTP superior a 400.
    *   ⚫ **Gris (Idle):** El monitoreo global está en pausa o no hay sitios configurados.
*   **Doble Tipo de Monitoreo:**
    *   🌐 **Monitoreo HTTP / HTTPS:** Peticiones web nativas para validar que tu servidor web devuelva códigos exitosos (2xx/3xx). Los errores del lado del servidor (>= 400) se catalogan como advertencias visibles.
    *   ⚡ **Monitoreo Ping / ICMP:** Envío nativo de paquetes ICMP para verificar la conectividad de hosts e IPs de red con cálculo preciso de latencia en milisegundos.
*   **Notificaciones Nativas:** Alertas de escritorio flotantes e inmediatas al instante en que un monitor se cae o cuando se recupera con éxito, mostrando el tiempo de respuesta o el error reportado.
*   **Interfaz de Usuario Premium (Glassmorphism):** Un panel moderno con fondos translúcidos, efectos de luces dinámicas, gradientes armónicos y soporte completo para estados interactivos y adaptabilidad.
*   **Gráficos en Tiempo Real:** Mini-gráficas vectoriales (SVG) reactivas dentro de cada tarjeta de monitor, mostrando el historial de latencia y estado de los últimos 20 chequeos en tiempo real.
*   **Intervalos Flexibles:** Configura la frecuencia de comprobación de forma global o define intervalos personalizados en segundos de forma individual por sitio.
*   **Auto-inicio con el Sistema (Autostart):** Registro seguro en Linux para iniciar la aplicación minimizada automáticamente en segundo plano cuando inicies sesión en tu sistema operativo.
*   **Almacenamiento Local:** Configuración guardada en texto plano bajo un estándar seguro en `~/.config/montray/sites.json`.

---

## 🛠️ Requisitos Previos

*   **Node.js** (v18.0.0 o superior recomendado)
*   **npm** (incluido con Node.js)
*   **Sistema Operativo:** Optimizado principalmente para Linux, aunque compatible con cualquier entorno que soporte Electron.

---

## 🚀 Instalación y Uso

Sigue estos sencillos pasos para clonar el repositorio, instalar las dependencias y ejecutar MonTray en modo de desarrollo:

### 1. Clonar el repositorio
```bash
git clone https://github.com/jcmt2k/montray.git
cd montray
```

### 2. Instalar dependencias
```bash
npm install
```

### 3. Iniciar la aplicación
```bash
npm start
```

---

## 📦 Empaquetado y Distribución

MonTray está configurado con `electron-builder` para compilarse como binarios independientes listos para producción.

Para generar los paquetes autoinstalables oficiales de Linux (**AppImage** y **DEB**):

```bash
npm run dist
```

Los instaladores resultantes se generarán en el directorio `dist/`:
*   `dist/MonTray-1.0.0.AppImage` (Ejecutable portable)
*   `dist/montray_1.0.0_amd64.deb` (Paquete instalable para Debian/Ubuntu)

---

## 🔒 Seguridad Integrada

El monitoreo mediante Ping / ICMP ejecuta comandos de consola a nivel de sistema. MonTray implementa filtros estrictos de saneamiento para evitar ataques de **inyección de comandos (Command Injection)**. Cualquier hostname o IP ingresado es limpiado rigurosamente mediante expresiones regulares para permitir únicamente caracteres alfanuméricos, puntos, guiones y puertos.

---

## 📁 Estructura del Proyecto

*   `main.js`: Proceso principal de Electron. Controla el ciclo de vida del software, el programador de tareas en segundo plano, la bandeja del sistema, el sistema de notificaciones nativas y la persistencia de configuración en disco.
*   `preload.js`: Puente de comunicación seguro (IPC) con `contextIsolation` activado para permitir que la interfaz gráfica interactúe con el sistema operativo de forma controlada y segura.
*   `assets/`: Contiene los iconos de la aplicación y los iconos dinámicos para los estados de la bandeja del sistema.
*   `src/index.html`: Estructura semántica HTML5 del dashboard principal utilizando componentes modernos y diálogos nativos `<dialog>`.
*   `src/renderer.js`: Lógica del cliente. Gestiona la reactividad del DOM, eventos de usuario, renderizado de gráficas SVG, validaciones de formularios y actualización en tiempo real desde el proceso principal.
*   `src/styles.css`: Estilos visuales personalizados. Define el diseño premium (*Glassmorphic*), tipografías modernas, transiciones y animaciones.

---

## ✒️ Autor y Licencia

Desarrollado con dedicación por **Julio Mejía** ([jcmt2k@gmail.com](mailto:jcmt2k@gmail.com)).

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para obtener más detalles.
