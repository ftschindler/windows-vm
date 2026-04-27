# Export Windows 11 User Settings
# Captures: appearance, taskbar, Start, Explorer, themes, DWM, wallpaper,
#           fonts, cursors, sounds, keyboard/language, regional, privacy,
#           notifications, accessibility, visual effects, power plan,
#           default app associations, and Start/taskbar layout.
#
# Output folder: <script dir>\Win11AppearanceExport
# Run as the target user (no elevation required except where noted).

$ExportPath = "$PSScriptRoot\Win11AppearanceExport"
New-Item -ItemType Directory -Force -Path $ExportPath | Out-Null

function Export-RegKey {
    param([string]$Key)
    $SafeName = $Key.Replace('\', '_').Replace(':', '').Replace(' ', '_')
    $OutFile   = "$ExportPath\reg\$SafeName.reg"
    New-Item -ItemType Directory -Force -Path "$ExportPath\reg" | Out-Null
    reg export $Key $OutFile /y 2>&1 | Out-Null
}

# --- Registry keys -----------------------------------------------------------

$RegKeys = @(
    # Taskbar (Win11 alignment, widgets, chat, badges, grouping)
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Taskband",

    # Start Menu
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartPage",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartPage2",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Start",

    # Explorer view / behavior
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\CabinetState",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons\NewStartPanel",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Streams",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StreamsMRU",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",

    # Theme & Personalization
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent",

    # DWM / window chrome / accent color
    "HKCU\Software\Microsoft\Windows\DWM",

    # Desktop / visual effects
    "HKCU\Control Panel\Desktop",
    "HKCU\Control Panel\Colors",

    # Search box style
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Search",

    # Wallpaper history (Win11)
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Wallpapers",

    # Mouse / cursor
    "HKCU\Control Panel\Cursors",
    "HKCU\Control Panel\Mouse",

    # Sounds
    "HKCU\AppEvents\Schemes",
    "HKCU\Control Panel\Sound",

    # Keyboard / input
    "HKCU\Keyboard Layout\Preload",
    "HKCU\Keyboard Layout\Substitutes",
    "HKCU\Control Panel\Keyboard",

    # Regional / locale
    "HKCU\Control Panel\International",

    # Privacy / capability consent
    "HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
    "HKCU\Software\Microsoft\Personalization\Settings",
    "HKCU\Software\Microsoft\InputPersonalization",

    # Notifications
    "HKCU\Software\Microsoft\Windows\CurrentVersion\PushNotifications",
    "HKCU\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings",

    # Accessibility
    "HKCU\Control Panel\Accessibility",
    "HKCU\Software\Microsoft\Narrator",

    # User-scope font registrations (Win11 / 1809+)
    "HKCU\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
)

Write-Host "Exporting registry keys..."
foreach ($Key in $RegKeys) {
    Export-RegKey $Key
}

# --- Wallpaper ---------------------------------------------------------------

Write-Host "Saving wallpaper..."
New-Item -ItemType Directory -Force -Path "$ExportPath\wallpaper" | Out-Null

try {
    $WallpaperPath = (Get-ItemProperty "HKCU:\Control Panel\Desktop" -Name Wallpaper -ErrorAction Stop).Wallpaper
    Set-Content -Path "$ExportPath\wallpaper\wallpaper_path.txt" -Value $WallpaperPath

    # Copy the actual image file so it survives reprovisioning
    if ($WallpaperPath -and (Test-Path $WallpaperPath)) {
        Copy-Item -Path $WallpaperPath -Destination "$ExportPath\wallpaper\" -Force
    } else {
        # Fall back to the transcoded cache (always present)
        $Transcoded = "$env:APPDATA\Microsoft\Windows\Themes\TranscodedWallpaper"
        if (Test-Path $Transcoded) {
            Copy-Item -Path $Transcoded -Destination "$ExportPath\wallpaper\TranscodedWallpaper.jpg" -Force
        }
    }

    # WallpaperStyle and TileWallpaper are captured via the Control Panel\Desktop reg export above.
} catch {
    Write-Warning "Could not save wallpaper: $_"
}

# --- Theme file --------------------------------------------------------------

Write-Host "Saving theme..."
New-Item -ItemType Directory -Force -Path "$ExportPath\theme" | Out-Null

try {
    $ThemePath = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes" -Name CurrentTheme -ErrorAction Stop).CurrentTheme
    if (Test-Path $ThemePath) {
        # Always save as a fixed filename to avoid Windows creating "(2)" duplicates on re-import.
        Copy-Item -Path $ThemePath -Destination "$ExportPath\theme\exported.theme" -Force
    }
} catch {
    Write-Warning "Could not save theme file: $_"
}

# --- Accent color (Win11: AccentColor is the user-chosen value) --------------

Write-Host "Saving accent color..."
try {
    $DwmProps = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\DWM" -ErrorAction Stop
    $Info = [ordered]@{
        AccentColor          = $DwmProps.AccentColor
        AccentColorInactive  = $DwmProps.AccentColorInactive
        ColorizationColor    = $DwmProps.ColorizationColor
        ColorPrevalence      = $DwmProps.ColorPrevalence
    }
    $Info | ConvertTo-Json | Set-Content -Path "$ExportPath\accent_color.json"
} catch {
    Write-Warning "Could not save accent color: $_"
}

# --- Start / Taskbar layout (Win11 JSON) -------------------------------------

Write-Host "Saving Start/Taskbar layout..."
New-Item -ItemType Directory -Force -Path "$ExportPath\layout" | Out-Null

# Win11 layout JSON file (written by the shell on save)
$LayoutJson = "$env:LOCALAPPDATA\Microsoft\Windows\Shell\LayoutModification.json"
if (Test-Path $LayoutJson) {
    Copy-Item $LayoutJson -Destination "$ExportPath\layout\" -Force
}

# Export-StartLayout may still produce useful XML on some Win11 builds
try {
    Export-StartLayout -Path "$ExportPath\layout\StartLayout.xml" -ErrorAction Stop
} catch {
    Write-Warning "Export-StartLayout not available on this build (expected on Win11 23H2+): $_"
}

# --- Keyboard / Language list ------------------------------------------------

Write-Host "Saving language/keyboard settings..."
New-Item -ItemType Directory -Force -Path "$ExportPath\locale" | Out-Null

try {
    Get-WinUserLanguageList | ConvertTo-Json -Depth 5 |
        Set-Content -Path "$ExportPath\locale\language_list.json"
} catch {
    Write-Warning "Get-WinUserLanguageList failed: $_"
}

try {
    [PSCustomObject]@{
        SystemLocale    = (Get-WinSystemLocale).Name
        UILanguage      = (Get-WinUILanguageOverride).Name
        HomeLocation    = (Get-WinHomeLocation).GeoId
        TimeZone        = (Get-TimeZone).Id
    } | ConvertTo-Json | Set-Content -Path "$ExportPath\locale\locale_settings.json"
} catch {
    Write-Warning "Could not save one or more locale settings: $_"
}

# --- Default app associations ------------------------------------------------

Write-Host "Saving default app associations..."
New-Item -ItemType Directory -Force -Path "$ExportPath\appassoc" | Out-Null

try {
    # Note: on some Win11 builds DISM export requires elevation (error 740).
    # If this fails, re-run the dump as Administrator to capture app associations.
    $AssocFile = "$ExportPath\appassoc\DefaultAppAssociations.xml"
    $result = & dism.exe /Online /Export-DefaultAppAssociations:"$AssocFile" 2>&1
    if ($LASTEXITCODE -eq 740) {
        Write-Warning "DISM export requires elevation on this build - re-run as Administrator to capture app associations."
    } elseif ($LASTEXITCODE -ne 0) {
        Write-Warning "DISM export returned $LASTEXITCODE`: $result"
    }
} catch {
    Write-Warning "Could not export default app associations: $_"
}

# --- Power plan --------------------------------------------------------------

Write-Host "Saving power plan..."
New-Item -ItemType Directory -Force -Path "$ExportPath\power" | Out-Null

try {
    $ActiveScheme = & powercfg /getactivescheme
    # Extract GUID (format: "Power Scheme GUID: xxxxxxxx-... (Name)")
    if ($ActiveScheme -match '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})') {
        $PlanGuid = $Matches[1]
        & powercfg /export "$ExportPath\power\ActivePowerPlan.pow" $PlanGuid 2>&1 | Out-Null
        Set-Content -Path "$ExportPath\power\active_plan_guid.txt" -Value $PlanGuid
    }
} catch {
    Write-Warning "Could not save power plan: $_"
}

# --- User-installed fonts (Win11 / 1809+) ------------------------------------

Write-Host "Saving user-installed fonts..."
$UserFontDir = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
if (Test-Path $UserFontDir) {
    $FontFiles = Get-ChildItem $UserFontDir -File
    if ($FontFiles.Count -gt 0) {
        $FontDest = "$ExportPath\fonts"
        New-Item -ItemType Directory -Force -Path $FontDest | Out-Null
        Copy-Item -Path "$UserFontDir\*" -Destination $FontDest -Recurse -Force
        Write-Host "  Copied $($FontFiles.Count) font file(s)."
    } else {
        Write-Host "  No user-installed fonts found (directory exists but is empty)."
    }
} else {
    Write-Host "  No user-installed fonts found."
}

# --- User Start Menu shortcuts (.lnk) ----------------------------------------

Write-Host "Saving user Start Menu shortcuts..."
$StartMenuSrc  = "$env:APPDATA\Microsoft\Windows\Start Menu"
$StartMenuDest = "$ExportPath\startmenu"
if (Test-Path $StartMenuSrc) {
    Copy-Item -Path $StartMenuSrc -Destination $StartMenuDest -Recurse -Force
}

# --- Custom cursor files -----------------------------------------------------

Write-Host "Saving cursor scheme files..."
New-Item -ItemType Directory -Force -Path "$ExportPath\cursors" | Out-Null

try {
    $CursorKey  = "HKCU:\Control Panel\Cursors"
    $CursorProps = Get-ItemProperty $CursorKey -ErrorAction Stop
    $CursorProps.PSObject.Properties |
        Where-Object { $_.Value -and $_.Value -match '\.(cur|ani)$' } |
        ForEach-Object {
            $SrcPath = [System.Environment]::ExpandEnvironmentVariables($_.Value)
            if (Test-Path $SrcPath) {
                Copy-Item -Path $SrcPath -Destination "$ExportPath\cursors\" -Force -ErrorAction SilentlyContinue
            }
        }
} catch {
    Write-Warning "Could not save cursor files: $_"
}

# Lock screen: captured via CapabilityAccessManager + ContentDeliveryManager
# in registry export above. Spotlight images are session-specific; not copied.

# --- Summary -----------------------------------------------------------------

$FileCount = (Get-ChildItem $ExportPath -Recurse -File).Count
Write-Host ""
Write-Host "Export complete. $FileCount files saved to: $ExportPath"
Write-Host ""
Write-Host "Subfolders:"
Get-ChildItem $ExportPath -Directory | ForEach-Object {
    $n = (Get-ChildItem $_.FullName -Recurse -File).Count
    Write-Host "  $($_.Name)  ($n files)"
}
