# Hetzner Cloud infrastructure for the PBX (docs/deploy.md §4).
#
# Terraform owns the VM lifecycle; NixOS itself is installed onto the VM
# with nixos-anywhere from this flake (the ubuntu image below is only a
# boot placeholder that gets completely wiped):
#
#   nix run github:numtide/nixos-anywhere -- \
#     --flake .#pbx-prod root@$(terraform -chdir=infra output -raw pbx_ipv4)
#
# DNS stays in the domains repo (custom-server module) — one home per
# fact: this repo owns the server, that repo owns the records.

terraform {
  required_version = ">= 1.0"

  required_providers {
    hcloud = {
      source = "hetznercloud/hcloud"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

variable "hcloud_token" {
  type        = string
  sensitive   = true
  description = "Project-scoped Hetzner Cloud API token (console: Security -> API Tokens)."
}

variable "ssh_public_keys" {
  type        = list(string)
  description = "Operator keys authorized while installing (the hardened sshd later only accepts the keys baked into hosts/pbx-prod)."
}

resource "hcloud_ssh_key" "operator" {
  for_each = toset(var.ssh_public_keys)

  name       = "pbx-${substr(md5(each.value), 0, 8)}"
  public_key = each.value
}

resource "hcloud_server" "pbx" {
  name        = "pbx"
  server_type = "cx22" # 2 vCPU / 4 GB — plenty for a small-org PBX
  image       = "ubuntu-24.04"
  location    = "fsn1" # Falkenstein
  ssh_keys    = [for k in hcloud_ssh_key.operator : k.id]

  # The NixOS config opens every telephony port itself
  # (modules/telephony/edge.nix), so no Hetzner Cloud Firewall is wired
  # here; add one later only if defense-in-depth at the hoster is wanted.
  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  labels = {
    project = "nix-international-telephony"
    role    = "pbx"
  }
}

output "pbx_ipv4" {
  description = "Public IPv4 — point pbx.artmann.tech at this (domains repo, custom-server module)."
  value       = hcloud_server.pbx.ipv4_address
}

output "pbx_ipv6" {
  description = "Public IPv6 (AAAA record)."
  value       = hcloud_server.pbx.ipv6_address
}
