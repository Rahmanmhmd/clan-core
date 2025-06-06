import argparse
import ipaddress
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clan_cli.async_run import AsyncRuntime
from clan_cli.cmd import run
from clan_cli.completions import (
    add_dynamic_completer,
    complete_machines,
)
from clan_cli.errors import ClanError
from clan_cli.machines.machines import Machine
from clan_cli.nix import nix_shell
from clan_cli.ssh.host import Host, is_ssh_reachable
from clan_cli.ssh.host_key import HostKeyCheck
from clan_cli.ssh.parse import parse_deployment_address
from clan_cli.ssh.tor import TorTarget, spawn_tor, ssh_tor_reachable

log = logging.getLogger(__name__)


@dataclass
class DeployInfo:
    addrs: list[str]
    tor: str | None = None
    pwd: str | None = None

    @staticmethod
    def from_hostname(hostname: str, args: argparse.Namespace) -> "DeployInfo":
        m = Machine(hostname, flake=args.flake)
        return DeployInfo(addrs=[m.target_host_address])

    @staticmethod
    def from_json(data: dict[str, Any]) -> "DeployInfo":
        return DeployInfo(
            tor=data.get("tor"), pwd=data.get("pass"), addrs=data.get("addrs", [])
        )


def is_ipv6(ip: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address)
    except ValueError:
        return False


def find_reachable_host(
    deploy_info: DeployInfo, host_key_check: HostKeyCheck
) -> Host | None:
    host = None
    for addr in deploy_info.addrs:
        host_addr = f"[{addr}]" if is_ipv6(addr) else addr
        host_ = parse_deployment_address(
            machine_name="uknown", host=host_addr, host_key_check=host_key_check
        )
        if is_ssh_reachable(host_):
            host = host_
            break

    return host


def qrcode_scan(picture_file: Path) -> str:
    cmd = nix_shell(
        ["zbar"],
        [
            "zbarimg",
            "--quiet",
            "--raw",
            str(picture_file),
        ],
    )
    res = run(cmd)
    return res.stdout.strip()


def parse_qr_code(picture_file: Path) -> DeployInfo:
    data = qrcode_scan(picture_file)
    return DeployInfo.from_json(json.loads(data))


def ssh_shell_from_deploy(
    deploy_info: DeployInfo, runtime: AsyncRuntime, host_key_check: HostKeyCheck
) -> None:
    if host := find_reachable_host(deploy_info, host_key_check):
        host.interactive_ssh()
    else:
        log.info("Could not reach host via clearnet 'addrs'")
        log.info(f"Trying to reach host via tor '{deploy_info.tor}'")
        spawn_tor(runtime)
        if not deploy_info.tor:
            msg = "No tor address provided, please provide a tor address."
            raise ClanError(msg)
        if ssh_tor_reachable(TorTarget(onion=deploy_info.tor, port=22)):
            host = Host(host=deploy_info.tor, password=deploy_info.pwd, tor_socks=True)
        else:
            msg = "Could not reach host via tor either."
            raise ClanError(msg)


def ssh_command_parse(args: argparse.Namespace) -> DeployInfo | None:
    if args.json:
        json_file = Path(args.json)
        if json_file.is_file():
            data = json.loads(json_file.read_text())
            return DeployInfo.from_json(data)
        data = json.loads(args.json)
        return DeployInfo.from_json(data)
    if args.png:
        return parse_qr_code(Path(args.png))
    if hasattr(args, "machines"):
        return DeployInfo.from_hostname(args.machines[0], args)
    return None


def ssh_command(args: argparse.Namespace) -> None:
    host_key_check = HostKeyCheck.from_str(args.host_key_check)
    deploy_info = ssh_command_parse(args)
    if not deploy_info:
        msg = "No MACHINE, --json or --png data provided"
        raise ClanError(msg)

    with AsyncRuntime() as runtime:
        ssh_shell_from_deploy(deploy_info, runtime, host_key_check)


def register_parser(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    machines_parser = group.add_argument(
        "machines",
        type=str,
        nargs="*",
        default=[],
        metavar="MACHINE",
        help="Machine to ssh into.",
    )
    add_dynamic_completer(machines_parser, complete_machines)

    group.add_argument(
        "-j",
        "--json",
        help="specify the json file for ssh data (generated by starting the clan installer)",
    )
    group.add_argument(
        "-P",
        "--png",
        help="specify the json file for ssh data as the qrcode image (generated by starting the clan installer)",
    )
    parser.add_argument(
        "--ssh_args", nargs=argparse.REMAINDER, help="additional ssh arguments"
    )
    parser.add_argument(
        "--host-key-check",
        choices=["strict", "ask", "tofu", "none"],
        default="ask",
        help="Host key (.ssh/known_hosts) check mode.",
    )
    parser.set_defaults(func=ssh_command)
