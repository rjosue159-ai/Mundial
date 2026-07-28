# -*- coding: utf-8 -*-
# Genera notif_engine.ps1 (agrupador + HTML) embebiendo el catalogo.
import json
cat=json.load(open('cat_dep.json',encoding='utf-8'))

cat_lines=[]
for cod,v in cat.items():
    ent=v['ent'].replace("'","''"); nom=v['nombre'].replace("'","''")
    cat_lines.append("$cat['%s']=@{codEnt='%s';ent='%s';nombre='%s';interno='%s'}"%(cod,v['codEnt'],ent,nom,v['interno']))
CAT="\n".join(cat_lines)

# --- plantillas HTML (single-quoted, tokens {{...}}) ---
SHELL_EJEC = r'''<table role="presentation" cellpadding="0" cellspacing="0" width="1000" style="border-collapse:collapse;background:#ffffff;font-family:Arial,Helvetica,sans-serif;">
<tr><td style="background:#1e8a4c;height:60px;text-align:center;color:#fff;font-size:18px;font-weight:bold;">Sistema FEDECREDITO &nbsp;&middot;&nbsp; RPA</td></tr>
<tr><td style="background:#efefef;border:1px solid #d8d8d8;padding:6px 12px;font-size:13px;font-weight:bold;color:#333;">Notificacion del Robot</td></tr>
<tr><td style="padding:16px 14px 4px;text-align:center;">
<div style="color:#1b7a44;font-size:15px;font-weight:bold;">Se envia la informacion correspondiente al arqueo de Depositarios BNA para su entidad {{CODENT}} - {{ENT}}</div>
<div style="color:#1b7a44;font-size:13px;font-weight:bold;margin-top:4px;">Fecha de envio : {{FECHAENVIO}}</div></td></tr>
<tr><td style="padding:12px 14px 18px;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:12px;color:#222;">
<tr>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">ATM</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;text-align:left;">UBICACION</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">FECHA</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">$1</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">$2</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">$5</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">$10</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">$20</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">$50</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">$100</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">TOTAL</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">MONTO</th>
<th style="border:1px solid #9a9a9a;padding:7px 6px;">DIFERENCIA</th>
</tr>
{{FILAS}}
{{TOTAL}}
</table></td></tr>
<tr><td style="background:#1e8a4c;height:32px;text-align:center;color:#fff;font-size:12px;font-weight:bold;">Este correo electronico ha sido generado automaticamente por un Robot.</td></tr>
</table>'''

ROW_EJEC = r'''<tr>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:center;">{{ATM}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;">{{UBIC}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:center;">{{FECHA}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{D1}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{D2}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{D5}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{D10}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{D20}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{D50}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{D100}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;font-weight:bold;">{{TOTAL}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{MONTO}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;color:{{DIFCOLOR}};font-weight:bold;">{{DIF}}</td>
</tr>'''

TOTROW = r'''<tr style="background:#f4f4f4;font-weight:bold;">
<td style="border:1px solid #9a9a9a;padding:6px;text-align:center;" colspan="3">Total general</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TD1}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TD2}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TD5}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TD10}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TD20}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TD50}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TD100}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TTOTAL}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;">{{TMONTO}}</td>
<td style="border:1px solid #9a9a9a;padding:6px;text-align:right;color:{{TDIFCOLOR}};">{{TDIF}}</td>
</tr>'''

