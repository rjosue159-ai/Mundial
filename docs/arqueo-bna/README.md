# Arqueo de Efectivo — Depositarios BNA

Respaldo de los entregables **estables** del proceso RPA de arqueo (Fedecrédito / E2ASolutions). Alcance: **cajeros BNA**.

> **Estado:** el código PAD que ejecuta el arqueo (extracción de FIN TRACE y cálculo del MONTO) **todavía NO está aquí**: queda pendiente de validarse en la VM antes de subirse. Este respaldo contiene lo que ya está validado en lógica: el motor de notificaciones, las plantillas de correo, los diagramas y las explicaciones.
>
> **No se incluye ningún dato real** (transacciones, montos de clientes, números de tarjeta, archivos `.xlsb`/CSV de datos). El único número de tarjeta que aparecía en un ejemplo está enmascarado.

## Estructura

```
docs/arqueo-bna/
├── notificaciones/
│   ├── notif_engine.ps1                 Motor de notificaciones (agrupa por entidad + arma el HTML). PROBADO con datos reales.
│   ├── gen_notif_engine.py              Generador del motor (embebe el catálogo y las plantillas HTML).
│   ├── catalogo_depositarios.json       Mapeo cajero → entidad socia (22 depositarios).
│   ├── plantilla_correo_ejecucion.html  Plantilla del correo por entidad (datos de ejemplo).
│   └── plantillas_correo_inicio_fin.html Plantillas de los correos de inicio y fin.
├── diagramas/
│   ├── Arqueo_BNA_Flujo.pdf             Diagrama de flujo del proceso (2 páginas).
│   ├── Arqueo_BNA_Flujo_pagina1.png / pagina2.png
│   └── flujo_diagrama.html              Fuente del diagrama.
├── explicacion/
│   ├── Arqueo_BNA_Explicacion_FinTrace_Monto.pdf   Explicación (simple + técnica línea por línea).
│   └── explicacion_codigo.html          Fuente.
└── especificacion/
    └── Arqueo_BNA_Especificacion.docx   Especificación funcional del arqueo.
```

## Módulo de notificaciones (en PAD, al final del proceso)

Las notificaciones corren **dentro del mismo PAD**, después de que el robot termina todos los arqueos.

1. **Al arrancar el robot** → correo de **inicio** (a `%CorreoPrueba%`).
2. **Durante el arqueo** (por cada cajero) → guardar el A030 en `%rutaa030%\<cajero>_<fecha>.xlsx` y agregar una fila a `resumen_hoy.csv` con las columnas:
   `NO,CONCEPTO,D1,D2,D5,D10,D20,D50,D100,TOTAL,FECHA,MONTO,DIFERENCIA`.
3. **Al terminar la cola:**
   - Ejecutar `notif_engine.ps1` pasándole `resumen_hoy.csv`, `CorreoPrueba`, `rutaa030`, `LinkMaster`, `FechaHoy`, `FechaEnvio`.
   - Convertir la salida JSON a objeto → `Notif`.
   - Por cada `Notif.ejecucion` → enviar el correo de la entidad (HTML + adjuntos A030) con el módulo de correo existente.
   - Enviar el correo de **fin** (`Notif.fin`).

En modo prueba, `%CorreoPrueba%` = un solo correo, y todos los envíos llegan ahí.

### Ejecutar el motor (ejemplo)

```powershell
& '.\notif_engine.ps1' -MasterCsv 'resumen_hoy.csv' -CorreoPrueba 'correo@dominio' `
  -Rutaa030 'C:\RPA\A030' -LinkMaster 'https://.../Master.xlsb' `
  -FechaHoy '25/07/2026' -FechaEnvio 'lunes, 28 de julio de 2026 09:15'
```

Devuelve un JSON con `ejecucion[]` (un correo por entidad, con `to`, `cc`, `asunto`, `html`, `adjuntos[]`) y `fin` (`to`, `asunto`, `html`).
