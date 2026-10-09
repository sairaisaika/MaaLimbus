#[tauri::command]
pub async fn limbus_project_update_check() -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let exe=std::env::current_exe().map_err(|e|e.to_string())?;
        let app=exe.parent().ok_or("Application root unavailable")?;
        let launcher=app.join("launcher").join("MaaLimbusLauncher.exe");
        if !launcher.is_file(){return Err("Update helper is missing from this package".into());}
        let mut command=std::process::Command::new(launcher);
        command.arg("--app").arg(app).arg("--check-only").current_dir(app);
        #[cfg(windows)] {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let result=command.status().map_err(|e|e.to_string())?;
        if !result.success(){return Err("Update check failed; running software was not replaced".into());}
        let bytes=std::fs::read(app.join("config/user-update-check-result.json")).map_err(|e|e.to_string())?;
        serde_json::from_slice(&bytes).map_err(|e|e.to_string())
    }).await.map_err(|e|e.to_string())?
}