SHELL_FIN = r'''<table role="presentation" cellpadding="0" cellspacing="0" width="920" style="border-collapse:collapse;background:#fff;font-family:Arial,Helvetica,sans-serif;">
<tr><td style="background:#1e8a4c;height:60px;text-align:center;color:#fff;font-size:18px;font-weight:bold;">Sistema FEDECREDITO &nbsp;&middot;&nbsp; RPA</td></tr>
<tr><td style="background:#efefef;border:1px solid #d8d8d8;padding:6px 12px;font-size:13px;font-weight:bold;color:#333;">Notificacion del Robot</td></tr>
<tr><td style="padding:18px 20px 4px;text-align:center;">
<div style="color:#1b7a44;font-size:16px;font-weight:bold;">El proceso de arqueo de efectivo ha finalizado - Depositarios BNA</div>
<div style="color:#1b7a44;font-size:13px;font-weight:bold;margin-top:6px;">Fecha de finalizacion : {{FECHAENVIO}}</div></td></tr>
<tr><td style="padding:10px 20px;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;text-align:center;font-size:13px;">
<tr>
<td style="border:1px solid #cfcfcf;padding:10px;"><div style="color:#666;font-size:11px;font-weight:bold;">CAJEROS ARQUEADOS</div><div style="font-size:20px;font-weight:bold;color:#1b2930;">{{NARQ}}</div></td>
<td style="border:1px solid #cfcfcf;padding:10px;"><div style="color:#666;font-size:11px;font-weight:bold;">CUADRADOS</div><div style="font-size:20px;font-weight:bold;color:#1b7a44;">{{NCUAD}}</div></td>
<td style="border:1px solid #cfcfcf;padding:10px;"><div style="color:#666;font-size:11px;font-weight:bold;">A REVISAR</div><div style="font-size:20px;font-weight:bold;color:#c0392b;">{{NREV}}</div></td>
</tr></table></td></tr>
<tr><td style="padding:6px 20px 4px;font-size:12px;font-weight:bold;color:#333;">Cajeros con diferencia (a revisar):</td></tr>
<tr><td style="padding:2px 20px 14px;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;font-size:12px;color:#222;">
<tr>
<th style="border:1px solid #9a9a9a;padding:6px;">ENTIDAD</th>
<th style="border:1px solid #9a9a9a;padding:6px;">ATM</th>
<th style="border:1px solid #9a9a9a;padding:6px;text-align:left;">UBICACION</th>
<th style="border:1px solid #9a9a9a;padding:6px;">FECHA</th>
<th style="border:1px solid #9a9a9a;padding:6px;">TOTAL</th>
<th style="border:1px solid #9a9a9a;padding:6px;">MONTO</th>
<th style="border:1px solid #9a9a9a;padding:6px;">DIFERENCIA</th>
</tr>
{{FILASREV}}
</table></td></tr>
<tr><td style="padding:4px 20px 20px;text-align:center;font-size:13px;"><a href="{{LINK}}" style="color:#1b7a44;font-weight:bold;">Ver el detalle completo del arqueo en SharePoint (Master)</a></td></tr>
<tr><td style="background:#1e8a4c;height:32px;text-align:center;color:#fff;font-size:12px;font-weight:bold;">Este correo electronico ha sido generado automaticamente por un Robot.</td></tr>
</table>'''

ROW_FIN = r'''<tr>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:center;">{{ENT}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:center;">{{ATM}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;">{{UBIC}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:center;">{{FECHA}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{TOTAL}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;">{{MONTO}}</td>
<td style="border:1px solid #cfcfcf;padding:6px;text-align:right;color:#c0392b;font-weight:bold;">{{DIF}}</td>
</tr>'''

def psq(s):  # a single-quoted PS here-string
    return "@'\n"+s+"\n'@"

