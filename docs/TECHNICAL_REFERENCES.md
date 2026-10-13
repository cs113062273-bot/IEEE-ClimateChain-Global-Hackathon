# Dependency verification

Retrieved 2026-10-13. The dependency lockfiles record exact resolved packages.

- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation): App Router manual setup, Node >=20.9, Windows support, build/type checking. npm registry resolved Next 16.4.0 and React 19.3.0 on this run.
- [React application setup](https://react.dev/learn/creating-a-react-app): framework application guidance.
- [Tailwind with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs): PostCSS integration. Registry resolved Tailwind and its PostCSS plugin 4.3.3.
- [Recharts upstream](https://github.com/recharts/recharts): native SVG charts and matching `react-is` version. Recharts 3.10.1 declares React 19 compatibility. The old recharts.org guide failed in the browsing tool; upstream README was used instead.
- [SciPy MILP](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html): optimization status, integer variables and HiGHS solver.
- [HiGHS parallel execution](https://ergo-code.github.io/HiGHS/dev/parallel/): static scheduler and the `threads` option. The local Windows crash was addressed with serialized solver execution and one native thread; [upstream Windows issue 2885](https://github.com/ergo-code/highs/issues/2885) reports a related multi-thread access violation. This is supporting context, not proof of an identical upstream cause.
- [Hardhat 3](https://hardhat.org/docs/getting-started): compatible local EVM test runner and deployment tooling. Chain-specific version checks are recorded in CHAIN_WORKLOG.md.

Host verification: Python 3.11.9, Node 24.19.0, npm 11.17.0 and Git 2.53.0.windows.2. The Windows `py` launcher is absent, so setup uses `python` and the virtual environment interpreter explicitly.
