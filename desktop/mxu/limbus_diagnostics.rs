/// Opt-in local resource diagnostics: the sampler runs in the packaged launcher,
/// which owns a read-only view of this machine's counters.
///
/// The command is deliberately the smallest honest bridge: it starts the same
/// launcher the other panels already use, with a dedicated flag, and reads one
/// JSON snapshot from its stdout (`--resource-diagnostics`). The launcher takes
/// no controller lease on that path, sends no gameplay input and writes no
/// state; a stuck or absent provider comes back as a normal `unsupported` field
/// inside the snapshot, so only a real process failure is an error.
#[tauri::command]
pub async fn limbus_resource_diagnostics(interval_ms: Option<i64>) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        let app = exe.parent().ok_or("Application root unavailable")?;
        let launcher = app.join("launcher").join("MaaLimbusLauncher.exe");
        if !launcher.is_file() { return Err("Local diagnostics helper is missing from this package".into()); }
        let mut command = std::process::Command::new(launcher);
        command.arg("--app").arg(app).arg("--resource-diagnostics");
        if let Some(interval) = interval_ms {
            command.arg("--interval-ms").arg(interval.to_string());
        }
        command.current_dir(app);
        #[cfg(windows)] {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let result = command.output().map_err(|e| e.to_string())?;
        if !result.status.success() {
            return Err("Local resource diagnostics are unavailable; nothing was sampled and no input was sent.".into());
        }
        serde_json::from_slice(&result.stdout).map_err(|e| e.to_string())
    }).await.map_err(|e| e.to_string())?
}
