"""HW1 P07: 31 original deterministic cases, no live inference."""

from scripts._deterministic import main as run_deterministic


def main(argv=None):
    return run_deterministic('p07', 'agent_loop', 31, argv)


if __name__ == '__main__':
    raise SystemExit(main())
