---
name: psd-to-ugui-prefab
description: Convert Photoshop .psd UI mockups into Unity UGUI prefab assets, exported sprite PNGs, and a layer binding manifest. Use when an AI agent is asked to import, slice, convert, or rebuild a visual Unity UGUI prefab hierarchy from a PSD without generating TypeScript or C# control code.
---

# PSD to UGUI Prefab

## Overview

Use this skill to turn a Photoshop PSD into Unity-ready UGUI visual assets. The bundled converter exports visible PSD layers as sprite PNGs, writes deterministic Unity `.meta` files, creates a `.prefab` hierarchy with `RectTransform` + `Image` components, detects button-like layers as UGUI `Button` nodes, and writes a binding manifest for later code generation.

This skill does not generate code. Use `$ugui-to-csharp` after this skill when C# control code is needed.

## Quick Start

Run the converter from this skill folder:

```bash
python3 scripts/psd_to_ugui_prefab.py /absolute/path/screen.psd --out /absolute/path/UnityProject/Assets/UI/Generated/Screen --name Screen --clean-sprites
```

For a smoke test without a PSD:

```bash
python3 scripts/psd_to_ugui_prefab.py --demo --out /tmp/psd-to-ugui-prefab-demo --name DemoScreen
```

The converter requires `psd-tools` and Pillow for real PSD input. If imports fail, install them in the active Python environment before rerunning:

```bash
python3 -m pip install psd-tools pillow
```

## Workflow

1. Choose an output folder inside the Unity project, usually under `Assets/UI/Generated/<ScreenName>`.
2. Ensure the Unity project has the `com.unity.ugui` package installed.
3. Run `scripts/psd_to_ugui_prefab.py` with the PSD path, output folder, screen name, and `--clean-sprites` when regenerating an existing output folder.
4. Review `<ScreenName>.bindings.json` to confirm layer names, roles, coordinates, generated binding keys, and sprite paths.
5. Open Unity or refresh the Asset Database so PNG `.meta` files and the prefab are imported.
6. If code is needed, pass the generated `<ScreenName>.bindings.json` to `$ugui-to-csharp`.

## Layer Naming

The converter infers visual/control roles from layer names:

- `btn_*`, `button_*`, or names containing ` button` become UGUI `Button` nodes.
- Chinese `按钮` / `按鈕` and common action names such as `play`, `start`, `submit`, `confirm`, `cancel`, `close`, `menu`, `chat`, and `search` are also treated as buttons.
- `txt_*`, `text_*`, `label_*`, or `title_*` are tagged as text bindings in the manifest, but remain rasterized images by default for visual fidelity.
- Other visible leaf layers become UGUI `Image` nodes.

Groups are traversed into visible leaf layers by default. Groups with direct clipping-mask layers are exported as one composited sprite to preserve masks. Hidden layers are skipped unless `--include-hidden` is passed. PSD layer order is preserved as Unity sibling order: earlier children render behind later children.

Generated Unity GameObject names use the same English `snake_case` names as code bindings. The binding manifest stores `sourceLayer` for the PSD path and `psdName` for the exact original PSD layer/group name.

Binding keys in `nodes[].property` and Unity names in `nodes[].gameObject` are generated from the PSD layer path as English `snake_case`: Chinese terms are translated with the built-in UI dictionary, spaces and separators become `_`, and duplicate keys get `_2`, `_3`, etc. Use `--translation-map /path/to/map.json` to provide or override project-specific Chinese-to-English terms.

## Generated Files

Each conversion writes:

- `<Name>.prefab` with a root `RectTransform` and one child per exported layer.
- `Sprites/*.png` and matching `.png.meta` files with deterministic GUIDs for prefab references.
- `<Name>.bindings.json` containing the PSD size, layer bounds, GameObject names, roles, sprite paths, and stable binding keys.

Use `--clean-sprites` for repeated conversions into the same folder so stale, previously exported sprite files do not remain in `Sprites/`.

## Validation

Always run at least one deterministic check after editing this skill:

```bash
python3 scripts/psd_to_ugui_prefab.py --demo --out /tmp/psd-to-ugui-prefab-demo --name DemoScreen
```

When a Unity project is available, refresh Unity and check the console for YAML/import warnings before considering the conversion complete.
