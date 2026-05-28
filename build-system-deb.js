const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PROJECT_DIR = __dirname;
const DIST_DIR = path.join(PROJECT_DIR, 'dist');
const TMP_DEB_DIR = path.join(DIST_DIR, 'tmp-system-deb');
const TMP_SRC_DIR = path.join(DIST_DIR, 'tmp-src');

console.log('🚀 Iniciando la creación del paquete debian montray-system...');

// 1. Asegurar limpieza de directorios de compilación
function cleanDir(dirPath) {
  if (fs.existsSync(dirPath)) {
    fs.rmSync(dirPath, { recursive: true, force: true });
  }
}

cleanDir(TMP_DEB_DIR);
cleanDir(TMP_SRC_DIR);

fs.mkdirSync(TMP_DEB_DIR, { recursive: true });
fs.mkdirSync(TMP_SRC_DIR, { recursive: true });

// 2. Copiar archivos fuente del proyecto a tmp-src
console.log('📦 Copiando archivos del código fuente...');
const filesToCopy = ['main.js', 'preload.js', 'package.json'];
filesToCopy.forEach(file => {
  fs.copyFileSync(path.join(PROJECT_DIR, file), path.join(TMP_SRC_DIR, file));
});

function copyFolderSync(from, to) {
  if (!fs.existsSync(to)) {
    fs.mkdirSync(to, { recursive: true });
  }
  fs.readdirSync(from).forEach(element => {
    const stat = fs.lstatSync(path.join(from, element));
    if (stat.isFile()) {
      fs.copyFileSync(path.join(from, element), path.join(to, element));
    } else if (stat.isDirectory()) {
      copyFolderSync(path.join(from, element), path.join(to, element));
    }
  });
}

copyFolderSync(path.join(PROJECT_DIR, 'src'), path.join(TMP_SRC_DIR, 'src'));
copyFolderSync(path.join(PROJECT_DIR, 'assets'), path.join(TMP_SRC_DIR, 'assets'));

// 3. Crear estructura de directorios Debian
console.log('📁 Creando estructura de directorios del paquete...');
const paths = {
  debian: path.join(TMP_DEB_DIR, 'DEBIAN'),
  bin: path.join(TMP_DEB_DIR, 'usr', 'bin'),
  shareApp: path.join(TMP_DEB_DIR, 'usr', 'share', 'montray'),
  desktop: path.join(TMP_DEB_DIR, 'usr', 'share', 'applications'),
  pixmaps: path.join(TMP_DEB_DIR, 'usr', 'share', 'pixmaps')
};

Object.values(paths).forEach(p => fs.mkdirSync(p, { recursive: true }));

// 4. Empaquetar app.asar usando asar
console.log('⚡ Empaquetando app.asar...');
const asarOutFile = path.join(paths.shareApp, 'app.asar');
try {
  execSync(`npx asar pack "${TMP_SRC_DIR}" "${asarOutFile}"`, { stdio: 'inherit' });
} catch (error) {
  console.error('❌ Error al empaquetar con asar:', error);
  process.exit(1);
}

// 5. Escribir script wrapper executable (/usr/bin/montray)
console.log('✍️ Creando script de inicio en /usr/bin/montray...');
const wrapperScript = `#!/bin/bash
# Script de inicio para MonTray usando el Electron del sistema
set -e

if command -v electron >/dev/null 2>&1; then
  exec electron /usr/share/montray/app.asar "$@"
elif command -v electron30 >/dev/null 2>&1; then
  exec electron30 /usr/share/montray/app.asar "$@"
else
  # Buscar cualquier binario de electron en /usr/bin
  ELECTRON_BIN=$(find /usr/bin -name "electron*" | head -n 1)
  if [ -n "$ELECTRON_BIN" ]; then
    exec "$ELECTRON_BIN" /usr/share/montray/app.asar "$@"
  else
    echo "❌ Error: No se encontró ningún binario 'electron' instalado en el sistema." >&2
    echo "Por favor, instala Electron mediante tu gestor de paquetes habitual." >&2
    echo "Ejemplo en Debian/Ubuntu: sudo apt install electron" >&2
    exit 1
  fi
fi
`;

const wrapperPath = path.join(paths.bin, 'montray');
fs.writeFileSync(wrapperPath, wrapperScript, { encoding: 'utf8', mode: 0o755 });

// 6. Escribir archivo de configuración control (DEBIAN/control)
console.log('✍️ Escribiendo archivo DEBIAN/control...');
const controlContent = `Package: montray-system
Version: 1.0.0
Section: utils
Priority: optional
Architecture: all
Depends: electron (>= 28.0.0) | electron
Maintainer: Julio Mejia <jcmt2k@gmail.com>
Description: Monitoreo liviano de servidores usando el Electron de sistema
 MonTray es una aplicación liviana en bandeja de sistema para el monitoreo
 de servidores, URLs e IPs. Esta versión ultra-compacta no incluye el runtime
 de Electron integrado, sino que depende de que esté instalado en el sistema,
 reduciendo el instalador a apenas 1.2 MB.
`;
fs.writeFileSync(path.join(paths.debian, 'control'), controlContent, 'utf8');

// 7. Escribir acceso directo .desktop
console.log('✍️ Creando entrada de escritorio .desktop...');
const desktopContent = `[Desktop Entry]
Name=MonTray (System)
Comment=Monitoreo de servidores en bandeja de sistema
Exec=/usr/bin/montray --hidden
Icon=montray
Terminal=false
Type=Application
Categories=Network;Utility;
StartupNotify=false
`;
fs.writeFileSync(path.join(paths.desktop, 'montray.desktop'), desktopContent, 'utf8');

// 8. Copiar icono de la aplicación
console.log('🖼️ Copiando icono de la app a pixmaps...');
fs.copyFileSync(
  path.join(PROJECT_DIR, 'assets', 'app-icon.png'),
  path.join(paths.pixmaps, 'montray.png')
);

// 9. Construir el paquete .deb usando dpkg-deb
console.log('🛠️ Compilando paquete .deb con dpkg-deb...');
const debOutFile = path.join(DIST_DIR, 'montray-system_1.0.0_all.deb');
try {
  execSync(`dpkg-deb --root-owner-group --build "${TMP_DEB_DIR}" "${debOutFile}"`, { stdio: 'inherit' });
  console.log(`\n✅ ¡Paquete .deb del sistema creado con éxito!`);
  console.log(`📦 Ubicación: ${debOutFile}`);
  const stats = fs.statSync(debOutFile);
  console.log(`⚖️ Peso del instalador: ${(stats.size / 1024 / 1024).toFixed(2)} MB (${stats.size.toLocaleString()} bytes)`);
} catch (error) {
  console.error('❌ Error al construir el paquete .deb con dpkg-deb:', error);
  process.exit(1);
} finally {
  // Limpieza de directorios temporales
  console.log('🧹 Limpiando archivos temporales...');
  cleanDir(TMP_DEB_DIR);
  cleanDir(TMP_SRC_DIR);
  console.log('✨ Proceso completado.');
}
