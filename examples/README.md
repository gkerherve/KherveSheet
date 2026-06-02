# KherveSheet example files

Rich, ready-to-open `.ksheet` workbooks shipped with KherveSheet. They
appear in the app under **Help ▸ Example Files** (the menu auto-discovers
every `*.ksheet` in this folder).

## Authoring new examples

`ksheet_author.py` is a small, Qt-free library for writing `.ksheet`
files directly (just `h5py` + `numpy`). A `.ksheet` is an HDF5 container
whose loader re-evaluates formulas on open, so examples are generated
without launching the GUI.

```bash
python examples/build_projectile_motion.py
```

Each `build_*.py` script constructs a `Workbook`, adds formatted tables,
charts, equations and notes, and saves a `.ksheet` here. See
`build_projectile_motion.py` for a complete, worked reference.

The specialised **`ksheet-example-author`** agent
(`.claude/agents/ksheet-example-author.md`) automates this: ask it for a
topic and it designs, generates and verifies a polished example.

> Indices in the library are 0-based; formula cell references are 1-based
> A1 strings. A `table()` starting at row `n` puts its header at sheet row
> `n+1` and its first data row at sheet row `n+2`.
