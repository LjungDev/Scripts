import argparse
import subprocess
import os
import tempfile
from typing import Callable, List

is_verbose: bool = False

# Generic utilities


def print_verbose(msg: str) -> None:
    global is_verbose
    if is_verbose:
        print(msg)


def last_index(input: str, sep: str) -> str:
    try:
        return len(input) - "".join(reversed(input)).index(sep) - 1
    except:
        return -1


def find_entry_in_dir(start_dir: str, predicate: Callable[[os.DirEntry], bool]) -> str | None:
    entry_path: str = None
    dirs_to_check = [start_dir]

    while len(dirs_to_check) > 0 and not entry_path:
        dir = dirs_to_check.pop()

        with os.scandir(dir) as it:
            entries = [entry for entry in it if entry.name != ".git"]
            new_dirs = [entry for entry in entries if entry.is_dir()]
            dirs_to_check.extend([os.path.join(dir, subdir)
                                 for subdir in new_dirs])
            matches: List[os.DirEntry] = [
                entry for entry in entries if predicate(entry)]
            if len(matches) > 0:
                entry_path = os.path.join(dir, matches[0].name)

    return entry_path


def find_entry_in_dir_up(start_dir: str, predicate: Callable[[os.DirEntry], bool]) -> str | None:
    path = start_dir
    entry_path: str = None
    last_slash_index: int = 1

    while path and not entry_path and last_slash_index > 0:
        with os.scandir(path) as it:
            for entry in it:
                if predicate(entry):
                    entry_path = path
                    break
        last_slash_index = last_index(path, os.sep)
        path = path[0:last_slash_index]

    return entry_path


# Path finders

def find_git_root() -> str:
    path = os.getcwd()
    git_root = ""
    last_slash_index: int = 1

    while path and not git_root and last_slash_index > 0:
        with os.scandir(path) as it:
            for entry in it:
                if entry.name == ".git":
                    git_root = path
                    break
        last_slash_index = last_index(path, os.sep)
        path = path[0:last_slash_index]

    if not git_root:
        raise Exception("unable to find .git starting from %s" % os.getcwd())

    print_verbose("found .git in %s" % git_root)

    return git_root


def get_ue_bin_path() -> str:
    path = os.environ["UE_DIFF_BIN"] if "UE_DIFF_BIN" in os.environ else None

    if not path:
        raise Exception(
            "unable to find UE bin file to use for diff (set UE_DIFF_BIN environment variable to your 'UnrealEditor-Cmd.exe')")

    print_verbose("ue bin path is %s" % path)

    return path


def get_valid_asset_path(relative_asset_path: str) -> str:
    asset_path = os.path.abspath(
        os.path.join(os.getcwd(), relative_asset_path))

    if not os.path.isfile(asset_path):
        raise Exception(
            "asset path '%s' does not point to a valid asset" % asset_path)

    print_verbose("asset path is %s" % asset_path)

    return asset_path


def get_project_path(start_dir: str) -> str:
    def predicate(entry: os.DirEntry) -> bool:
        return entry.name.endswith(".uproject")

    path: str = None

    path = find_entry_in_dir(start_dir, predicate)

    if not path:
        path = find_entry_in_dir_up(start_dir, predicate)

    if not path:
        raise Exception(
            "unable to find .uproject starting from %s" % start_dir)

    print_verbose("found .uproject as %s" % path)

    return path


def get_asset_temp_path(asset_path: str, revision: str) -> str:
    tmp_dir = tempfile.mkdtemp()
    name_parts = os.path.splitext(asset_path)
    asset_base_name = os.path.basename(name_parts[0])
    new_name = "%s_%s%s" % (asset_base_name, revision, name_parts[1])
    new_path = os.path.join(tmp_dir, new_name)

    print_verbose("asset temp path is %s" % new_path)
    return new_path


# Command runners

def run_cmd(cwd: str, cmd_parts: List[str]) -> None:
    print_verbose("(running '%s' from %s)" % (" ".join(cmd_parts), cwd))
    subprocess.run(cmd_parts, cwd=cwd, check=True)


def run_cmd_capture(cwd: str, cmd_parts: List[str]) -> str:
    print_verbose("(running '%s' from %s)" % (" ".join(cmd_parts), cwd))
    result = subprocess.run(
        cmd_parts, capture_output=True, cwd=cwd, check=True, encoding="utf-8")
    return result.stdout


def run_cmd_capture_blob(cwd: str, cmd_parts: List[str]) -> bytes:
    print_verbose("(running '%s' from %s)" % (" ".join(cmd_parts), cwd))
    result = subprocess.run(
        cmd_parts, capture_output=True, cwd=cwd, check=True)
    return result.stdout


# Git operations


