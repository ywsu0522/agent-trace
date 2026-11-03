"""HW1 P04: 12 original deterministic cases, no live inference."""

from scripts._deterministic import main as run_deterministic


def main(argv=None):
    return run_deterministic('p04', 'email_qa', 12, argv)


if __name__ == '__main__':
    raise SystemExit(main())
