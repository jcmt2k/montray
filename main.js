const { app, Tray, Menu, BrowserWindow, ipcMain, Notification, nativeImage, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');

let tray = null;
let mainWindow = null;
let isMonitoringActive = true;
const siteTimers = {};

// Ruta de almacenamiento de configuración en ~/.config/montray/
const userDataPath = app.getPath('userData');
if (!fs.existsSync(userDataPath)) {
  fs.mkdirSync(userDataPath, { recursive: true });
}
const configPath = path.join(userDataPath, 'sites.json');

// Configuración por defecto
const DEFAULT_CONFIG = {
  settings: {
    globalInterval: 30, // segundos
    notificationsEnabled: true,
    startMinimized: false,
    autostart: false
  },
  sites: []
};

let config = { ...DEFAULT_CONFIG };

// Cargar configuración de disco
function loadConfig() {
  try {
    if (fs.existsSync(configPath)) {
      const data = fs.readFileSync(configPath, 'utf8');
      const loaded = JSON.parse(data);
      config = {
        settings: { ...DEFAULT_CONFIG.settings, ...loaded.settings },
        sites: loaded.sites || []
      };
    } else {
      config = { ...DEFAULT_CONFIG };
      saveConfig();
    }
  } catch (error) {
    console.error('Error al cargar la configuración:', error);
    config = { ...DEFAULT_CONFIG };
  }
}

// Guardar configuración a disco
function saveConfig() {
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
  } catch (error) {
    console.error('Error al guardar la configuración:', error);
  }
}

// Enviar estado de sitios a la interfaz
function broadcastSites() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('sites-updated', config.sites);
  }
}

// --- Métodos de Monitoreo ---

// Realizar un Ping ICMP ejecutando el comando ping del sistema
function pingIP(ip, timeoutMs = 5000) {
  return new Promise((resolve) => {
    // En Linux, -c 1 envía un paquete, -W define el tiempo límite en segundos
    const timeoutSec = Math.max(1, Math.round(timeoutMs / 1000));
    const start = Date.now();
    
    // Evitar inyección de comandos saneando la IP/hostname
    // Permitir letras, números, guiones, puntos y puertos simples
    const cleanIp = ip.replace(/[^a-zA-Z0-9.-]/g, '');
    
    exec(`ping -c 1 -W ${timeoutSec} "${cleanIp}"`, (error, stdout, stderr) => {
      const latency = Date.now() - start;
      if (error) {
        let msg = 'Offline';
        if (stdout.includes('100% packet loss') || stderr.includes('unreachable') || error.code === 1) {
          msg = 'Inalcanzable (100% packet loss)';
        } else if (error.message) {
          msg = `Error de ping (${error.code})`;
        }
        resolve({ online: false, latency: null, error: msg });
      } else {
        const match = stdout.match(/time=([\d.]+)\s*ms/);
        const parsedLatency = match ? parseFloat(match[1]) : latency;
        resolve({ online: true, latency: Math.round(parsedLatency), error: null });
      }
    });
  });
}

