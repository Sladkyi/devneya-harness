#!/usr/bin/env python3
"""Resolve published DSH/TUI versions and prepare an unpublishable candidate."""

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

from normalize_lock import normalize

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "https://registry.npmjs.org"
COMPONENTS = {
    "dsh": ("@deepseek-ai/dsh", "deepseek-ai/deepseek-harness", "dsh-v"),
    "tui": ("@deepseek-harness-tui/dsh-tui", "ccch1mneyyy/dsh-TUI", "v"),
}
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")
SHA = re.compile(r"[0-9a-f]{40}")


def version_key(version):
    match = VERSION.fullmatch(version)
    if not match:
        raise ValueError(f"Unsupported npm release version: {version!r}")
    major, minor, patch, prerelease = match.groups()
    identifiers = tuple(
        (0, int(value)) if value.isascii() and value.isdigit() else (1, value)
        for value in prerelease.split(".")
    ) if prerelease else ()
    return int(major), int(minor), int(patch), prerelease is None, identifiers


def npm_manifest(package, version):
    with urlopen(f"{REGISTRY}/{quote(package, safe='')}/{version}", timeout=30) as response:
        manifest = json.load(response)
    if manifest["name"] != package or (version != "latest" and manifest["version"] != version):
        raise ValueError(f"Registry returned a different package or release for {package}@{version}")
    version_key(manifest["version"])
    return manifest


def output_versions(config, pinned):
    result = {name: config[name] for name in COMPONENTS}
    if not pinned:
        for name, (package, _, _) in COMPONENTS.items():
            latest = npm_manifest(package, "latest")["version"]
            if version_key(latest) > version_key(result[name]):
                result[name] = latest
    changed = any(result[name] != config[name] for name in COMPONENTS)
    outputs = {**result, "build": str(changed or pinned).lower()}
    print(f"DSH {result['dsh']}, TUI {result['tui']} (pinned: DSH {config['dsh']}, TUI {config['tui']})")
    if path := os.environ.get("GITHUB_OUTPUT"):
        with Path(path).open("a", encoding="utf-8") as stream:
            for name, value in outputs.items():
                stream.write(f"{name}={value}\n")
    return outputs


def source_commit(repo, prefix, manifest):
    tag = "refs/tags/" + prefix + manifest["version"]
    result = subprocess.check_output(
        ["git", "ls-remote", "--exit-code", f"https://github.com/{repo}.git", tag, tag + "^{}"],
        encoding="utf-8", timeout=45,
    )
    refs = {ref: commit for commit, ref in (line.split() for line in result.splitlines())}
    commit = refs.get(tag + "^{}") or refs.get(tag)
    if not commit or not SHA.fullmatch(commit):
        raise ValueError(f"Missing source commit for {repo} {tag}")
    if manifest.get("gitHead") and manifest["gitHead"] != commit:
        raise ValueError(f"npm gitHead does not match the source tag for {repo} {tag}")
    return commit


def package_archive(manifest):
    dist = manifest["dist"]
    url = urlsplit(dist["tarball"])
    if url.scheme != "https" or url.netloc != "registry.npmjs.org":
        raise ValueError("Candidate tarball must come from the public npm registry")
    with urlopen(url.geturl(), timeout=45) as response:
        if urlsplit(response.geturl()).netloc != url.netloc:
            raise ValueError("Candidate tarball redirected off the npm registry")
        archive = response.read(128 * 1024 * 1024 + 1)
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode("ascii")
    if len(archive) > 128 * 1024 * 1024 or integrity != dist["integrity"]:
        raise ValueError(f"Cannot verify tarball for {manifest['name']}@{manifest['version']}")
    return tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz")


def check_patch_sources(patches, changed):
    mismatches = []
    for package, manifest in changed.items():
        rows = [row for row in patches if row["package"] == package]
        if not rows:
            continue
        with package_archive(manifest) as archive:
            for row in rows:
                path = "package/" + row["path"]
                try:
                    member = archive.getmember(path)
                except KeyError:
                    mismatches.append(f"{package}: {row['path']} is missing")
                    continue
                if not member.isfile():
                    mismatches.append(f"{package}: {row['path']} is no longer a regular file")
                    continue
                with archive.extractfile(member) as source:
                    fingerprint = hashlib.file_digest(source, "sha256").hexdigest()
                if fingerprint != row["sha256"]:
                    mismatches.append(f"{package}: {row['path']} changed")
                else:
                    row["version"] = manifest["version"]
    if mismatches:
        raise ValueError("Upstream files used by DH patches need review:\n- " + "\n- ".join(mismatches))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def prepare(config, versions):
    for component, version in versions.items():
        if version_key(version) < version_key(config[component]):
            raise ValueError(f"Refusing to downgrade {component}")
    if all(config[name] == versions[name] for name in COMPONENTS):
        return
    package_file = ROOT / "runtime/package.json"
    patch_file = ROOT / "patches/integration.json"
    runtime = json.loads(package_file.read_text(encoding="utf-8"))
    spec = json.loads(patch_file.read_text(encoding="utf-8"))
    changed = {}
    for name, (package, repo, prefix) in COMPONENTS.items():
        version = versions[name]
        if version == config[name]:
            continue
        manifest = npm_manifest(package, version)
        changed[package] = manifest
        config[name] = version
        config[name + "Source"] = source_commit(repo, prefix, manifest)
        for section in ("dependencies", "overrides"):
            for dependency in runtime[section]:
                if dependency == package or (name == "dsh" and dependency.startswith(package + "-")):
                    runtime[section][dependency] = version
        if name == "dsh":
            for row in spec["patches"]:
                patched_package = row["package"]
                if patched_package.startswith(package + "-") and patched_package not in changed:
                    changed[patched_package] = npm_manifest(patched_package, version)
    check_patch_sources(spec["patches"], changed)

    if subprocess.check_output(["npm", "--version"], text=True).strip() != config["npm"]:
        raise ValueError(f"Candidate lockfile must use npm {config['npm']}")
    write_json(ROOT / "build.json", config)
    write_json(package_file, runtime)
    write_json(patch_file, spec)
    env = {key: value for key, value in os.environ.items() if not key.lower().startswith("npm_config_")}
    env.update(
        npm_config_userconfig=str(ROOT / "runtime/builder.npmrc"),
        npm_config_globalconfig=str(ROOT / "runtime/global.npmrc"),
    )
    subprocess.run(
        ["npm", "install", "--package-lock-only", "--ignore-scripts", "--strict-peer-deps",
         "--include=optional", "--no-audit", "--no-fund"],
        cwd=ROOT / "runtime", env=env, check=True, timeout=600,
    )
    normalize(ROOT / "runtime/package-lock.json", config["tui"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("probe")
    probe.add_argument("--pinned", action="store_true")
    candidate = commands.add_parser("prepare")
    candidate.add_argument("--dsh", required=True)
    candidate.add_argument("--tui", required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "build.json").read_text(encoding="utf-8"))
    if args.command == "probe":
        output_versions(config, args.pinned)
    else:
        prepare(config, {"dsh": args.dsh, "tui": args.tui})


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
