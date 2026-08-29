# NixOS VM test for the hardened SSH server integration (the
# nix-ssh-config input wired into the example host in flake.nix):
#   * sshd comes up alongside the telephony stack with the hardened
#     effective config (key-only auth, no root login, post-quantum
#     KexAlgorithms first, AEAD ciphers, banner, forwarding off)
#   * a real key-based login works and negotiates mlkem768x25519-sha256
#   * password auth is not offered by the server; root login is refused
#     even with a valid user key
#
# The module under test is passed in by flake.nix so this file stays a
# plain (input-free) NixOS test module like the other suites.
{ sshServerModule }:
let
  common = import ./common.nix;
in
{
  name = "telephony-ssh";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode ++ [
        sshServerModule
        {
          # sshd -T (effective-config dump) is not on the default PATH.
          environment.systemPackages = [ pkgs.openssh ];
          users.users.testuser.isNormalUser = true;
          users.groups.testuser = { };
          services.ssh-server = {
            enable = true;
            # Keys-only is the module default since upstream v0.1.2
            # (kbdInteractiveAuthentication follows passwordAuthentication).
          };
        }
      ];
    };

  testScript = ''
    ${common.bootWait}

    machine.wait_for_unit("sshd.service")
    machine.succeed("ss -ltn 'sport = :22' | grep -q ':22'")

    # --- Effective config: the hardening actually reached sshd ---
    # (sshd -T prints canonical directive casing; compare case-insensitively)
    effective = machine.succeed(
        "sshd -T -C user=testuser,host=machine,addr=127.0.0.1"
    ).lower()
    assert "passwordauthentication no" in effective, effective
    assert "permitrootlogin no" in effective, effective
    assert "pubkeyauthentication yes" in effective, effective
    # Post-quantum ML-KEM hybrid first, AEAD-only ciphers, ETM-only MACs.
    assert "kexalgorithms mlkem768x25519-sha256," in effective, effective
    assert "ciphers chacha20-poly1305@openssh.com," in effective, effective
    assert "macs hmac-sha2-512-etm@openssh.com," in effective, effective
    assert "x11forwarding no" in effective, effective
    assert "allowtcpforwarding no" in effective, effective
    assert "maxauthtries 3" in effective, effective
    assert "banner /etc/ssh/banner" in effective, effective
    # Keys-only must close the PAM password door too, not just the
    # password method: keyboard-interactive prompts accept Unix account
    # passwords whenever a user has one.
    assert "kbdinteractiveauthentication no" in effective, effective
    machine.succeed("test -s /etc/ssh/banner")

    # --- Behavioural: key-based login negotiates the PQ kex ---
    machine.succeed("install -d -m 700 -o testuser -g testuser /home/testuser/.ssh")
    machine.succeed(
        "ssh-keygen -t ed25519 -N \"\" -f /home/testuser/.ssh/id_ed25519 -C ssh-test"
    )
    machine.succeed(
        "cat /home/testuser/.ssh/id_ed25519.pub >> /home/testuser/.ssh/authorized_keys"
        " && chown -R testuser:testuser /home/testuser/.ssh"
        " && chmod 600 /home/testuser/.ssh/authorized_keys"
    )
    login = machine.succeed(
        "runuser -u testuser -- ssh -vv -i /home/testuser/.ssh/id_ed25519"
        " -o UserKnownHostsFile=/home/testuser/.ssh/known_hosts"
        " -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
        " testuser@127.0.0.1 whoami 2>&1"
    )
    assert "testuser" in login, login
    assert "kex: algorithm: mlkem768x25519-sha256" in login, login

    # --- Denial paths: passwords not offered (publickey is the ONLY
    # server-offered method), root refused even with a valid user key ---
    pw_status, pw_out = machine.execute(
        "runuser -u testuser -- ssh -o BatchMode=yes"
        " -o PubkeyAuthentication=no"
        " -o PreferredAuthentications=password,keyboard-interactive"
        " -o UserKnownHostsFile=/home/testuser/.ssh/known_hosts"
        " -o StrictHostKeyChecking=accept-new"
        " testuser@127.0.0.1 true 2>&1"
    )
    assert pw_status != 0, pw_out
    assert "Permission denied (publickey)" in pw_out, pw_out

    root_status, root_out = machine.execute(
        "runuser -u testuser -- ssh -o BatchMode=yes"
        " -i /home/testuser/.ssh/id_ed25519"
        " -o UserKnownHostsFile=/home/testuser/.ssh/known_hosts"
        " -o StrictHostKeyChecking=accept-new"
        " root@127.0.0.1 true 2>&1"
    )
    assert root_status != 0, root_out
    assert "Permission denied" in root_out, root_out

    # The telephony stack still boots next to sshd (shared firewall etc.).
    wait_for_freeswitch(machine, "test-es-4d5e6f")
  '';
}
