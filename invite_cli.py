"""Generate invite codes for InkForge beta testing.

Usage:
    python invite_cli.py --count 5             # 5 single-use codes, 30-day expiry
    python invite_cli.py --count 10 --uses 3   # 10 codes, 3 uses each
    python invite_cli.py --count 1 --days 90   # 1 code, 90 days
"""
import argparse
from novel_agent.user.db import Database


def main():
    p = argparse.ArgumentParser(description="Generate InkForge invite codes")
    p.add_argument("--count", "-c", type=int, default=10, help="Number of codes (default: 10)")
    p.add_argument("--uses",  "-u", type=int, default=1,  help="Max uses per code (default: 1)")
    p.add_argument("--days",  "-d", type=int, default=30, help="Expiry in days (default: 30, 0=never)")
    args = p.parse_args()

    db = Database()
    codes = db.generate_codes(count=args.count, max_uses=args.uses, days=args.days)

    print(f"\n  Generated {len(codes)} invite code(s) — {args.uses} use(s) each, "
          f"{args.days} day(s) expiry\n")
    for c in codes:
        print(f"    {c}")
    print()


if __name__ == "__main__":
    main()
