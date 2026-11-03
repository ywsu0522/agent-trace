"""HW1 P05: 44 original deterministic cases, no live inference."""

from scripts._deterministic import main as run_deterministic


def main(argv=None):
    return run_deterministic('p05', 'tool_registry', 44, argv)


if __name__ == '__main__':
    raise SystemExit(main())