// Realizar una petición HTTP/HTTPS utilizando fetch nativo de Node.js
async function checkHTTP(url, timeoutMs = 5000) {
  // Autocompletar http:// si no tiene esquema
  let targetUrl = url.trim();
  if (!/^https?:\/\//i.test(targetUrl)) {
    targetUrl = 'http://' + targetUrl;
  }

  try {
    new URL(targetUrl);
  } catch (e) {
    return { online: false, latency: null, error: 'URL malformada (Ej: https://google.com)' };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const start = Date.now();
  
  try {
    const response = await fetch(targetUrl, {
      signal: controller.signal,
      method: 'GET',
      headers: {
        'User-Agent': 'MonTray/1.0',
        'Cache-Control': 'no-cache'
      }
    });
    
    const latency = Date.now() - start;
    
    if (response.status >= 400) {
      return {
        online: true,
        latency: Math.round(latency),
        error: `Estado HTTP ${response.status} ${response.statusText}`,
        warning: true
      };
    }
    
    return { online: true, latency: Math.round(latency), error: null, warning: false };
  } catch (error) {
    let errMsg = 'Offline';
    if (error.name === 'AbortError') {
      errMsg = 'Límite de tiempo excedido (Timeout)';
    } else if (error.code === 'ENOTFOUND' || error.message.includes('getaddrinfo')) {
      errMsg = 'Servidor no encontrado (DNS error)';
    } else {
      errMsg = error.message || 'Error de conexión';
    }
    return { online: false, latency: null, error: errMsg };
  } finally {
    clearTimeout(timeoutId);
  }
}

// Ejecutar el chequeo individual de un sitio
async function checkSite(site) {
  if (!site.enabled || !isMonitoringActive) return;
  
  // Actualizar estado a 'checking' temporalmente
  const index = config.sites.findIndex(s => s.id === site.id);
  if (index !== -1) {
    config.sites[index].status = 'checking';
    broadcastSites();
  }
  
  let result;
  if (site.type === 'ping') {
    result = await pingIP(site.address);
  } else {
    result = await checkHTTP(site.address);
  }
  
  // Recargar índice por si cambió la lista durante el async check
  const idx = config.sites.findIndex(s => s.id === site.id);
  if (idx === -1) return;
  
  const currentSite = config.sites[idx];
  const previousStatus = currentSite.status === 'checking' ? currentSite.lastStatus || 'idle' : currentSite.status;
  const newStatus = result.online ? (result.warning ? 'warning' : 'online') : 'offline';
  
  currentSite.status = newStatus;
  currentSite.lastStatus = newStatus; // Guardar estado real
  currentSite.lastCheck = new Date().toISOString();
  currentSite.lastLatency = result.latency;
  currentSite.lastError = result.error;
  
  // Guardar historial corto para gráficas (últimos 20 chequeos)
  if (!currentSite.history) currentSite.history = [];
  currentSite.history.push({
    timestamp: currentSite.lastCheck,
    online: result.online,
    warning: result.warning || false,
    latency: result.latency
  });
  if (currentSite.history.length > 20) {
    currentSite.history.shift();
  }
  
  saveConfig();
  broadcastSites();
  updateTrayIcon();
  triggerNotificationIfNeeded(currentSite, previousStatus, newStatus);
}

// Enviar notificación si cambia de estado
function triggerNotificationIfNeeded(site, prevStatus, newStatus) {
  if (!config.settings.notificationsEnabled) return;
  if (!prevStatus || prevStatus === 'idle' || prevStatus === 'checking') return;
  
  if (prevStatus !== 'offline' && newStatus === 'offline') {
    new Notification({
      title: `🚨 Sitio Caído: ${site.name}`,
      body: `${site.address} no responde. Detalle: ${site.lastError || 'Sin respuesta'}`,
      icon: path.join(__dirname, 'assets', 'app-icon.png')
    }).show();
  } else if (prevStatus === 'offline' && newStatus !== 'offline') {
    const latencyMsg = site.lastLatency ? ` (${site.lastLatency} ms)` : '';
    new Notification({
      title: `✅ Sitio Recuperado: ${site.name}`,
      body: `${site.address} vuelve a estar en línea${latencyMsg}.`,
      icon: path.join(__dirname, 'assets', 'app-icon.png')
    }).show();
  }
}

// --- Planificación de Tareas (Scheduler) ---

function startSiteMonitoring(site) {
  stopSiteMonitoring(site.id);
  if (!site.enabled || !isMonitoringActive) return;
  
  const intervalSeconds = site.interval || config.settings.globalInterval || 30;
  
  // Primer chequeo inmediato
  checkSite(site);
  
  // Programar bucle
  siteTimers[site.id] = setInterval(() => {
    checkSite(site);
  }, intervalSeconds * 1000);
}

function stopSiteMonitoring(siteId) {
  if (siteTimers[siteId]) {
    clearInterval(siteTimers[siteId]);
    delete siteTimers[siteId];
  }
}

function startAllMonitoring() {
  config.sites.forEach(site => {
    startSiteMonitoring(site);
  });
}

function stopAllMonitoring() {
  Object.keys(siteTimers).forEach(id => {
    stopSiteMonitoring(id);
  });
}

// --- Inicio Automático (Linux Autostart) ---

function updateAutostart(enabled) {
  const autostartDir = path.join(app.getPath('home'), '.config', 'autostart');
  const autostartFile = path.join(autostartDir, 'montray.desktop');
  
  try {
    if (enabled) {
      if (!fs.existsSync(autostartDir)) {
        fs.mkdirSync(autostartDir, { recursive: true });
      }
      
      const appPath = app.getAppPath();
      const exePath = process.execPath;
      
      const desktopContent = `[Desktop Entry]
Type=Application
Version=1.0
Name=MonTray
Comment=Monitoreo de servidores en system tray
Exec="${exePath}" "${appPath}" --hidden
StartupNotify=false
Terminal=false
Icon=${path.join(appPath, 'assets', 'app-icon.png')}
Categories=Network;Utility;
`;
      fs.writeFileSync(autostartFile, desktopContent, 'utf-8');
      fs.chmodSync(autostartFile, 0o755);
    } else {
      if (fs.existsSync(autostartFile)) {
        fs.unlinkSync(autostartFile);
      }
    }
  } catch (error) {
    console.error('Error al configurar inicio automático:', error);
  }
}

// --- Ventana e Icono de Bandeja ---

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 920,
    height: 650,
    minWidth: 700,
    minHeight: 500,
    title: 'MonTray - Panel de Monitoreo',
    icon: path.join(__dirname, 'assets', 'app-icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    show: false // Se muestra según parámetros
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  // Evitar cierre completo, ocultar a la bandeja en su lugar
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
    return false;
  });
}