def get_git_relative_asset_path(git_root: str, asset_path: str) -> str:
    return os.path.relpath(asset_path, git_root).replace("\\", "/")


def git_find_last_revision(git_root: str, file_path: str) -> str:
    revision = run_cmd_capture(git_root, ["git", "log", "--format=%h", "-n",
                                          "1", file_path])

    revision = revision.strip()

    if not revision:
        raise Exception(
            "could not found previous revision for asset '%s'" % file_path)

    return revision


def git_download_asset_revision(git_root: str, asset_path: str, revision: str, tmp_path: str) -> None:
    git_asset_path = get_git_relative_asset_path(git_root, asset_path)
    raw_contents = run_cmd_capture_blob(
        git_root, ["git", "show", "%s:%s" % (revision, git_asset_path)])

    with open(tmp_path, "wb") as file:
        file.write(raw_contents)


def git_is_lfs(git_root: str, asset_path: str) -> bool:
    lfs_files_output = run_cmd_capture(git_root, ["git", "lfs", "ls-files"])
    lfs_files = [file[13:] for file in lfs_files_output.splitlines()]
    git_asset_path = get_git_relative_asset_path(git_root, asset_path)
    is_lfs = git_asset_path in lfs_files
    return is_lfs


# Diff operations

def create_diff_command_parts(ue_bin_path: str, project_path: str, asset_path: str, second_asset_path: str = None) -> str:
    args = [ue_bin_path, project_path, "-diff", asset_path]
    if second_asset_path:
        args.extend([second_asset_path])
    return args


def diff_lfs(git_root: str, asset_path: str, revision: str, ue_bin_path: str, project_path: str) -> None:
    git_asset_path = get_git_relative_asset_path(git_root, asset_path)
    lfs_envs_output = run_cmd_capture(git_root, ["git", "lfs", "env"])
    lfs_media_dir_matches = [line[14:] for line in lfs_envs_output.splitlines(
    ) if "LocalMediaDir=" in line]

    if len(lfs_media_dir_matches) == 0:
        raise Exception(
            "unable to find LocalMediaDir by lfs env output:\n%s" % lfs_envs_output)

    lfs_media_dir = lfs_media_dir_matches[0]
    print_verbose("lfs media dir is %s" % lfs_media_dir)

    oid_output = run_cmd_capture(
        git_root, ["git", "cat-file", "-p", "%s:%s" % (revision, git_asset_path)])
    asset_oid_matches = [line[11:]
                         for line in oid_output.splitlines() if "oid sha256:" in line]

    if len(asset_oid_matches) == 0:
        raise Exception(
            "unable to find asset oid from cat-file output:\n%s" % oid_output)

    asset_oid = asset_oid_matches[0]
    print_verbose("asset oid is %s" % asset_oid)

    left_asset_path = os.path.join(
        lfs_media_dir, asset_oid[0:2], asset_oid[2:4], asset_oid)
    print_verbose("left asset path is %s" % left_asset_path)

    if not os.path.isfile(left_asset_path):
        raise Exception("left asset path '%s' is not a valid file" %
                        left_asset_path)

    cmd_parts = create_diff_command_parts(
        ue_bin_path, project_path, left_asset_path, asset_path)
    run_cmd(git_root, cmd_parts)


def diff_normal(git_root: str, asset_path: str, revision: str, ue_bin_path: str, project_path: str) -> None:
    tmp_path = get_asset_temp_path(asset_path, revision)
    git_download_asset_revision(
        git_root, asset_path, revision, tmp_path)
    cmd_parts = create_diff_command_parts(
        ue_bin_path, project_path, tmp_path, asset_path)
    run_cmd(git_root, cmd_parts)
    os.unlink(tmp_path)

# Main


def main():
    global is_verbose
    parser = argparse.ArgumentParser(
        description="""
            Helper script to diff primarily .uasset files that 
            can't be diffed normally from the editor (for example 
            when using the Content dir as a separate repo/submodule).""")

    parser.add_argument(
        "asset", type=str, help="Path to asset.")
    parser.add_argument("--verbose", action='store_true',
                        help="Will output extra debug info if specified.")

    args = parser.parse_args()
    is_verbose = args.verbose

    relative_asset_path = args.asset

    git_root = find_git_root()
    asset_path = get_valid_asset_path(relative_asset_path)
    project_path = get_project_path(git_root)
    ue_bin_path = get_ue_bin_path()
    git_relative_asset_path = os.path.relpath(asset_path, git_root)
    revision = git_find_last_revision(git_root, git_relative_asset_path)

    is_lfs = git_is_lfs(git_root, asset_path)

    if is_lfs:
        diff_lfs(git_root, asset_path, revision, ue_bin_path, project_path)
    else:
        diff_normal(git_root, asset_path, revision, ue_bin_path, project_path)


if __name__ == '__main__':
    main()
