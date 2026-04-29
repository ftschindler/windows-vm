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

  # Create Dev Drive disk if it doesn't exist. An existing devdrive.vdi is
  # preserved across vagrant destroy cycles (see triggers below), so this
  # only runs on first-time setup or after manually deleting the file.
  devdrive_disk = File.join(File.dirname(__FILE__), "devdrive.vdi")
  unless File.exist?(devdrive_disk)
    puts "Creating Dev Drive disk (500GB)..."
    system("VBoxManage createhd --filename '#{devdrive_disk}' --size #{500 * 1024}")
  end

  # VirtualBox provider settings
  config.vm.provider "virtualbox" do |vb|
    vb.gui = true
    vb.name = "Windows Development Environment"
    vb.memory = "8192"
    vb.cpus = 4

    # Attach Dev Drive disk to SATA port 1
    # Note: Using --nonrotational for SSD optimization
    vb.customize ['storageattach', :id, '--storagectl', 'SATA Controller', '--port', 1, '--device', 0, '--type', 'hdd', '--medium', devdrive_disk, '--nonrotational', 'on']
  end

  # Auto install guest additions
  config.vbguest.auto_update = true

  # Synced folder for provisioning scripts
  config.vm.synced_folder "./synced", "C:/vagrant", type: "virtualbox"

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
    config.vm.provision "install-tools", type: "shell", run: "once" do |s|
      s.path = "provision_install_tools.ps1"
      s.powershell_args = "-ExecutionPolicy Bypass"
    end

    config.vm.provision "uninstall-bloatware", type: "shell", run: "once" do |s|
      s.path = "provision_uninstall_bloat.ps1"
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
    config.vm.provision "configure-uac", type: "shell", run: "once" do |s|
      s.path = "provision_configure_uac.ps1"
      s.powershell_args = "-ExecutionPolicy Bypass"
    end

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

  # Preserve devdrive across VM destroy.
  #
  # Problem: vagrant destroy calls "VBoxManage unregistervm --delete" which
  # deletes all attached disk files. Detaching the medium beforehand doesn't
  # reliably work (hot-unplug fails while the VM is still running).
  #
  # Solution: move the .vdi to a temporary name before destroy (instant rename
  # on the same filesystem), then move it back afterwards. VirtualBox can't
  # delete a file that no longer exists at the expected path.
  config.trigger.before :destroy do |t|
    t.info = "Preserving Dev Drive data"
    devdrive_disk = File.join(File.dirname(__FILE__), "devdrive.vdi")
    devdrive_persist = devdrive_disk + ".persist"
    t.run = { inline: "bash -c '\n" \
      "VBoxManage storageattach \"Windows Development Environment\" --storagectl \"SATA Controller\" --port 1 --device 0 --medium none 2>&1 || true\n" \
      "VBoxManage closemedium disk \"#{devdrive_disk}\" 2>&1 || true\n" \
      "if [ -f \"#{devdrive_disk}\" ]; then mv \"#{devdrive_disk}\" \"#{devdrive_persist}\" && echo \"Dev Drive moved to safe location\"; fi\n" \
      "'" }
  end

  config.trigger.after :destroy do |t|
    t.info = "Restoring Dev Drive"
    devdrive_disk = File.join(File.dirname(__FILE__), "devdrive.vdi")
    devdrive_persist = devdrive_disk + ".persist"
    t.run = { inline: "bash -c '\n" \
      "if [ -f \"#{devdrive_persist}\" ]; then mv \"#{devdrive_persist}\" \"#{devdrive_disk}\" && echo \"Dev Drive restored\"; fi\n" \
      "rm -f synced/admin-ready .vagrant/admin-transitioned\n" \
      "'" }
  end
end
