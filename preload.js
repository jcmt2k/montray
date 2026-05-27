const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // Solicitar datos iniciales
  getSites: () => ipcRenderer.invoke('get-sites'),
  getSettings: () => ipcRenderer.invoke('get-settings'),
  
  // Operaciones de gestión de monitores
  addSite: (site) => ipcRenderer.invoke('add-site', site),
  editSite: (id, site) => ipcRenderer.invoke('edit-site', id, site),
  deleteSite: (id) => ipcRenderer.invoke('delete-site', id),
  toggleSite: (id, enabled) => ipcRenderer.invoke('toggle-site', id, enabled),
  checkAllNow: () => ipcRenderer.invoke('check-all-now'),
  checkSiteNow: (id) => ipcRenderer.invoke('check-site-now', id),
  
  // Guardar configuración global
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
  
  // Suscripción a eventos enviados desde el Main Process
  onSitesUpdated: (callback) => {
    const subscription = (event, data) => callback(data);
    ipcRenderer.on('sites-updated', subscription);
    return () => ipcRenderer.removeListener('sites-updated', subscription);
  },
  onStatusUpdated: (callback) => {
    const subscription = (event, data) => callback(data);
    ipcRenderer.on('status-updated', subscription);
    return () => ipcRenderer.removeListener('status-updated', subscription);
  }
});