function showWindow() {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
}

function toggleWindow() {
  if (!mainWindow) return;
  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    showWindow();
  }
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'assets', 'icon-idle.png'));
  
  const buildMenu = () => {
    return Menu.buildFromTemplate([
      { 
        label: 'Abrir MonTray', 
        font: { weight: 'bold' },
        click: () => showWindow() 
      },
      { 
        label: 'Verificar todo ahora', 
        click: () => {
          config.sites.filter(s => s.enabled).forEach(s => checkSite(s));
        } 
      },
      { type: 'separator' },
      { 
        label: 'Monitoreo Activo', 
        type: 'checkbox', 
        checked: isMonitoringActive, 
        click: (item) => {
          isMonitoringActive = item.checked;
          if (isMonitoringActive) {
            startAllMonitoring();
          } else {
            stopAllMonitoring();
            // Actualizar estados locales de sitios a 'idle'
            config.sites.forEach(s => {
              if (s.enabled) s.status = 'idle';
            });
            broadcastSites();
          }
          updateTrayIcon();
        } 
      },
      { type: 'separator' },
      { 
        label: 'Salir', 
        click: () => {
          app.isQuitting = true;
          stopAllMonitoring();
          app.quit();
        } 
      }
    ]);
  };

  tray.setToolTip('MonTray - Monitoreo de Red');
  tray.setContextMenu(buildMenu());
  
  // Al hacer clic primario
  tray.on('click', () => {
    toggleWindow();
  });
}

function updateTrayIcon() {
  if (!tray) return;
  
  if (!isMonitoringActive) {
    tray.setImage(path.join(__dirname, 'assets', 'icon-idle.png'));
    tray.setToolTip('MonTray - Monitoreo desactivado');
    return;
  }
  
  const activeSites = config.sites.filter(s => s.enabled);
  if (activeSites.length === 0) {
    tray.setImage(path.join(__dirname, 'assets', 'icon-idle.png'));
    tray.setToolTip('MonTray - Sin sitios configurados');
    return;
  }
  
  const offlineSites = activeSites.filter(s => s.status === 'offline');
  const warningSites = activeSites.filter(s => s.status === 'warning');
  const totalCount = activeSites.length;
  
  if (offlineSites.length > 0) {
    tray.setImage(path.join(__dirname, 'assets', 'icon-offline.png'));
    tray.setToolTip(`MonTray - ${offlineSites.length} caído(s) de ${totalCount}`);
  } else if (warningSites.length > 0) {
    // Si hay advertencias de estado (ej: 404), podemos usar offline o un tono intermedio
    // Usamos el icono offline para alertar al usuario que hay anomalías
    tray.setImage(path.join(__dirname, 'assets', 'icon-offline.png'));
    tray.setToolTip(`MonTray - ${warningSites.length} advertencia(s) de ${totalCount}`);
  } else {
    tray.setImage(path.join(__dirname, 'assets', 'icon-online.png'));
    tray.setToolTip(`MonTray - Todos online (${totalCount}/${totalCount})`);
  }
}

// --- Controladores de Eventos IPC ---

ipcMain.handle('get-sites', () => config.sites);
ipcMain.handle('get-settings', () => config.settings);

