"""HW1 P03: 18 original deterministic cases, no live inference."""

from scripts._deterministic import main as run_deterministic


def main(argv=None):
    return run_deterministic('p03', 'bm25', 18, argv, uses_archive=True)


if __name__ == '__main__':
    raise SystemExit(main())
