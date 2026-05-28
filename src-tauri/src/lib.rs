use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use std::path::PathBuf;
use std::fs;
use serde::{Serialize, Deserialize};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use chrono::Local;

// --- ESTRUCTURAS DE DATOS (Emparejadas exactamente con Electron) ---

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SiteHistory {
    pub timestamp: String,
    pub online: bool,
    pub warning: bool,
    pub latency: Option<u32>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Site {
    pub id: String,
    pub name: String,
    #[serde(rename = "type")]
    pub site_type: String,
    pub address: String,
    pub interval: Option<u32>,
    pub enabled: bool,
    pub status: String,
    #[serde(rename = "lastStatus")]
    pub last_status: Option<String>,
    #[serde(rename = "lastCheck")]
    pub last_check: Option<String>,
    #[serde(rename = "lastLatency")]
    pub last_latency: Option<u32>,
    #[serde(rename = "lastError")]
    pub last_error: Option<String>,
    #[serde(default)]
    pub history: Vec<SiteHistory>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Settings {
    #[serde(rename = "globalInterval")]
    pub global_interval: u32,
    #[serde(rename = "notificationsEnabled")]
    pub notifications_enabled: bool,
    #[serde(rename = "startMinimized")]
    pub start_minimized: bool,
    pub autostart: bool,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct AppConfig {
    pub settings: Settings,
    pub sites: Vec<Site>,
}

pub struct AppState {
    pub config: Mutex<AppConfig>,
    pub is_monitoring_active: Mutex<bool>,
    pub site_timers: Mutex<HashMap<String, u32>>,
}

// --- UTILIDADES DE CONFIGURACIÓN Y SISTEMA ---

fn get_config_path() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/home/julio".to_string());
    std::path::Path::new(&home).join(".config").join("montray").join("sites.json")
}

fn load_config() -> AppConfig {
    let path = get_config_path();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(path) {
            if let Ok(config) = serde_json::from_str::<AppConfig>(&content) {
                return config;
            }
        }
    }
    
    // Configuración por defecto
    AppConfig {
        settings: Settings {
            global_interval: 30,
            notifications_enabled: true,
            start_minimized: false,
            autostart: false,
        },
        sites: Vec::new(),
    }
}

fn save_config(config: &AppConfig) {
    let path = get_config_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).ok();
    }
    if let Ok(content) = serde_json::to_string_pretty(config) {
        fs::write(path, content).ok();
    }
}

fn update_autostart(enabled: bool, app: &AppHandle) {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/home/julio".to_string());
    let autostart_dir = std::path::Path::new(&home).join(".config").join("autostart");
    let autostart_file = autostart_dir.join("montray.desktop");
    
    if enabled {
        fs::create_dir_all(&autostart_dir).ok();
        let desktop_content = format!(
            "[Desktop Entry]\n\
             Type=Application\n\
             Version=1.0\n\
             Name=MonTray\n\
             Comment=Monitoreo de servidores en system tray\n\
             Exec=montray-tauri --hidden\n\
             StartupNotify=false\n\
             Terminal=false\n\
             Icon=montray\n\
             Categories=Network;Utility;\n"
        );
        fs::write(autostart_file, desktop_content).ok();
    } else {
        if autostart_file.exists() {
            fs::remove_file(autostart_file).ok();
        }
    }
}

// --- NOTIFICACIONES ---

fn trigger_notification(title: &str, body: &str) {
    std::process::Command::new("notify-send")
        .arg("-i")
        .arg("montray")
        .arg(title)
        .arg(body)
        .spawn()
        .ok();
}

// --- CHEQUEOS DE RED (HTTP & PING) ---

async fn check_http(address: &str, timeout_ms: u64) -> (bool, Option<u32>, Option<String>, bool) {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_millis(timeout_ms))
        .build()
        .unwrap_or_default();
    
    let mut url = address.trim().to_string();
    if !url.to_lowercase().starts_with("http://") && !url.to_lowercase().starts_with("https://") {
        url = format!("http://{}", url);
    }
    
    let start = std::time::Instant::now();
    match client.get(&url).header("User-Agent", "MonTray/1.0").send().await {
        Ok(response) => {
            let latency = start.elapsed().as_millis() as u32;
            let status = response.status();
            if status.is_success() {
                (true, Some(latency), None, false)
            } else {
                (true, Some(latency), Some(format!("Estado HTTP {}", status)), true)
            }
        }
        Err(e) => {
            let err_msg = if e.is_timeout() {
                "Límite de tiempo excedido (Timeout)".to_string()
            } else {
                format!("{}", e)
            };
            (false, None, Some(err_msg), false)
        }
    }
}

