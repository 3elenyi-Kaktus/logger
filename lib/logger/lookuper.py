import argparse
import re
from argparse import ArgumentParser
from pathlib import Path

if __name__ == "__main__":
    parser = ArgumentParser()
    parser = ArgumentParser(description=f"")
    parser.add_argument(
        "-p",
        "--path",
        required=True,
        help="Path to directory or file to examine",
        dest="path",
    )
    args: argparse.Namespace = parser.parse_args()
    print(f"Parsed args: {vars(args)}")
    path = Path(args.path)
    if not path.exists():
        raise RuntimeError(f"Path {path} does not exist")

    files: list[Path] = sorted(path.glob("**/*.py"))
    filenames = [x.name for x in files]
    print(f"Found {len(filenames)} files: {filenames}")

    max_filename_length = 0
    max_function_name_length = 0
    max_lines_count = 0
    max_log_string_length = 0
    for file in files:
        with open(file, "rt") as f:
            lines = f.readlines()
        logging_used: bool = False
        for line in lines:
            if "logging." in line:
                logging_used = True
                break
        if not logging_used:
            continue
        max_filename_length = max(max_filename_length, len(file.name))
        max_lines_count = max(max_lines_count, len(lines))
        for line in lines:
            if match := re.fullmatch(r".*?def (.+?)\(.*\n", line):
                max_function_name_length = max(len(match.group(1)), max_function_name_length)
                max_log_string_length = max(
                    max_log_string_length, len(f"{file.name}->{match.group(1)}({str(len(lines))})")
                )
    print(f"Max filename length: {max_filename_length}")
    print(f"Max function name length: {max_function_name_length}")
    print(f"Max lines count: {max_lines_count} -> {len(str(max_lines_count))}")
    print(f"Max log string length: {max_log_string_length}")
