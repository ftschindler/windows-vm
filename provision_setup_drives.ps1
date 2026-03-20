$ErrorActionPreference = 'Stop'

Write-Host "=== Setting up drives ==="

# Step 1: Move DVD drive to Z: first (before initializing disk)
Write-Host ""
Write-Host "Step 1: Moving DVD drive to Z:..."
$dvd = Get-Volume | Where-Object { $_.DriveType -eq 'CD-ROM' } | Select-Object -First 1
if ($dvd -and $dvd.DriveLetter) {
    $currentLetter = $dvd.DriveLetter
    Write-Host "Current DVD drive letter: ${currentLetter}:"

    # Get the partition using CIM
    $cdrom = Get-CimInstance -ClassName Win32_Volume | Where-Object { $_.DriveLetter -eq "${currentLetter}:" }
    if ($cdrom) {
        Set-CimInstance -InputObject $cdrom -Property @{DriveLetter="Z:"}
        Write-Host "SUCCESS: DVD drive moved to Z:"
    }
} else {
    Write-Host "WARNING: No DVD drive found or no drive letter assigned"
}

# Step 2: Initialize and format the second disk as D:
Write-Host ""
Write-Host "Step 2: Setting up Dev Drive (Disk 1)..."
$disk = Get-Disk -Number 1 -ErrorAction SilentlyContinue

if (-not $disk) {
    Write-Host "ERROR: Disk 1 not found"
    exit 1
}

if ($disk.PartitionStyle -eq 'RAW') {
    Write-Host "Initializing Disk 1 as GPT..."
    Initialize-Disk -Number 1 -PartitionStyle GPT -PassThru | Out-Null

    Write-Host "Creating partition and formatting as NTFS..."
    $partition = New-Partition -DiskNumber 1 -UseMaximumSize -DriveLetter D
    Format-Volume -DriveLetter D -FileSystem NTFS -NewFileSystemLabel "DevDrive" -Confirm:$false | Out-Null

    Write-Host "SUCCESS: Dev Drive created and formatted as D:"
} else {
    Write-Host "Disk 1 already initialized as $($disk.PartitionStyle)"

    # Check if there's already a data partition with a drive letter
    $existingPartition = Get-Partition -DiskNumber 1 -ErrorAction SilentlyContinue |
        Where-Object { $_.DriveLetter -and $_.Type -eq 'Basic' } |
        Select-Object -First 1

    if ($existingPartition) {
        Write-Host "Dev Drive already has drive letter: $($existingPartition.DriveLetter):"
    } else {
        # Check if there's a partition without a drive letter that we can use
        $partition = Get-Partition -DiskNumber 1 -ErrorAction SilentlyContinue |
            Where-Object { -not $_.DriveLetter -and $_.Size -gt 100MB } |
            Select-Object -First 1

        if ($partition) {
            Write-Host "Found existing partition without drive letter, assigning D:..."
            Set-Partition -InputObject $partition -NewDriveLetter D
            Format-Volume -DriveLetter D -FileSystem NTFS -NewFileSystemLabel "DevDrive" -Confirm:$false | Out-Null
            Write-Host "SUCCESS: Dev Drive configured as D:"
        } else {
            # Create new partition
            Write-Host "Creating new partition..."
            $partition = New-Partition -DiskNumber 1 -UseMaximumSize -DriveLetter D
            Format-Volume -DriveLetter D -FileSystem NTFS -NewFileSystemLabel "DevDrive" -Confirm:$false | Out-Null
            Write-Host "SUCCESS: Dev Drive created as D:"
        }
    }
}

# Step 3: Verify configuration
Write-Host ""
Write-Host "Step 3: Verifying drive configuration..."
Get-Volume | Where-Object { $_.DriveLetter -in @('D', 'Z') } | Select-Object DriveLetter, FileSystemLabel, DriveType, Size | Format-Table -AutoSize

Write-Host ""
Write-Host "=== Drive setup complete ==="