fn ping_ip(ip: &str, timeout_ms: u64) -> (bool, Option<u32>, Option<String>) {
    let timeout_sec = std::cmp::max(1, timeout_ms / 1000) as u32;
    let clean_ip: String = ip.chars().filter(|c| c.is_alphanumeric() || *c == '.' || *c == '-').collect();
    
    let start = std::time::Instant::now();
    let output = std::process::Command::new("ping")
        .arg("-c")
        .arg("1")
        .arg("-W")
        .arg(timeout_sec.to_string())
        .arg(&clean_ip)
        .output();
        
    let latency = start.elapsed().as_millis() as u32;
    
    match output {
        Ok(out) => {
            if out.status.success() {
                let stdout_str = String::from_utf8_lossy(&out.stdout);
                if let Some(time_pos) = stdout_str.find("time=") {
                    let sub = &stdout_str[time_pos + 5..];
                    if let Some(space_pos) = sub.find(' ') {
                        if let Ok(lat_parsed) = sub[..space_pos].parse::<f32>() {
                            return (true, Some(lat_parsed.round() as u32), None);
                        }
                    }
                }
                (true, Some(latency), None)
            } else {
                let stderr_str = String::from_utf8_lossy(&out.stderr);
                let stdout_str = String::from_utf8_lossy(&out.stdout);
                let mut msg = "Offline".to_string();
                if stdout_str.contains("100% packet loss") || stderr_str.contains("unreachable") {
                    msg = "Inalcanzable (100% packet loss)".to_string();
                }
                (false, None, Some(msg))
            }
        }
        Err(e) => (false, None, Some(format!("Error de ping: {}", e)))
    }
}

// --- CONTROLADOR DE BANDEJA DE SISTEMA (TRAY ICON) ---

fn update_tray_icon(app_handle: &AppHandle, state: &AppState) {
    let is_active = *state.is_monitoring_active.lock().unwrap();
    let config = state.config.lock().unwrap();
    
    let tray = match app_handle.tray_by_id("main") {
        Some(t) => t,
        None => return,
    };
    
    let icon_name = if !is_active {
        "icon-idle.png"
    } else {
        let active_sites: Vec<&Site> = config.sites.iter().filter(|s| s.enabled).collect();
        if active_sites.is_empty() {
            "icon-idle.png"
        } else {
            let offline_count = active_sites.iter().filter(|s| s.status == "offline").count();
            let warning_count = active_sites.iter().filter(|s| s.status == "warning").count();
            
            if offline_count > 0 || warning_count > 0 {
                "icon-offline.png"
            } else {
                "icon-online.png"
            }
        }
    };
    
    // Buscar recurso
    let icon_path = app_handle.path().resource_dir()
        .unwrap_or_default()
        .join("assets")
        .join(icon_name);
        
    if let Ok(img) = tauri::image::Image::from_path(icon_path) {
        tray.set_icon(Some(img)).ok();
    }
}

// --- PROCESADOR DE CHEQUEOS ---

