"""Import-compatibility shim for the anonymous supplement (generated file).

The validation sources were written to run from a repository root that is on
`sys.path`, where they say

    from benchmarks.paper_eval.t_onesweep import common as C
    from benchmarks.paper_eval.paper_config import write_manifest   (lazy)

In this package the same sources live in `code/t_onesweep/`, which Python puts
on `sys.path[0]` whenever you run one of them by path. This package therefore
sits next to them and makes both module names resolve here.

It adds no behaviour and changes no result:

  * `paper_eval/paper_config.py` is the repository file, anonymized, and only
    writes the `.config.json` provenance manifest next to a CSV. Its `git_sha()`
    returns "unknown" outside a checkout, which is the only difference you will
    see between a manifest you regenerate and the one shipped in `data/`.
  * `paper_eval/t_onesweep/__init__.py` re-points `__path__` at the directory
    the sources already live in, so `...t_onesweep.common` is the very same
    `code/t_onesweep/common.py` file you can read.
"""
