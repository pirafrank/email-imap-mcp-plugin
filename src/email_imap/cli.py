from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .config import ConfigError, load_config
from .core import EmailClient

def _parser():
    p = argparse.ArgumentParser(prog="email-imap", description="Safe IMAP/SMTP mailbox tools")
    sub = p.add_subparsers(dest="command", required=True)
    def common(q):
        q.add_argument("--config", help="TOML configuration path"); q.add_argument("--account"); q.add_argument("--json", action="store_true")
    q = sub.add_parser("accounts"); q.add_argument("--config", help="TOML configuration path"); q.add_argument("--json", action="store_true")
    q = sub.add_parser("check"); common(q)
    q = sub.add_parser("folders"); common(q)
    q = sub.add_parser("search"); common(q); q.add_argument("--folder", default="INBOX"); q.add_argument("--from", dest="from_address", default=""); q.add_argument("--to", dest="to_address", default=""); q.add_argument("--subject", default=""); q.add_argument("--text", default=""); q.add_argument("--since", default=""); q.add_argument("--before", default=""); q.add_argument("--unread", action="store_true"); q.add_argument("--max-results", type=int, default=10)
    q = sub.add_parser("read"); common(q); q.add_argument("uid"); q.add_argument("--folder", default="INBOX")
    q = sub.add_parser("download"); common(q); q.add_argument("uid"); q.add_argument("filename"); q.add_argument("--folder", default="INBOX")
    q = sub.add_parser("send"); common(q); q.add_argument("--to", required=True); q.add_argument("--subject", default=""); q.add_argument("--body", required=True); q.add_argument("--cc", default=""); q.add_argument("--bcc", default=""); q.add_argument("--reply-to", dest="reply_to_uid", default=""); q.add_argument("--folder", default="INBOX"); q.add_argument("--attach", action="append", default=[]); q.add_argument("--yes", action="store_true")
    return p

def _print(result, as_json):
    if as_json: print(json.dumps(result, ensure_ascii=False))
    elif result.get("error"): print(f"error: {result['error']}", file=sys.stderr)
    elif "folders" in result: print("\n".join(f"{x['name']}" + (f" ({x['messages']})" if "messages" in x else "") for x in result["folders"]))
    elif "messages" in result:
        for m in result["messages"]: print(f"{m['uid']}  {m['date']}  {m['from']}  {m['subject']}")
        print(f"{result['total_matches']} match(es)")
    elif "body" in result: print(f"From: {result['from']}\nTo: {result['to']}\nSubject: {result['subject']}\n\n{result['body']}")
    else: print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get("error") else 0

def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "accounts":
            result = {"ok": True, "default": config.default_account, "accounts": [{"name": a.name, "address": a.address, "display_name": a.display_name} for a in config.accounts.values()]}
        elif args.command == "send":
            if not args.yes:
                print("refusing to send without --yes (explicit confirmation required)", file=sys.stderr); return 2
            result = EmailClient(config).send(args.to, args.subject, args.body, args.account, args.cc, args.bcc, args.reply_to_uid, args.folder, args.attach)
        else:
            client = EmailClient(config)
            if args.command == "check": result = client.check(args.account)
            elif args.command == "folders": result = client.folders(args.account)
            elif args.command == "search": result = client.search(args.account, args.folder, args.max_results, from_address=args.from_address, to_address=args.to_address, subject=args.subject, text=args.text, since=args.since, before=args.before, unread_only=args.unread)
            elif args.command == "read": result = client.read(args.uid, args.account, args.folder)
            else: result = client.download(args.uid, args.filename, args.account, args.folder)
        return _print(result, getattr(args, "json", False))
    except (ConfigError, OSError, RuntimeError, ValueError) as exc:
        if getattr(args, "json", False): print(json.dumps({"error": str(exc)}))
        else: print(f"error: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())