async fn check_site(site_id: String, app_handle: AppHandle, state: Arc<AppState>) {
    // 1. Establecer en estado 'checking'
    let mut site_name = String::new();
    let mut address = String::new();
    let mut site_type = String::new();
    let mut enabled = false;
    
    {
        let mut config = state.config.lock().unwrap();
        if let Some(site) = config.sites.iter_mut().find(|s| s.id == site_id) {
            if !site.enabled { return; }
            site.status = "checking".to_string();
            site_name = site.name.clone();
            address = site.address.clone();
            site_type = site.site_type.clone();
            enabled = site.enabled;
        }
    }
    
    if !enabled { return; }
    
    // Emitir actualización inicial de checking
    let current_sites = {
        let config = state.config.lock().unwrap();
        config.sites.clone()
    };
    app_handle.emit("sites-updated", &current_sites).ok();
    
    // 2. Realizar el chequeo
    let timeout_ms = 5000;
    let (online, latency, error, warning) = if site_type == "ping" {
        let (on, lat, err) = ping_ip(&address, timeout_ms);
        (on, lat, err, false)
    } else {
        check_http(&address, timeout_ms).await
    };
    
    // 3. Procesar resultados
    let mut prev_status = String::new();
    let mut new_status = String::new();
    
    {
        let mut config = state.config.lock().unwrap();
        if let Some(site) = config.sites.iter_mut().find(|s| s.id == site_id) {
            prev_status = if site.status == "checking" {
                site.last_status.clone().unwrap_or_else(|| "idle".to_string())
            } else {
                site.status.clone()
            };
            
            new_status = if online {
                if warning { "warning".to_string() } else { "online".to_string() }
            } else {
                "offline".to_string()
            };
            
            site.status = new_status.clone();
            site.last_status = Some(new_status.clone());
            site.last_check = Some(Local::now().to_rfc3339());
            site.last_latency = latency;
            site.last_error = error.clone();
            
            // Historial
            let history_item = SiteHistory {
                timestamp: site.last_check.clone().unwrap(),
                online,
                warning,
                latency,
            };
            site.history.push(history_item);
            if site.history.len() > 20 {
                site.history.remove(0);
            }
            
            save_config(&config);
        }
    }
    
    // Emitir estado actualizado
    let final_sites = {
        let config = state.config.lock().unwrap();
        config.sites.clone()
    };
    app_handle.emit("sites-updated", &final_sites).ok();
    
    update_tray_icon(&app_handle, &state);
    
    // Notificaciones
    let notifications_enabled = {
        let config = state.config.lock().unwrap();
        config.settings.notifications_enabled
    };
    
    if notifications_enabled && !prev_status.is_empty() && prev_status != "idle" && prev_status != "checking" {
        if prev_status != "offline" && new_status == "offline" {
            let body = format!("{} no responde. Detalle: {}", address, error.unwrap_or_else(|| "Sin respuesta".to_string()));
            trigger_notification(&format!("🚨 Sitio Caído: {}", site_name), &body);
        } else if prev_status == "offline" && new_status != "offline" {
            let latency_msg = match latency {
                Some(lat) => format!(" ({} ms)", lat),
                None => "".to_string(),
            };
            let body = format!("{} vuelve a estar en línea{}.", address, latency_msg);
            trigger_notification(&format!("✅ Sitio Recuperado: {}", site_name), &body);
        }
    }
}

// --- BUCLE PLANIFICADOR DE CHEQUEOS ---

fn start_scheduler(app_handle: AppHandle, state: Arc<AppState>) {
    std::thread::spawn(move || {
        let runtime = tokio::runtime::Runtime::new().unwrap();
        runtime.block_on(async {
            loop {
                tokio::time::sleep(std::time::Duration::from_secs(1)).await;
                
                let is_active = *state.is_monitoring_active.lock().unwrap();
                if !is_active { continue; }
                
                let (sites, global_interval) = {
                    let config = state.config.lock().unwrap();
                    (config.sites.clone(), config.settings.global_interval)
                };
                
                let mut timers = state.site_timers.lock().unwrap();
                for site in sites {
                    if !site.enabled {
                        timers.remove(&site.id);
                        continue;
                    }
                    
                    let interval = site.interval.unwrap_or(global_interval);
                    let trigger_check = match timers.get_mut(&site.id) {
                        Some(remaining) => {
                            if *remaining > 0 {
                                *remaining -= 1;
                            }
                            if *remaining == 0 {
                                *remaining = interval;
                                true
                            } else {
                                false
                            }
                        }
                        None => {
                            timers.insert(site.id.clone(), interval);
                            true
                        }
                    };
                    
                    if trigger_check {
                        let app_handle_clone = app_handle.clone();
                        let state_clone = state.clone();
                        tokio::spawn(check_site(site.id, app_handle_clone, state_clone));
                    }
                }
            }
        });
    });
}

// --- COMANDOS TAURI (IPCs) ---

#[tauri::command]
fn get_sites(state: State<'_, Arc<AppState>>) -> Vec<Site> {
    let config = state.config.lock().unwrap();
    config.sites.clone()
}

#[tauri::command]
fn get_settings(state: State<'_, Arc<AppState>>) -> Settings {
    let config = state.config.lock().unwrap();
    config.settings.clone()
}