ps = r'''param($MasterCsv,$CorreoPrueba,$Rutaa030,$LinkMaster,$FechaHoy,$FechaEnvio)
$ErrorActionPreference='Stop'
$ci=[Globalization.CultureInfo]::InvariantCulture

$cat=@{}
__CAT__

function Money($v){ if($null -eq $v -or ("$v").Trim() -eq ''){return '0.00'}; return ([double]::Parse(("$v"),$ci)).ToString('F2',$ci) }
function ToNum($v){ if($null -eq $v -or ("$v").Trim() -eq ''){return 0.0}; return [double]::Parse(("$v"),$ci) }

$SHELL_EJEC=__SHELL_EJEC__
$ROW_EJEC=__ROW_EJEC__
$TOTROW=__TOTROW__
$SHELL_FIN=__SHELL_FIN__
$ROW_FIN=__ROW_FIN__

$rows = Import-Csv -Path $MasterCsv
$hoy = @($rows | Where-Object { $_.FECHA -eq $FechaHoy })
if($hoy.Count -eq 0){ $hoy = $rows }   # respaldo para prueba

$reg = foreach($r in $hoy){
  $c = $cat[("$($r.NO)")]
  [pscustomobject]@{ NO=$r.NO; UBIC=$r.CONCEPTO; FECHA=$r.FECHA;
    D1=$r.D1;D2=$r.D2;D5=$r.D5;D10=$r.D10;D20=$r.D20;D50=$r.D50;D100=$r.D100;
    TOTAL=$r.TOTAL; MONTO=$r.MONTO; DIF=$r.DIFERENCIA;
    codEnt=$(if($c){$c.codEnt}else{'??'}); ent=$(if($c){$c.ent}else{'DESCONOCIDA'}) }
}

$ejec=@()
foreach($g in ($reg | Group-Object codEnt)){
  $ent=$g.Group[0].ent; $codEnt=$g.Name
  $filas=''
  $tD1=0.0;$tD2=0.0;$tD5=0.0;$tD10=0.0;$tD20=0.0;$tD50=0.0;$tD100=0.0;$tTot=0.0;$tMon=0.0;$tDif=0.0
  foreach($x in $g.Group){
    $dc = if((ToNum $x.DIF) -eq 0){'#1b7a44'}else{'#c0392b'}
    $fila = $ROW_EJEC
    $fila = $fila.Replace('{{ATM}}',"$($x.NO)").Replace('{{UBIC}}',"$($x.UBIC)").Replace('{{FECHA}}',"$($x.FECHA)")
    $fila = $fila.Replace('{{D1}}',(Money $x.D1)).Replace('{{D2}}',(Money $x.D2)).Replace('{{D5}}',(Money $x.D5)).Replace('{{D10}}',(Money $x.D10)).Replace('{{D20}}',(Money $x.D20)).Replace('{{D50}}',(Money $x.D50)).Replace('{{D100}}',(Money $x.D100))
    $fila = $fila.Replace('{{TOTAL}}',(Money $x.TOTAL)).Replace('{{MONTO}}',(Money $x.MONTO)).Replace('{{DIF}}',(Money $x.DIF)).Replace('{{DIFCOLOR}}',$dc)
    $filas += $fila
    $tD1+=ToNum $x.D1;$tD2+=ToNum $x.D2;$tD5+=ToNum $x.D5;$tD10+=ToNum $x.D10;$tD20+=ToNum $x.D20;$tD50+=ToNum $x.D50;$tD100+=ToNum $x.D100;$tTot+=ToNum $x.TOTAL;$tMon+=ToNum $x.MONTO;$tDif+=ToNum $x.DIF
  }
  $tdc = if($tDif -eq 0){'#1b7a44'}else{'#c0392b'}
  $tr=$TOTROW.Replace('{{TD1}}',$tD1.ToString('F2',$ci)).Replace('{{TD2}}',$tD2.ToString('F2',$ci)).Replace('{{TD5}}',$tD5.ToString('F2',$ci)).Replace('{{TD10}}',$tD10.ToString('F2',$ci)).Replace('{{TD20}}',$tD20.ToString('F2',$ci)).Replace('{{TD50}}',$tD50.ToString('F2',$ci)).Replace('{{TD100}}',$tD100.ToString('F2',$ci)).Replace('{{TTOTAL}}',$tTot.ToString('F2',$ci)).Replace('{{TMONTO}}',$tMon.ToString('F2',$ci)).Replace('{{TDIF}}',$tDif.ToString('F2',$ci)).Replace('{{TDIFCOLOR}}',$tdc)
  $html=$SHELL_EJEC.Replace('{{CODENT}}',$codEnt).Replace('{{ENT}}',$ent).Replace('{{FECHAENVIO}}',$FechaEnvio).Replace('{{FILAS}}',$filas).Replace('{{TOTAL}}',$tr)
  $adj=@($g.Group | ForEach-Object { $Rutaa030 + '\' + "$($_.NO)_" + ($_.FECHA -replace '/','') + '.xlsx' })
  $ejec += [pscustomobject]@{ to=$CorreoPrueba; cc=$CorreoPrueba; asunto=("Arqueo Depositarios BNA - " + $codEnt + " " + $ent); html=$html; adjuntos=$adj }
}

$narq=$reg.Count
$cuad=@($reg | Where-Object { (ToNum $_.DIF) -eq 0 }).Count
$nrev=$narq-$cuad
$filasRev=''
foreach($x in ($reg | Where-Object { (ToNum $_.DIF) -ne 0 })){
  $fr=$ROW_FIN.Replace('{{ENT}}',($x.codEnt+' - '+$x.ent)).Replace('{{ATM}}',"$($x.NO)").Replace('{{UBIC}}',"$($x.UBIC)").Replace('{{FECHA}}',"$($x.FECHA)").Replace('{{TOTAL}}',(Money $x.TOTAL)).Replace('{{MONTO}}',(Money $x.MONTO)).Replace('{{DIF}}',(Money $x.DIF))
  $filasRev+=$fr
}
$finHtml=$SHELL_FIN.Replace('{{FECHAENVIO}}',$FechaEnvio).Replace('{{NARQ}}',"$narq").Replace('{{NCUAD}}',"$cuad").Replace('{{NREV}}',"$nrev").Replace('{{FILASREV}}',$filasRev).Replace('{{LINK}}',$LinkMaster)
$fin=[pscustomobject]@{ to=$CorreoPrueba; asunto='Arqueo Depositarios BNA - Resumen final'; html=$finHtml }

[pscustomobject]@{ ejecucion=$ejec; fin=$fin } | ConvertTo-Json -Depth 6
'''

ps = ps.replace('__CAT__',CAT)
ps = ps.replace('__SHELL_EJEC__',psq(SHELL_EJEC))
ps = ps.replace('__ROW_EJEC__',psq(ROW_EJEC))
ps = ps.replace('__TOTROW__',psq(TOTROW))
ps = ps.replace('__SHELL_FIN__',psq(SHELL_FIN))
ps = ps.replace('__ROW_FIN__',psq(ROW_FIN))
open('notif_engine.ps1','w',encoding='utf-8').write(ps)
print('notif_engine.ps1 generado,', len(ps),'chars')
