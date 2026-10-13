# Busca e Apreensao - regenera todas as versoes a partir da cena principal.
#   01_Cena_Render_Cycles\busca.blend  (FONTE: modele aqui)
#     -> 02_Cena_VR_Otimizada  (Unity / Unreal: .blend, .glb, .fbx)
#     -> 04_ThreeJS\web         (WebXR: cena.glb, lightmaps, cena.json)
#   07_Personagens\rocketbox   -> 04_ThreeJS\web\personagens (personagens animados)
#
# Uso:  .\atualizar_tudo.ps1            (padrao)
#       .\atualizar_tudo.ps1 rapido     (teste)
#       .\atualizar_tudo.ps1 alta       (qualidade maxima)
#       .\atualizar_tudo.ps1 recriar    (refaz o .blend do zero pelo script busca.py - APAGA edicoes manuais)
$ErrorActionPreference = "Stop"
$B = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$D = $PSScriptRoot

Push-Location "$D\01_Cena_Render_Cycles"
if ($args -contains "recriar" -or -not (Test-Path "busca.blend")) {
    Write-Host "0/3  Criando a cena principal do zero (busca.py)..."
    & $B -b --factory-startup --python "busca.py" 2>&1 | Select-String -Pattern '^\[BUSCA\]' | ForEach-Object { $_.Line }
}
Write-Host "0/3  Integrando modelos novos e texturas CC0 na cena principal..."
& $B -b "busca.blend" --python "integrar_modelos.py" 2>&1 | Select-String -Pattern '^\[MODELOS\]' | ForEach-Object { $_.Line }
& $B -b "busca.blend" --python "aplicar_texturas_cc0.py" 2>&1 | Select-String -Pattern '^\[CC0\]' | ForEach-Object { $_.Line }
Pop-Location

Write-Host "1/3  Gerando versao VR (Unity/Unreal)..."
Push-Location "$D\02_Cena_VR_Otimizada"
& $B -b "$D\01_Cena_Render_Cycles\busca.blend" --python "otimizar_para_vr.py" *> vr_log.txt
Pop-Location
Select-String -Path "$D\02_Cena_VR_Otimizada\vr_log.txt" -Pattern '^\[VR\] (TOTAL|Colisao)' | ForEach-Object { $_.Line }

Write-Host "2/3  Gerando versao three.js (bake de lightmaps)..."
Push-Location "$D\04_ThreeJS"
$nivel = $args | Where-Object { $_ -in "rapido", "alta" }
& $B -b "$D\02_Cena_VR_Otimizada\busca_VR.blend" --python "pipeline_threejs.py" -- $nivel *> pipeline_log.txt
Pop-Location
Select-String -Path "$D\04_ThreeJS\pipeline_log.txt" -Pattern '^\[THREE\]' | ForEach-Object { $_.Line }

Write-Host "3/3  Personagens (Rocketbox -> 04_ThreeJS\web\personagens; so refaz o que mudou)..."
if ((Test-Path "$D\07_Personagens\rocketbox") -or (Test-Path "$D\..\leiseca\07_Personagens\rocketbox")) {
    & $B -b --factory-startup --python "$D\07_Personagens\converter_personagens.py" 2>&1 | Select-String -Pattern '^\[PERSONAGENS\]' | ForEach-Object { $_.Line }
} else { Write-Host "     (pasta 07_Personagens\rocketbox nao existe; mantidos os .glb atuais - ver 07_Personagens\LEIA-ME.md)" }
Write-Host "Pronto. Para ver no navegador: 04_ThreeJS\web\iniciar_servidor.bat"
