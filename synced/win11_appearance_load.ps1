# Import Windows 11 User Settings
# Restores: appearance, taskbar, Start, Explorer, themes, DWM, wallpaper,
#           fonts, cursors, sounds, keyboard/language, regional, privacy,
#           notifications, accessibility, visual effects, power plan,
#           default app associations, and Start/taskbar layout.
#
# Source folder: <script dir>\Win11AppearanceExport
# Run as the target user.
# NOTE: A few steps (DISM app associations, Set-TimeZone) require elevation
#       the script will warn and skip them when not running as Administrator.

$ImportPath = "$PSScriptRoot\Win11AppearanceExport"

if (-not (Test-Path $ImportPath)) {
    Write-Error "Import path not found: $ImportPath"
    exit 1
}

function Test-Admin {
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object System.Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

$IsAdmin = Test-Admin

# --- Registry ----------------------------------------------------------------

Write-Host "Importing registry keys..."
$RegDir = "$ImportPath\reg"
if (Test-Path $RegDir) {
    Get-ChildItem -Path $RegDir -Filter *.reg | ForEach-Object {
        Write-Host "  $($_.Name)"
        reg import $_.FullName 2>&1 | Out-Null
    }
} else {
    Write-Warning "No reg\ folder found - skipping."
}

# --- Wallpaper ---------------------------------------------------------------

Write-Host "Restoring wallpaper..."
$WallpaperDir = "$ImportPath\wallpaper"
if (Test-Path "$WallpaperDir\wallpaper_path.txt") {
    $OriginalPath = (Get-Content "$WallpaperDir\wallpaper_path.txt").Trim()
    if (-not $OriginalPath) {
        Write-Host "  No wallpaper configured (wallpaper_path.txt is empty)."
    } else {
        $OriginalName = Split-Path $OriginalPath -Leaf

        # Prefer the original file if it still exists, otherwise use our copy
        if (Test-Path $OriginalPath) {
            $RestorePath = $OriginalPath
        } elseif (Test-Path "$WallpaperDir\$OriginalName") {
            # Copy it back to the original location (best effort)
            New-Item -ItemType Directory -Force -Path (Split-Path $OriginalPath) | Out-Null
            Copy-Item "$WallpaperDir\$OriginalName" -Destination $OriginalPath -Force -ErrorAction SilentlyContinue
            $RestorePath = $OriginalPath
        } elseif (Test-Path "$WallpaperDir\TranscodedWallpaper.jpg") {
            $RestorePath = "$WallpaperDir\TranscodedWallpaper.jpg"
        } else {
            $RestorePath = $null
            Write-Warning "  Wallpaper file not found."
        }

        if ($RestorePath) {
            Set-ItemProperty -Path "HKCU:\Control Panel\Desktop" -Name Wallpaper -Value $RestorePath
            # WallpaperStyle / TileWallpaper are already set by the reg import above.
            rundll32.exe user32.dll, UpdatePerUserSystemParameters
            Write-Host "  Wallpaper set to: $RestorePath"
        }
    }
}

# --- Theme file --------------------------------------------------------------

Write-Host "Applying theme..."
$ThemeDir = "$ImportPath\theme"
if (Test-Path $ThemeDir) {
    $ThemeFile = Get-ChildItem -Path $ThemeDir -Filter *.theme | Select-Object -First 1
    if ($ThemeFile) {
        # Copy to a fixed canonical path so Windows applies it in-place without creating duplicates.
        $CanonicalThemePath = "$env:LOCALAPPDATA\Microsoft\Windows\Themes\Custom.theme"
        New-Item -ItemType Directory -Force -Path (Split-Path $CanonicalThemePath) | Out-Null
        Copy-Item $ThemeFile.FullName -Destination $CanonicalThemePath -Force
        Start-Process $CanonicalThemePath
        Write-Host "  Theme applied: $CanonicalThemePath"
    }
}

# --- Accent color ------------------------------------------------------------

Write-Host "Restoring accent color..."
if (Test-Path "$ImportPath\accent_color.json") {
    try {
        $Info = Get-Content "$ImportPath\accent_color.json" | ConvertFrom-Json
        # AccentColor is a DWORD that may exceed Int32 range.
        # Use reg.exe which handles unsigned DWORD values correctly.
        $DwmRegPath = "HKCU\Software\Microsoft\Windows\DWM"
        if ($null -ne $Info.AccentColor) {
            reg add $DwmRegPath /v AccentColor /t REG_DWORD /d ([long]$Info.AccentColor) /f 2>&1 | Out-Null
        }
        if ($null -ne $Info.AccentColorInactive) {
            reg add $DwmRegPath /v AccentColorInactive /t REG_DWORD /d ([long]$Info.AccentColorInactive) /f 2>&1 | Out-Null
        }
        if ($null -ne $Info.ColorPrevalence) {
            reg add $DwmRegPath /v ColorPrevalence /t REG_DWORD /d ([long]$Info.ColorPrevalence) /f 2>&1 | Out-Null
        }
        # ColorizationColor is computed by the OS; no need to set it.
    } catch {
        Write-Warning "  Could not restore accent color: $_"
    }
}

# --- Start / Taskbar layout --------------------------------------------------

Write-Host "Restoring Start/Taskbar layout..."
$LayoutDir = "$ImportPath\layout"

# Win11: write LayoutModification.json to the Shell folder, then restart Explorer
$LayoutJson = "$LayoutDir\LayoutModification.json"
if (Test-Path $LayoutJson) {
    $ShellDir = "$env:LOCALAPPDATA\Microsoft\Windows\Shell"
    New-Item -ItemType Directory -Force -Path $ShellDir | Out-Null
    Copy-Item $LayoutJson -Destination $ShellDir -Force
    Write-Host "  LayoutModification.json placed. Explorer restart will apply it."
}

# Win10-style XML: Import-StartLayout was removed in Win11. Skip on Win11+.
$OsBuild = [System.Environment]::OSVersion.Version.Build
$LayoutXml = "$LayoutDir\StartLayout.xml"
if ((Test-Path $LayoutXml) -and ($OsBuild -lt 22000)) {
    try {
        Import-StartLayout -LayoutPath $LayoutXml -MountPath "$env:SystemDrive\" -ErrorAction Stop
        Write-Host "  StartLayout.xml applied."
    } catch {
        Write-Warning "  Import-StartLayout failed: $_"
    }
}

# --- Keyboard / Language list ------------------------------------------------

Write-Host "Restoring keyboard/language settings..."
$LocaleDir = "$ImportPath\locale"

if (Test-Path "$LocaleDir\language_list.json") {
    try {
        $LangData = Get-Content "$LocaleDir\language_list.json" | ConvertFrom-Json
        # Build the new list starting from the first language, then replace entries
        $NewList = New-WinUserLanguageList $LangData[0].LanguageTag
        # Remove the auto-added default entry so we can rebuild from scratch
        $NewList.Clear()
        foreach ($lang in $LangData) {
            $entry = New-WinUserLanguageList $lang.LanguageTag
            # Carry over input method tips if present
            if ($lang.InputMethodTips -and $lang.InputMethodTips.Count -gt 0) {
                $entry[0].InputMethodTips.Clear()
                foreach ($tip in $lang.InputMethodTips) {
                    $entry[0].InputMethodTips.Add($tip)
                }
            }
            $NewList.Add($entry[0])
        }
        Set-WinUserLanguageList $NewList -Force
        Write-Host "  Language list applied."
    } catch {
        Write-Warning "  Could not restore language list: $_"
    }
}

if (Test-Path "$LocaleDir\locale_settings.json") {
    $Loc = Get-Content "$LocaleDir\locale_settings.json" | ConvertFrom-Json

    if ($Loc.SystemLocale) {
        try   { Set-WinSystemLocale $Loc.SystemLocale; Write-Host "  System locale set to: $($Loc.SystemLocale)" }
        catch { Write-Warning "  Could not set system locale: $_" }
    }

    if ($Loc.UILanguage) {
        try   { Set-WinUILanguageOverride -Language $Loc.UILanguage; Write-Host "  UI language override set to: $($Loc.UILanguage)" }
        catch { Write-Warning "  Could not set UI language override: $_" }
    }

    if ($Loc.HomeLocation) {
        try   { Set-WinHomeLocation -GeoId $Loc.HomeLocation; Write-Host "  Home location set to GeoId: $($Loc.HomeLocation)" }
        catch { Write-Warning "  Could not set home location: $_" }
    }

    if ($Loc.TimeZone) {
        if ($IsAdmin) {
            try   { Set-TimeZone -Id $Loc.TimeZone; Write-Host "  Time zone set to: $($Loc.TimeZone)" }
            catch { Write-Warning "  Could not set time zone: $_" }
        } else {
            Write-Warning "  Skipping time zone '$($Loc.TimeZone)' - requires elevation. Re-run as Administrator."
        }
    }
}

# --- Default app associations ------------------------------------------------

Write-Host "Restoring default app associations..."
$AssocFile = "$ImportPath\appassoc\DefaultAppAssociations.xml"
if (Test-Path $AssocFile) {
    if ($IsAdmin) {
        $result = & dism.exe /Online /Import-DefaultAppAssociations:"$AssocFile" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  App associations imported via DISM."
        } else {
            Write-Warning "  DISM import returned $LASTEXITCODE - associations may not be fully applied."
        }
    } else {
        Write-Warning "  Skipping app associations import (requires elevation). Re-run as admin to apply."
    }
} else {
    Write-Host "  No app associations file found (not captured - re-run dump as Administrator to capture)."
}

