// Elementos DOM principales
const monitorsGrid = document.getElementById('monitorsGrid');
const emptyState = document.getElementById('emptyState');
const globalStatusSummary = document.getElementById('globalStatusSummary');
const configPathText = document.getElementById('configPathText');

// Botones de cabecera
const btnCheckAll = document.getElementById('btnCheckAll');
const btnSettings = document.getElementById('btnSettings');
const btnAddSite = document.getElementById('btnAddSite');
const btnEmptyAdd = document.getElementById('btnEmptyAdd');

// Diálogo Agregar / Editar Sitio
const siteDialog = document.getElementById('siteDialog');
const siteForm = document.getElementById('siteForm');
const siteIdInput = document.getElementById('siteId');
const siteNameInput = document.getElementById('siteName');
const siteTypeSelect = document.getElementById('siteType');
const siteAddressInput = document.getElementById('siteAddress');
const siteIntervalInput = document.getElementById('siteInterval');
const labelAddress = document.getElementById('labelAddress');
const siteAddressHint = document.getElementById('siteAddressHint');
const btnDialogClose = document.getElementById('btnDialogClose');
const btnCancelDialog = document.getElementById('btnCancelDialog');
const dialogTitle = document.getElementById('dialogTitle');

// Diálogo Ajustes Globales
const settingsDialog = document.getElementById('settingsDialog');
const settingsForm = document.getElementById('settingsForm');
const globalIntervalInput = document.getElementById('globalInterval');
const notificationsEnabledCheckbox = document.getElementById('notificationsEnabled');
const startMinimizedCheckbox = document.getElementById('startMinimized');
const autostartEnabledCheckbox = document.getElementById('autostartEnabled');
const btnSettingsClose = document.getElementById('btnSettingsClose');
const btnCancelSettings = document.getElementById('btnCancelSettings');

// Inicialización de la aplicación
document.addEventListener('DOMContentLoaded', async () => {
  // Ajustar la ruta en el footer
  if (configPathText) {
    configPathText.textContent = '~/.config/monitray';
  }

  // Cargar datos iniciales
  await refreshSitesList();
  
  // Escuchar actualizaciones dinámicas del Main Process
  window.api.onSitesUpdated((sites) => {
    updateUI(sites);
  });
});

// --- Lógica de Visualización de Sitios ---

async function refreshSitesList() {
  try {
    const sites = await window.api.getSites();
    updateUI(sites);
  } catch (error) {
    console.error('Error al obtener los sitios:', error);
  }
}

function updateUI(sites) {
  if (!sites || sites.length === 0) {
    monitorsGrid.style.display = 'none';
    emptyState.style.display = 'flex';
    globalStatusSummary.textContent = 'Sin sitios configurados';
    return;
  }

  emptyState.style.display = 'none';
  monitorsGrid.style.display = 'grid';

  // Limpiar rejilla
  monitorsGrid.innerHTML = '';

  let onlineCount = 0;
  let offlineCount = 0;
  let disabledCount = 0;

  sites.forEach(site => {
    if (!site.enabled) {
      disabledCount++;
    } else if (site.status === 'offline') {
      offlineCount++;
    } else {
      onlineCount++;
    }

    const card = createMonitorCard(site);
    monitorsGrid.appendChild(card);
  });

  // Actualizar resumen global en cabecera
  if (offlineCount > 0) {
    globalStatusSummary.innerHTML = `🚨 <span style="color: #fca5a5; font-weight: bold;">${offlineCount} sitio(s) fuera de línea</span> | ${onlineCount} en línea`;
  } else if (onlineCount > 0) {
    globalStatusSummary.innerHTML = `✅ <span style="color: #a7f3d0; font-weight: bold;">Todos los servicios operativos</span> | ${onlineCount} monitores activos`;
  } else {
    globalStatusSummary.textContent = 'Monitores inactivos o pausados';
  }
}

