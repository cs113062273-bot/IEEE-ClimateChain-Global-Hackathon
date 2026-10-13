"""Bounded tracked-file scan; never print matched credential values.

This catches common plaintext credential formats, not every possible secret.
"""
from __future__ import annotations
import argparse,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    "private-key-pem":r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "github-token":r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}",
    "aws-access-id":r"\bAKIA[A-Z0-9]{16}\b",
    "private-key-assignment":r"(?i)(?:private.?key)\s*[=:]\s*[\"']?(?:0x)?[0-9a-f]{64}\b",
}

def scan():
    files=subprocess.check_output(["git","ls-files","-z","--cached","--others","--exclude-standard"],cwd=ROOT).decode().split("\0")
    findings=[];checked=0
    for relative in sorted(set(files)):
        path=ROOT/relative
        if not path.is_file() or path.stat().st_size>16_000_000:continue
        try:body=path.read_text(encoding="utf-8")
        except (UnicodeError,OSError):continue
        checked+=1
        for label,pattern in PATTERNS.items():
            if re.search(pattern,body):findings.append({"path":relative,"pattern":label})
    return {"status":"passed" if not findings else "failed","checked_text_files":checked,"findings":findings,"scope":"tracked and nonignored untracked files; bounded common formats, no credential values printed"}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output");args=parser.parse_args();report=scan()
    if args.output:Path(args.output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2));raise SystemExit(0 if report["status"]=="passed" else 1)

if __name__=="__main__":main()