# --- Power plan --------------------------------------------------------------

Write-Host "Restoring power plan..."
$PowerFile = "$ImportPath\power\ActivePowerPlan.pow"
$GuidFile  = "$ImportPath\power\active_plan_guid.txt"
if (Test-Path $PowerFile) {
    & powercfg /import "$PowerFile" 2>&1 | Out-Null
    if (Test-Path $GuidFile) {
        $PlanGuid = Get-Content $GuidFile
        & powercfg /setactive $PlanGuid 2>&1 | Out-Null
        Write-Host "  Power plan imported and activated: $PlanGuid"
    }
}

# --- User-installed fonts ----------------------------------------------------

Write-Host "Restoring user-installed fonts..."
$FontSrc = "$ImportPath\fonts"
if (Test-Path $FontSrc) {
    $FontDest = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
    New-Item -ItemType Directory -Force -Path $FontDest | Out-Null
    $Fonts = Get-ChildItem $FontSrc -File
    foreach ($font in $Fonts) {
        $Dest = "$FontDest\$($font.Name)"
        if (-not (Test-Path $Dest)) {
            Copy-Item $font.FullName -Destination $Dest -Force

            # Register the font in the user-scope key (Win11 / 1809+)
            $FontName = [System.IO.Path]::GetFileNameWithoutExtension($font.Name)
            $RegKey   = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
            # Only register if key exists (it may not on very clean installs)
            if (Test-Path $RegKey) {
                Set-ItemProperty -Path $RegKey -Name "$FontName (TrueType)" -Value $font.Name -ErrorAction SilentlyContinue
            }
        }
    }
    Write-Host "  Installed $($Fonts.Count) font(s)."
} else {
    Write-Host "  No user fonts to restore."
}

