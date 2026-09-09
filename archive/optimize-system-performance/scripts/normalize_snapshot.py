#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize(data):
    data.setdefault("schema_version", 2)
    data.setdefault("platform", "unknown")
    data.setdefault("system", {})
    data.setdefault("cpu", {})
    data.setdefault("memory", {})
    data.setdefault("disk", {})
    data.setdefault("network", {})
    data.setdefault("listeners", {})
    data.setdefault("startup", {})
    processes = data.setdefault("processes", {})
    processes["top_cpu"] = ensure_list(processes.get("top_cpu") or data.get("top_cpu"))
    processes["top_memory"] = ensure_list(processes.get("top_memory") or data.get("top_memory"))
    processes["key_processes"] = ensure_list(processes.get("key_processes"))
    processes["all_sample"] = ensure_list(processes.get("all_sample"))
    return data


def main():
    parser = argparse.ArgumentParser(description="Normalize a performance snapshot summary JSON.")
    parser.add_argument("summary_json")
    parser.add_argument("--out", help="Optional output path. Defaults to stdout only.")
    args = parser.parse_args()

    data = normalize(load_json(args.summary_json))
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(out)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
