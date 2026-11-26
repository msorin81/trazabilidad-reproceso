<#
  Programa (o reprograma) la actualización automática de la app web de reproceso.
  No requiere permisos de administrador: la tarea corre con tu usuario mientras tengas sesión iniciada.

  Cuándo corre:
    · cada 2 horas entre las 7:00 a. m. y las 7:00 p. m. (y siempre a las 6:00 p. m.);
    · cada vez que inicias sesión en Windows;
    · si el equipo estaba apagado o suspendido a la hora programada, apenas vuelva a estar disponible.
  Solo publica si los Excel cambiaron (si no, termina en unos segundos sin hacer nada).

  Uso:
    powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1                 (configuración por defecto)
    powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1 -CadaHoras 1    (cada hora)
    powershell -ExecutionPolicy Bypass -File programar_actualizacion.ps1 -Quitar         (eliminar la tarea)
#>
param([string]$Hora = "18:00", [int]$CadaHoras = 2, [string]$Desde = "07:00", [int]$DuranteHoras = 12,
      [switch]$Quitar)

$Nombre = "Reproceso - actualizar app web"
if ($Quitar) {
    Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarea eliminada."
    return
}

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyW = Join-Path $env:LOCALAPPDATA "anaconda3\pythonw.exe"   # pythonw: sin ventana
if (-not (Test-Path $PyW)) { throw "No se encontró $PyW" }
$Usuario = "$env:USERDOMAIN\$env:USERNAME"

$accion = New-ScheduledTaskAction -Execute $PyW -Argument "`"$AppDir\actualizar_datos.py`" --auto" -WorkingDirectory $AppDir

# 1) a la hora fija de siempre
$diaria = New-ScheduledTaskTrigger -Daily -At $Hora
# 2) cada N horas durante la jornada (más oportunidades si el equipo estuvo suspendido)
$jornada = New-ScheduledTaskTrigger -Daily -At $Desde
$rep = (New-ScheduledTaskTrigger -Once -At $Desde -RepetitionInterval (New-TimeSpan -Hours $CadaHoras) `
        -RepetitionDuration (New-TimeSpan -Hours $DuranteHoras)).Repetition
$jornada.Repetition = $rep
# 3) al iniciar sesión (con un minuto de espera para que OneDrive y la red estén listos)
$inicio = New-ScheduledTaskTrigger -AtLogOn -User $Usuario
$inicio.Delay = "PT1M"

$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
          -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger @($diaria, $jornada, $inicio) -Settings $config `
    -Principal $principal -Force `
    -Description "Lee los Excel de reproceso y publica los cambios en GitHub / Streamlit Cloud. Registro: $AppDir\logs\actualizacion_auto.log" |
    Out-Null
Write-Host "Tarea programada: '$Nombre'"
Write-Host "  · todos los días a las $Hora"
Write-Host "  · cada $CadaHoras h desde las $Desde durante $DuranteHoras h"
Write-Host "  · al iniciar sesión en Windows"
Write-Host "Próxima ejecución: $((Get-ScheduledTaskInfo -TaskName $Nombre).NextRunTime)"