# --- User Start Menu shortcuts -----------------------------------------------

Write-Host "Restoring Start Menu shortcuts..."
$StartMenuSrc  = "$ImportPath\startmenu"
$StartMenuDest = "$env:APPDATA\Microsoft\Windows\Start Menu"
if (Test-Path $StartMenuSrc) {
    Get-ChildItem -Path $StartMenuSrc -Recurse -File |
        Where-Object { $_.Name -ne 'desktop.ini' } |
        ForEach-Object {
            $Dest = $_.FullName.Replace($StartMenuSrc, $StartMenuDest)
            New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
            Copy-Item -Path $_.FullName -Destination $Dest -Force -ErrorAction SilentlyContinue
        }
    Write-Host "  Start Menu shortcuts restored."
}

# --- Custom cursor files -----------------------------------------------------

Write-Host "Restoring cursor files..."
$CursorSrc = "$ImportPath\cursors"
if (Test-Path $CursorSrc) {
    # Copy custom cursor files back to their referenced paths
    $CursorKey = "HKCU:\Control Panel\Cursors"
    Get-ItemProperty $CursorKey -ErrorAction SilentlyContinue |
        ForEach-Object PSObject | Select-Object -ExpandProperty Properties |
        Where-Object { $_.Value -match '\.(cur|ani)$' } |
        ForEach-Object {
            $OrigPath = [System.Environment]::ExpandEnvironmentVariables($_.Value)
            $FileName = Split-Path $OrigPath -Leaf
            $SrcFile  = "$CursorSrc\$FileName"
            if ((Test-Path $SrcFile) -and (-not (Test-Path $OrigPath))) {
                New-Item -ItemType Directory -Force -Path (Split-Path $OrigPath) | Out-Null
                Copy-Item $SrcFile -Destination $OrigPath -Force -ErrorAction SilentlyContinue
            }
        }
    # Refresh cursor scheme (no reboot needed)
    $CursorProps = Get-ItemProperty $CursorKey
    $SchemeName  = $CursorProps.'(default)'
    if ($SchemeName) {
        Set-ItemProperty -Path $CursorKey -Name "(Default)" -Value $SchemeName
        # Broadcast WM_SETTINGCHANGE for cursors
        rundll32.exe user32.dll, UpdatePerUserSystemParameters
    }
}

# --- Restart Explorer to apply layout / taskbar changes ----------------------

Write-Host ""
$Restart = Read-Host "Restart Explorer now to apply taskbar/Start layout changes? [Y/n]"
if ($Restart -ne 'n' -and $Restart -ne 'N') {
    Write-Host "Restarting Explorer..."
    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Process explorer
}

Write-Host ""
Write-Host "Import complete."
Write-Host "For full effect, log off and back on (or reboot)."
if (-not $IsAdmin) {
    Write-Host ""
    Write-Host "Some settings were skipped because this session is not elevated."
    Write-Host "Re-run as Administrator to also restore:"
    Write-Host "  - Default app associations (DISM)"
    Write-Host "  - Time zone"
}