function createMonitorCard(site) {
  const card = document.createElement('div');
  
  // Determinar clases de estado
  const statusClass = `state-${site.status}`;
  card.className = `monitor-card ${statusClass}`;
  card.dataset.id = site.id;

  // Formatear último chequeo
  let timeStr = 'Nunca verificado';
  if (site.lastCheck) {
    timeStr = new Date(site.lastCheck).toLocaleTimeString();
  }

  // Latencia texto
  let latencyText = '---';
  let latencyClass = 'idle';
  if (site.status !== 'offline' && site.status !== 'idle' && site.lastLatency !== null) {
    latencyText = `${site.lastLatency} ms`;
    latencyClass = site.status; // online o warning
  } else if (site.status === 'offline') {
    latencyText = 'Error';
    latencyClass = 'offline';
  }

  // Generar barras de historial (últimos 20)
  const maxHistory = 20;
  const history = site.history || [];
  const paddingLength = Math.max(0, maxHistory - history.length);
  let historyBarsHtml = '';

  // Rellenar con vacíos si no hay suficiente historial
  for (let i = 0; i < paddingLength; i++) {
    historyBarsHtml += '<div class="history-bar-item" data-tooltip="Sin datos"></div>';
  }

  // Añadir datos reales
  history.forEach(item => {
    const itemDate = new Date(item.timestamp).toLocaleString();
    let valClass = 'val-online';
    let statusLabel = 'Online';
    if (!item.online) {
      valClass = 'val-offline';
      statusLabel = 'Offline';
    } else if (item.warning) {
      valClass = 'val-warning';
      statusLabel = 'Advertencia';
    }
    const lat = item.latency !== null ? `${item.latency} ms` : 'Sin respuesta';
    const tooltip = `${itemDate} - ${statusLabel} (${lat})`;
    historyBarsHtml += `<div class="history-bar-item ${valClass}" data-tooltip="${tooltip}"></div>`;
  });

  // Generador de sección de error si aplica
  const errorPanelHtml = (site.status === 'offline' || site.status === 'warning') && site.lastError
    ? `<div class="card-error-area" title="${site.lastError}">${site.lastError}</div>`
    : '';

  card.innerHTML = `
    <div class="card-header">
      <div class="card-title-area">
        <h4 class="card-title" title="${site.name}">${site.name}</h4>
        <span class="card-address" title="${site.address}">${site.address}</span>
      </div>
      <div class="status-badge">
        <span class="dot"></span>
        <span>${site.status}</span>
      </div>
    </div>
    
    <div class="card-details">
      <div>Tipo: <strong>${site.type.toUpperCase()}</strong></div>
      <div>Resp: <span class="latency-value ${latencyClass}">${latencyText}</span></div>
    </div>
    
    <div class="history-timeline">
      <div class="history-label">
        <span>Historial reciente</span>
        <span>Último: ${timeStr}</span>
      </div>
      <div class="history-bars">
        ${historyBarsHtml}
      </div>
    </div>

    ${errorPanelHtml}
    
    <div class="card-actions">
      <label class="switch" title="${site.enabled ? 'Pausar Monitoreo' : 'Iniciar Monitoreo'}">
        <input type="checkbox" class="toggle-enable" ${site.enabled ? 'checked' : ''}>
        <span class="slider"></span>
      </label>
      <div class="actions-buttons">
        <button class="btn-icon check-now" title="Verificar ahora" ${!site.enabled ? 'disabled' : ''}>🔄</button>
        <button class="btn-icon edit" title="Editar sitio">✏️</button>
        <button class="btn-icon delete" title="Eliminar sitio">🗑️</button>
      </div>
    </div>
  `;

  // --- Asignación de Eventos en la Tarjeta ---

  // Interruptor de habilitado/deshabilitado
  const toggle = card.querySelector('.toggle-enable');
  toggle.addEventListener('change', async (e) => {
    const isChecked = e.target.checked;
    await window.api.toggleSite(site.id, isChecked);
  });

  // Botón verificar ahora (individual)
  const btnCheck = card.querySelector('.check-now');
  btnCheck.addEventListener('click', async () => {
    if (window.api.checkSiteNow) {
      await window.api.checkSiteNow(site.id);
    } else {
      // Fallback si no está el IPC individual, forzamos un toggle rápido
      await window.api.toggleSite(site.id, false);
      await window.api.toggleSite(site.id, true);
    }
  });

  // Botón editar
  const btnEdit = card.querySelector('.edit');
  btnEdit.addEventListener('click', () => {
    openSiteDialogForEdit(site);
  });

  // Botón eliminar
  const btnDel = card.querySelector('.delete');
  btnDel.addEventListener('click', async () => {
    if (confirm(`¿Estás seguro de que deseas eliminar el monitor para "${site.name}"?`)) {
      await window.api.deleteSite(site.id);
    }
  });

  return card;
}

// --- Manejo del Diálogo Agregar / Editar Sitio ---

// Función para abrir modales de forma segura asegurando la exclusión mutua
function showModalSafely(dialogToOpen) {
  // Cerrar incondicionalmente ambos diálogos antes de abrir uno nuevo
  try {
    if (siteDialog && typeof siteDialog.close === 'function') {
      siteDialog.close();
    }
  } catch (e) {
    console.error(e);
  }
  
  try {
    if (settingsDialog && typeof settingsDialog.close === 'function') {
      settingsDialog.close();
    }
  } catch (e) {
    console.error(e);
  }

  // Abrir el modal correspondiente
  dialogToOpen.showModal();
}