ipcMain.handle('add-site', (event, newSite) => {
  const id = Date.now().toString(36) + Math.random().toString(36).substring(2, 7);
  const site = {
    id,
    name: newSite.name.trim(),
    type: newSite.type,
    address: newSite.address.trim(),
    interval: parseInt(newSite.interval) || null,
    enabled: true,
    status: 'idle',
    lastCheck: null,
    lastLatency: null,
    lastError: null,
    history: []
  };
  
  config.sites.push(site);
  saveConfig();
  startSiteMonitoring(site);
  broadcastSites();
  updateTrayIcon();
  return { success: true, site };
});

ipcMain.handle('edit-site', (event, id, updatedData) => {
  const idx = config.sites.findIndex(s => s.id === id);
  if (idx !== -1) {
    const oldEnabled = config.sites[idx].enabled;
    const oldAddress = config.sites[idx].address;
    const oldType = config.sites[idx].type;
    const oldInterval = config.sites[idx].interval;
    
    config.sites[idx] = {
      ...config.sites[idx],
      name: updatedData.name.trim(),
      type: updatedData.type,
      address: updatedData.address.trim(),
      interval: parseInt(updatedData.interval) || null,
    };
    
    saveConfig();
    
    // Si cambió configuración crítica, reiniciar monitores
    if (
      oldEnabled !== config.sites[idx].enabled ||
      oldAddress !== config.sites[idx].address ||
      oldType !== config.sites[idx].type ||
      oldInterval !== config.sites[idx].interval
    ) {
      if (config.sites[idx].enabled) {
        startSiteMonitoring(config.sites[idx]);
      } else {
        stopSiteMonitoring(id);
        config.sites[idx].status = 'idle';
      }
    }
    
    broadcastSites();
    updateTrayIcon();
    return { success: true, site: config.sites[idx] };
  }
  return { success: false, error: 'Sitio no encontrado' };
});

ipcMain.handle('delete-site', (event, id) => {
  const idx = config.sites.findIndex(s => s.id === id);
  if (idx !== -1) {
    stopSiteMonitoring(id);
    config.sites.splice(idx, 1);
    saveConfig();
    broadcastSites();
    updateTrayIcon();
    return { success: true };
  }
  return { success: false, error: 'Sitio no encontrado' };
});

ipcMain.handle('toggle-site', (event, id, enabled) => {
  const idx = config.sites.findIndex(s => s.id === id);
  if (idx !== -1) {
    config.sites[idx].enabled = enabled;
    saveConfig();
    if (enabled) {
      startSiteMonitoring(config.sites[idx]);
    } else {
      stopSiteMonitoring(id);
      config.sites[idx].status = 'idle';
      config.sites[idx].lastLatency = null;
      config.sites[idx].lastError = null;
    }
    broadcastSites();
    updateTrayIcon();
    return { success: true, site: config.sites[idx] };
  }
  return { success: false, error: 'Sitio no encontrado' };
});

ipcMain.handle('check-all-now', () => {
  config.sites.filter(s => s.enabled).forEach(s => checkSite(s));
  return { success: true };
});

ipcMain.handle('check-site-now', (event, id) => {
  const site = config.sites.find(s => s.id === id);
  if (site && site.enabled) {
    checkSite(site);
    return { success: true };
  }
  return { success: false, error: 'Sitio no encontrado o desactivado' };
});

ipcMain.handle('save-settings', (event, settings) => {
  const oldInterval = config.settings.globalInterval;
  const oldAutostart = config.settings.autostart;
  
  config.settings = { ...config.settings, ...settings };
  saveConfig();
  
  // Habilitar / deshabilitar autostart
  if (oldAutostart !== config.settings.autostart) {
    updateAutostart(config.settings.autostart);
  }
  
  // Si cambió el intervalo global, reiniciar planificadores por defecto
  if (oldInterval !== config.settings.globalInterval) {
    config.sites.forEach(site => {
      if (!site.interval && site.enabled) {
        startSiteMonitoring(site);
      }
    });
  }
  
  return { success: true, settings: config.settings };
});

// --- Ciclo de Vida del App ---

app.whenReady().then(() => {
  loadConfig();
  createTray();
  createWindow();
  
  // Comprobar si arranca oculto
  const startHidden = process.argv.includes('--hidden') || config.settings.startMinimized;
  if (!startHidden) {
    showWindow();
  }
  
  // Iniciar monitoreo
  startAllMonitoring();
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else {
      showWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // No salimos de la app cuando se cierran las ventanas, nos mantenemos en el tray
  if (process.platform !== 'darwin') {
    // En macOS es normal que las apps se mantengan activas
  }
});
