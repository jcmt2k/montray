// tauri-adapter.js
// Adaptador de compatibilidad para exponer window.api en el entorno de Tauri
(function () {
  const isTauri = typeof window.__TAURI__ !== 'undefined';
  
  if (isTauri && typeof window.api === 'undefined') {
    const { invoke } = window.__TAURI__.tauri;
    const { listen } = window.__TAURI__.event;
    
    console.log('⚡ Entorno Tauri detectado. Inicializando puente de compatibilidad window.api...');
    
    window.api = {
      // Solicitar datos iniciales
      getSites: () => invoke('get_sites'),
      getSettings: () => invoke('get_settings'),
      
      // Operaciones de gestión de monitores
      addSite: (site) => invoke('add_site', { site }),
      editSite: (id, site) => invoke('edit_site', { id, site }),
      deleteSite: (id) => invoke('delete_site', { id }),
      toggleSite: (id, enabled) => invoke('toggle_site', { id, enabled }),
      checkAllNow: () => invoke('check_all_now'),
      checkSiteNow: (id) => invoke('check_site_now', { id }),
      
      // Guardar configuración global
      saveSettings: (settings) => invoke('save_settings', { settings }),
      
      // Suscripción a eventos enviados desde el Main Process
      onSitesUpdated: (callback) => {
        let unlistenFn = null;
        listen('sites-updated', (event) => {
          callback(event.payload);
        }).then(unlisten => {
          unlistenFn = unlisten;
        });
        return () => {
          if (unlistenFn) unlistenFn();
        };
      },
      onStatusUpdated: (callback) => {
        let unlistenFn = null;
        listen('status-updated', (event) => {
          callback(event.payload);
        }).then(unlisten => {
          unlistenFn = unlisten;
        });
        return () => {
          if (unlistenFn) unlistenFn();
        };
      }
    };
  }
})();