#[tauri::command]
fn add_site(site: Site, state: State<'_, Arc<AppState>>, app: AppHandle) -> Result<Site, String> {
    let mut config = state.config.lock().unwrap();
    
    // Crear ID aleatorio
    let id = format!("{:x}", chrono::Utc::now().timestamp_millis());
    let mut new_site = site;
    new_site.id = id;
    new_site.enabled = true;
    new_site.status = "idle".to_string();
    new_site.history = Vec::new();
    
    config.sites.push(new_site.clone());
    save_config(&config);
    
    // Trigger inmediato
    let state_arc = app.state::<Arc<AppState>>().inner().clone();
    let app_clone = app.clone();
    let id_clone = new_site.id.clone();
    tokio::spawn(check_site(id_clone, app_clone, state_arc));
    
    app.emit("sites-updated", &config.sites).ok();
    update_tray_icon(&app, &**state);
    
    Ok(new_site)
}

#[tauri::command]
fn edit_site(id: String, site: Site, state: State<'_, Arc<AppState>>, app: AppHandle) -> Result<Site, String> {
    let mut config = state.config.lock().unwrap();
    let idx = config.sites.iter().position(|s| s.id == id).ok_or("Sitio no encontrado")?;
    
    let old_enabled = config.sites[idx].enabled;
    let old_address = config.sites[idx].address.clone();
    let old_type = config.sites[idx].site_type.clone();
    let old_interval = config.sites[idx].interval;
    
    config.sites[idx].name = site.name;
    config.sites[idx].site_type = site.site_type;
    config.sites[idx].address = site.address;
    config.sites[idx].interval = site.interval;
    
    let new_site = config.sites[idx].clone();
    save_config(&config);
    
    // Reiniciar monitores si cambió configuración crítica
    if old_enabled != new_site.enabled 
        || old_address != new_site.address 
        || old_type != new_site.site_type 
        || old_interval != new_site.interval 
    {
        let mut timers = state.site_timers.lock().unwrap();
        if new_site.enabled {
            timers.insert(id.clone(), new_site.interval.unwrap_or(config.settings.global_interval));
            let state_arc = app.state::<Arc<AppState>>().inner().clone();
            let app_clone = app.clone();
            let id_clone = id.clone();
            tokio::spawn(check_site(id_clone, app_clone, state_arc));
        } else {
            timers.remove(&id);
            config.sites[idx].status = "idle".to_string();
        }
    }
    
    app.emit("sites-updated", &config.sites).ok();
    update_tray_icon(&app, &**state);
    
    Ok(new_site)
}

#[tauri::command]
fn delete_site(id: String, state: State<'_, Arc<AppState>>, app: AppHandle) -> Result<(), String> {
    let mut config = state.config.lock().unwrap();
    let idx = config.sites.iter().position(|s| s.id == id).ok_or("Sitio no encontrado")?;
    
    config.sites.remove(idx);
    save_config(&config);
    
    state.site_timers.lock().unwrap().remove(&id);
    
    app.emit("sites-updated", &config.sites).ok();
    update_tray_icon(&app, &**state);
    
    Ok(())
}

#[tauri::command]
fn toggle_site(id: String, enabled: bool, state: State<'_, Arc<AppState>>, app: AppHandle) -> Result<Site, String> {
    let mut config = state.config.lock().unwrap();
    let idx = config.sites.iter().position(|s| s.id == id).ok_or("Sitio no encontrado")?;
    
    config.sites[idx].enabled = enabled;
    if !enabled {
        config.sites[idx].status = "idle".to_string();
        config.sites[idx].last_latency = None;
        config.sites[idx].last_error = None;
        state.site_timers.lock().unwrap().remove(&id);
    } else {
        state.site_timers.lock().unwrap().insert(id.clone(), config.sites[idx].interval.unwrap_or(config.settings.global_interval));
        let state_arc = app.state::<Arc<AppState>>().inner().clone();
        let app_clone = app.clone();
        let id_clone = id.clone();
        tokio::spawn(check_site(id_clone, app_clone, state_arc));
    }
    
    let site = config.sites[idx].clone();
    save_config(&config);
    
    app.emit("sites-updated", &config.sites).ok();
    update_tray_icon(&app, &**state);
    
    Ok(site)
}

#[tauri::command]
fn save_settings(settings: Settings, state: State<'_, Arc<AppState>>, app: AppHandle) -> Result<Settings, String> {
    let mut config = state.config.lock().unwrap();
    let old_autostart = config.settings.autostart;
    config.settings = settings.clone();
    save_config(&config);
    
    if old_autostart != settings.autostart {
        update_autostart(settings.autostart, &app);
    }
    
    Ok(settings)
}