function openSiteDialogForAdd() {
  dialogTitle.textContent = 'Agregar Sitio';
  siteIdInput.value = '';
  siteForm.reset();
  
  // Restablecer etiquetas por defecto
  updateFormLabels('http');
  
  showModalSafely(siteDialog);
}

function openSiteDialogForEdit(site) {
  dialogTitle.textContent = 'Editar Sitio';
  siteIdInput.value = site.id;
  siteNameInput.value = site.name;
  siteTypeSelect.value = site.type;
  siteAddressInput.value = site.address;
  siteIntervalInput.value = site.interval || '';
  
  updateFormLabels(site.type);
  
  showModalSafely(siteDialog);
}

function updateFormLabels(type) {
  if (type === 'ping') {
    labelAddress.textContent = 'Dirección IP o Hostname';
    siteAddressInput.placeholder = 'Ej: 8.8.8.8, mi-servidor.local';
    siteAddressHint.textContent = 'Ej: 192.168.1.1 o dns.google (sin http:// ni carpetas)';
    // Remover validación regex estricta de URL en dirección IP para admitir hostnames/IPs
    siteAddressInput.type = 'text';
    siteAddressInput.pattern = '^([a-zA-Z0-9.-]+)(:[0-9]+)?$';
  } else {
    labelAddress.textContent = 'Dirección URL';
    siteAddressInput.placeholder = 'Ej: https://miservidor.com';
    siteAddressHint.textContent = 'Ej: https://mi-web.com o http://192.168.1.50:8080/api';
    siteAddressInput.type = 'text';
    // Permitir url completa
    siteAddressInput.pattern = '^(https?:\\/\\/)?[a-zA-Z0-9.-]+(:[0-9]+)?(\\/.*)?$';
  }
}

// Escuchar cambios de tipo de monitoreo para ajustar etiquetas y validación
siteTypeSelect.addEventListener('change', (e) => {
  updateFormLabels(e.target.value);
});

// Eventos para cerrar diálogos
btnDialogClose.addEventListener('click', () => siteDialog.close());
btnCancelDialog.addEventListener('click', () => siteDialog.close());

// Envío del formulario de sitio
siteForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const siteData = {
    name: siteNameInput.value,
    type: siteTypeSelect.value,
    address: siteAddressInput.value,
    interval: siteIntervalInput.value ? parseInt(siteIntervalInput.value) : null
  };

  const id = siteIdInput.value;
  
  try {
    if (id) {
      await window.api.editSite(id, siteData);
    } else {
      await window.api.addSite(siteData);
    }
    siteDialog.close();
  } catch (error) {
    alert('Error al guardar el sitio: ' + error.message);
  }
});

// --- Manejo del Diálogo de Ajustes Globales ---

btnSettings.addEventListener('click', async () => {
  try {
    const settings = await window.api.getSettings();
    
    globalIntervalInput.value = settings.globalInterval || 30;
    notificationsEnabledCheckbox.checked = settings.notificationsEnabled !== false;
    startMinimizedCheckbox.checked = settings.startMinimized === true;
    autostartEnabledCheckbox.checked = settings.autostart === true;
    
    showModalSafely(settingsDialog);
  } catch (error) {
    console.error('Error al cargar ajustes:', error);
  }
});

btnSettingsClose.addEventListener('click', () => settingsDialog.close());
btnCancelSettings.addEventListener('click', () => settingsDialog.close());

settingsForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const settingsData = {
    globalInterval: parseInt(globalIntervalInput.value) || 30,
    notificationsEnabled: notificationsEnabledCheckbox.checked,
    startMinimized: startMinimizedCheckbox.checked,
    autostart: autostartEnabledCheckbox.checked
  };

  try {
    await window.api.saveSettings(settingsData);
    settingsDialog.close();
  } catch (error) {
    alert('Error al guardar la configuración: ' + error.message);
  }
});

// --- Acciones de Cabecera y Atajos ---

btnAddSite.addEventListener('click', openSiteDialogForAdd);
btnEmptyAdd.addEventListener('click', openSiteDialogForAdd);

btnCheckAll.addEventListener('click', async () => {
  btnCheckAll.disabled = true;
  const originalText = btnCheckAll.innerHTML;
  btnCheckAll.innerHTML = '<span class="icon">⏳</span> Verificando...';
  
  try {
    await window.api.checkAllNow();
  } catch (error) {
    console.error('Error al verificar todo:', error);
  } finally {
    // Restaurar botón tras un retraso corto visual
    setTimeout(() => {
      btnCheckAll.disabled = false;
      btnCheckAll.innerHTML = originalText;
    }, 1000);
  }
});
