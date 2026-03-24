# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "gusztavvargadr/windows-11"
  config.vm.box_version = "2601.0.0"
  config.vm.boot_timeout = 600

  # Read credentials from environment variables
  admin_password = ENV['ADMIN_PASSWORD']
  user_password = ENV['USER_PASSWORD']

  # Determine which commands need credentials
  # Only require credentials for operations that actually need them
  vagrant_command = ARGV[0]
  needs_credentials = !['destroy', 'global-status', 'status', 'halt', 'suspend', 'resume', 'version', 'plugin', 'box'].include?(vagrant_command)

  # Validate credentials are set (only when needed)
  if needs_credentials
    if admin_password.nil? || admin_password.empty?
      abort "ERROR: ADMIN_PASSWORD environment variable not set. Run: bash ./generate-credentials.sh"
    end
    if user_password.nil? || user_password.empty?
      abort "ERROR: USER_PASSWORD environment variable not set. Run: bash ./generate-credentials.sh"
    end
  end

  # Check if we should use admin credentials (flag file exists on host)
  use_admin = File.exist?('synced/admin-ready')

  if use_admin
    puts "INFO: Using admin credentials (admin-ready flag detected)"
    config.winrm.username = "admin"
    config.winrm.password = admin_password || "unused"
  else
    puts "INFO: Using vagrant credentials (initial provisioning)"
    config.winrm.username = "vagrant"
    config.winrm.password = "vagrant"
  end

  # ============================================================================
  # Provider-specific configuration
  # ============================================================================

  # VirtualBox provider
  config.vm.provider "virtualbox" do |vb, override|
    # Create Dev Drive disk if it doesn't exist (only when VBoxManage is available)
    devdrive_disk = File.join(File.dirname(__FILE__), "devdrive.vdi")
    unless File.exist?(devdrive_disk)
      if system("which VBoxManage > /dev/null 2>&1")
        puts "Creating Dev Drive disk (500GB) for VirtualBox..."
        system("VBoxManage createhd --filename '#{devdrive_disk}' --size #{500 * 1024}")
      end
    end

    vb.gui = true
    vb.name = "windows-dev-throwaway"
    vb.memory = "8192"
    vb.cpus = 4

    # Attach Dev Drive disk to SATA port 1
    vb.customize ['storageattach', :id, '--storagectl', 'SATA Controller', '--port', 1, '--device', 0, '--type', 'hdd', '--medium', devdrive_disk]

    # Auto install guest additions (requires vagrant-vbguest plugin)
    if Vagrant.has_plugin?("vagrant-vbguest")
      override.vbguest.auto_update = true
    end

    # Use VirtualBox-native shared folders
    override.vm.synced_folder "./synced", "C:/vagrant", type: "virtualbox"
  end

  # Libvirt provider (for KVM/QEMU)
  config.vm.provider "libvirt" do |libvirt, override|
    libvirt.driver = "kvm"
    libvirt.memory = 8192
    libvirt.cpus = 4
    libvirt.machine_type = "pc-q35-6.2"
    libvirt.cpu_mode = "host-passthrough"
    libvirt.nic_model_type = "e1000"
    libvirt.graphics_type = "vnc"
    libvirt.graphics_ip = "127.0.0.1"
    libvirt.video_type = "qxl"

    # Create Dev Drive disk (500GB)
    libvirt.storage :file, size: '500G', type: 'qcow2', bus: 'sata', device: 'sdb'

    # Use rsync for synced folders (more reliable with Windows on libvirt)
    # Note: Requires rsync to be available in the Windows VM (installed via provisioning)
    override.vm.synced_folder "./synced", "C:/vagrant", type: "rsync",
      rsync__exclude: [".git/", "*.vdi", "*.qcow2"],
      rsync__args: ["--verbose", "--archive", "--delete", "-z"]
  end

  # Default synced folder if no provider-specific override
  # This is a fallback, but providers should define their own above
  config.vm.synced_folder "./synced", "C:/vagrant"

  # ============================================================================
  # Phase 1: Hardware and User Setup (runs as vagrant user)
  # ============================================================================

  config.vm.provision "setup-drives", type: "shell", run: "once" do |s|
    s.path = "provision_setup_drives.ps1"
    s.powershell_args = "-ExecutionPolicy Bypass"
  end

  config.vm.provision "create-admin", type: "shell", run: "once" do |s|
    s.path = "provision_create_admin.ps1"
    s.powershell_args = "-ExecutionPolicy Bypass"
    s.env = { "ADMIN_PASSWORD" => admin_password }
  end

  config.vm.provision "create-user", type: "shell", run: "once" do |s|
    s.path = "provision_create_user.ps1"
    s.powershell_args = "-ExecutionPolicy Bypass"
    s.env = { "USER_PASSWORD" => user_password }
  end

  config.vm.provision "prepare-admin-winrm", type: "shell", run: "once" do |s|
    s.path = "provision_prepare_admin_winrm.ps1"
    s.powershell_args = "-ExecutionPolicy Bypass"
    s.env = { "ADMIN_PASSWORD" => admin_password }
  end

  # ============================================================================
  # Phase 2: Development Tools (runs as vagrant user)
  # ============================================================================

  config.vm.provision "install-winget", type: "shell", run: "once" do |s|
    s.path = "provision_install_winget.ps1"
    s.powershell_args = "-ExecutionPolicy Bypass"
    s.env = { "GITHUB_TOKEN" => ENV['GITHUB_TOKEN'] }
  end

  # Reload after WinGet installation to ensure PATH is updated
  config.vm.provision :reload, run: "once"

  # Only run these in Phase 1/2 (before admin credentials are active)
  unless use_admin
    config.vm.provision "shell", name: "install-git", run: "once", inline: "winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }", powershell_args: "-ExecutionPolicy Bypass"

    config.vm.provision "install-tools", type: "shell", run: "once" do |s|
      s.path = "provision_install_tools.ps1"
      s.powershell_args = "-ExecutionPolicy Bypass"
    end

    config.vm.provision "install-vs-professional", type: "shell", run: "once" do |s|
      s.path = "provision_install_vs_professional.ps1"
      s.powershell_args = "-ExecutionPolicy Bypass"
    end
  end

  # ============================================================================
  # Phase 3: Finalization (runs as admin user after reload)
  # ============================================================================

  if use_admin
    config.vm.provision "setup-user-startup", type: "shell", run: "once" do |s|
      s.path = "provision_setup_user_startup.ps1"
      s.powershell_args = "-ExecutionPolicy Bypass"
    end

    config.vm.provision "finalize", type: "shell", run: "once" do |s|
      s.path = "provision_finalize.ps1"
      s.powershell_args = "-ExecutionPolicy Bypass"
      s.env = { "USER_PASSWORD" => user_password }
    end
  end

  # ============================================================================
  # Triggers
  # ============================================================================

  # Clean up host-side flags when VM is destroyed
  config.trigger.before :destroy do |t|
    t.info = "Cleaning up admin-ready flag"
    t.run = { inline: "rm -f synced/admin-ready .vagrant/admin-transitioned" }
  end
end