#[tauri::command]
fn check_all_now(state: State<'_, Arc<AppState>>, app: AppHandle) -> Result<(), String> {
    let config = state.config.lock().unwrap();
    let state_arc = app.state::<Arc<AppState>>().inner().clone();
    
    for site in &config.sites {
        if site.enabled {
            let app_clone = app.clone();
            let state_clone = state_arc.clone();
            let id_clone = site.id.clone();
            tokio::spawn(check_site(id_clone, app_clone, state_clone));
        }
    }
    Ok(())
}

#[tauri::command]
fn check_site_now(id: String, state: State<'_, Arc<AppState>>, app: AppHandle) -> Result<(), String> {
    let config = state.config.lock().unwrap();
    let site = config.sites.iter().find(|s| s.id == id).ok_or("Sitio no encontrado")?;
    if site.enabled {
        let state_arc = app.state::<Arc<AppState>>().inner().clone();
        let app_clone = app.clone();
        tokio::spawn(check_site(id, app_clone, state_arc));
        Ok(())
    } else {
        Err("Sitio desactivado".to_string())
    }
}

// --- CONSTRUCTOR DE LA APLICACIÓN ---

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let initial_config = load_config();
    let initial_monitoring_active = true;
    
    let app_state = Arc::new(AppState {
        config: Mutex::new(initial_config),
        is_monitoring_active: Mutex::new(initial_monitoring_active),
        site_timers: Mutex::new(HashMap::new()),
    });
    
    let app_state_for_setup = app_state.clone();
    
    tauri::Builder::default()
        .manage(app_state) // Registrar estado tauri como Arc<AppState>
        .setup(move |app| {
            let app_handle = app.handle().clone();
            
            // 1. Configurar System Tray
            let open_i = MenuItem::with_id(app, "open", "Abrir MonTray", true, None::<&str>)?;
            let check_i = MenuItem::with_id(app, "check", "Verificar todo ahora", true, None::<&str>)?;
            let active_i = MenuItem::with_id(app, "active", "Monitoreo Activo", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Salir", true, None::<&str>)?;
            
            let menu = Menu::with_items(app, &[
                &open_i,
                &check_i,
                &active_i,
                &quit_i,
            ])?;
            
            let tray = TrayIconBuilder::with_id("main")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray_icon, event| {
                    if let TrayIconEvent::Click { button, .. } = event {
                        if button == tauri::tray::MouseButton::Left {
                            // Clic primario -> Toggle Ventana
                            let app = tray_icon.app_handle();
                            if let Some(window) = app.get_webview_window("main") {
                                if let Ok(visible) = window.is_visible() {
                                    if visible { window.hide().ok(); } else { window.show().ok(); window.set_focus().ok(); }
                                }
                            }
                        }
                    }
                })
                .on_menu_event(move |app, event| {
                    let state = app.state::<Arc<AppState>>().inner().clone();
                    match event.id().as_ref() {
                        "open" => {
                            if let Some(window) = app.get_webview_window("main") {
                                window.show().ok();
                                window.set_focus().ok();
                            }
                        }
                        "check" => {
                            let config = state.config.lock().unwrap();
                            for site in &config.sites {
                                if site.enabled {
                                    tokio::spawn(check_site(site.id.clone(), app.clone(), state.clone()));
                                }
                            }
                        }
                        "active" => {
                            let mut active = state.is_monitoring_active.lock().unwrap();
                            *active = !*active;
                            update_tray_icon(app, &state);
                        }
                        "quit" => {
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .build(app)?;
                
            update_tray_icon(&app_handle, &app_state_for_setup);
            
            // 2. Iniciar Planificador de Monitoreo
            start_scheduler(app_handle.clone(), app_state_for_setup.clone());
            
            // 3. Manejar arranque minimizado si se configuró
            let start_minimized = {
                let config = app_state_for_setup.config.lock().unwrap();
                config.settings.start_minimized
            };
            
            if start_minimized {
                if let Some(window) = app.get_webview_window("main") {
                    window.hide().ok();
                }
            }
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_sites,
            get_settings,
            add_site,
            edit_site,
            delete_site,
            toggle_site,
            check_all_now,
            check_site_now,
            save_settings
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
