---
name: ugui-to-csharp
description: Generate C# Unity UGUI view and controller code from a PSD-to-UGUI binding manifest. Use when an AI agent is asked to create, regenerate, or update C# UI control code for an existing generated UGUI prefab and bindings JSON, without slicing a PSD or generating prefab assets.
---

# UGUI to C#

## Overview

Use this skill after `$psd-to-ugui-prefab` or whenever a compatible `<Name>.bindings.json` already exists. The bundled generator reads the binding manifest and emits Unity C# `MonoBehaviour` view/controller code.

This skill does not read PSD files, export sprites, or create prefabs. It only generates code from a binding manifest.

## Quick Start

Run the generator from this skill folder:

```bash
python3 scripts/ugui_bindings_to_code.py /absolute/path/UnityProject/Assets/UI/Generated/Screen/Screen.bindings.json
```

To place code in another folder:

```bash
python3 scripts/ugui_bindings_to_code.py /absolute/path/Screen.bindings.json --out /absolute/path/UnityProject/Assets/Scripts/UI/Generated
```

## Inputs

The binding manifest must contain:

- `name`: screen/prefab name.
- `nodes[]`: exported UI nodes.
- `nodes[].property`: stable English `snake_case` C# binding key.
- `nodes[].gameObject`: generated English `snake_case` Unity GameObject name.
- `nodes[].psdName`: original PSD layer/group name when available.
- `nodes[].role`: `image`, `button`, or `text`.

The generated C# bridge resolves nodes by direct child index under the prefab root, using the same order stored in `nodes[]`. This keeps code generation independent from prefab YAML patching.

Generated C# methods use `nodes[].property` directly. Button handlers are named `on_<property>_click`, so a PSD path translated to `table_button_1_pass` becomes `on_table_button_1_pass_click`.

## Generated Files

Each run writes:

- `<Name>View.cs`, a Unity bridge with lookup methods such as `GetNode`, `GetImage`, `GetButton`, `SetNodeActive`, `SetText`, and `BindClick`.
- `<Name>Controller.cs`, a Unity controller with `show`, `hide`, `set_active`, `set_text`, `set_image_color`, and generated button handlers.
- Matching `.cs.meta` files with deterministic MonoScript GUIDs.

Attach `<Name>View` and `<Name>Controller` to the generated prefab root or to a scene instance of that prefab. The controller requires the view component and wires generated button handlers in `Awake`.

## Controller Naming

Generated C# fields and button handler methods use the manifest's English `snake_case` keys. For example, `table_button_1_pass` becomes `on_table_button_1_pass_click`.

## Validation

Always run at least one deterministic check after editing this skill:

```bash
python3 scripts/ugui_bindings_to_code.py /absolute/path/Screen.bindings.json --out /tmp/ugui-to-csharp-demo
```
