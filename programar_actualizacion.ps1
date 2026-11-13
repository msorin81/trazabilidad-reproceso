<#
  Programa (o reprograma) la actualización automática diaria de la app web de reproceso.
  No requiere permisos de administrador: la tarea corre con tu usuario mientras tengas sesión iniciada.
  Si el equipo está apagado a la hora programada, se ejecuta apenas lo enciendas.

  Uso:
    powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1              (todos los días 6:00 p. m.)
    powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1 -Hora 07:30  (otra hora)
    powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1 -Quitar      (eliminar la tarea)
#>
param([string]$Hora = "18:00", [switch]$Quitar)

$Nombre = "Reproceso - actualizar app web"
if ($Quitar) {
    Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarea eliminada."
    return
}

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyW = Join-Path $env:LOCALAPPDATA "anaconda3\pythonw.exe"   # pythonw: sin ventana
if (-not (Test-Path $PyW)) { throw "No se encontró $PyW" }

$accion = New-ScheduledTaskAction -Execute $PyW -Argument "`"$AppDir\actualizar_datos.py`" --auto" -WorkingDirectory $AppDir
$disparador = New-ScheduledTaskTrigger -Daily -At $Hora
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
          -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador -Settings $config -Principal $principal `
    -Description "Lee los Excel de reproceso y publica los cambios en GitHub / Streamlit Cloud. Registro: $AppDir\logs\actualizacion_auto.log" `
    -Force | Out-Null
$t = Get-ScheduledTask -TaskName $Nombre
Write-Host "Tarea programada: '$Nombre' todos los días a las $Hora."
Write-Host "Próxima ejecución: $((Get-ScheduledTaskInfo -TaskName $Nombre).NextRunTime)"
