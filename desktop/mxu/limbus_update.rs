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
#[tauri::command]
pub async fn limbus_rotation_manage(request_id: Option<String>, expected_rotation: Option<i64>) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        let app = exe.parent().ok_or("Application root unavailable")?;
        let launcher = app.join("launcher").join("MaaLimbusLauncher.exe");
        if !launcher.is_file() { return Err("Rotation helper is missing from this package".into()); }
        let mut command = std::process::Command::new(launcher);
        command.arg("--app").arg(app).current_dir(app);
        match request_id {
            Some(id) => {
                let cursor = expected_rotation.ok_or("Read rotation before skipping")?;
                command.arg("--skip-team").arg(id).arg("--expected-rotation").arg(cursor.to_string());
            },
            None => { command.arg("--rotation-status"); }
        }
        #[cfg(windows)] {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let result = command.output().map_err(|e| e.to_string())?;
        if !result.status.success() {
            return Err("Rotation change refused: finish the run and payout, or refresh the team. No gameplay input was sent.".into());
        }
        serde_json::from_slice(&result.stdout).map_err(|e| e.to_string())
    }).await.map_err(|e| e.to_string())?
}
