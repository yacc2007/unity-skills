#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def stable_guid(*parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:32]


def pascal_case(value: str, fallback: str = "Node") -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    if not words:
        words = [fallback]
    result = "".join(word[:1].upper() + word[1:] for word in words)
    if result[:1].isdigit():
        result = fallback + result
    return result


def code_identifier(value: str, fallback: str = "node") -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    name = re.sub(r"_+", "_", name)
    if not name:
        name = fallback
    if name[:1].isdigit():
        name = f"{fallback}_{name}"
    return name


def click_handler_name(key: str) -> str:
    return f"on_{code_identifier(key)}_click"


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def mono_script_meta(guid: str) -> str:
    return f"""fileFormatVersion: 2
guid: {guid}
MonoImporter:
  externalObjects: {{}}
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
  icon: {{instanceID: 0}}
  userData:
  assetBundleName:
  assetBundleVariant:
"""


def load_bindings(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Binding manifest must be a JSON object: {path}")
    if not isinstance(data.get("name"), str):
        raise SystemExit("Binding manifest is missing string field: name")
    if not isinstance(data.get("nodes"), list):
        raise SystemExit("Binding manifest is missing array field: nodes")
    for index, node in enumerate(data["nodes"]):
        if not isinstance(node, dict):
            raise SystemExit(f"nodes[{index}] must be an object")
        for field in ("property", "gameObject", "role"):
            if not isinstance(node.get(field), str):
                raise SystemExit(f"nodes[{index}] is missing string field: {field}")
    return data


def generate_csharp_view(class_name: str, nodes: list[dict[str, object]]) -> str:
    binding_initializers = []
    for index, node in enumerate(nodes):
        binding_initializers.append(
            "        new BindingSpec "
            + "{ "
            + f"key = {q(str(node['property']))}, "
            + f"childIndex = {index}, "
            + f"role = {q(str(node['role']))} "
            + "},"
        )
    specs = "\n".join(binding_initializers)

    return f"""using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public sealed class {class_name} : MonoBehaviour
{{
    [Serializable]
    public sealed class BindingSpec
    {{
        public string key;
        public int childIndex;
        public string role;
    }}

    public sealed class Binding
    {{
        public string key;
        public string role;
        public GameObject node;
        public RectTransform rectTransform;
        public Image image;
        public Button button;
    }}

    [SerializeField] private GameObject root;
    [SerializeField] private BindingSpec[] specs = new BindingSpec[]
    {{
{specs}
    }};

    private readonly List<Binding> bindings = new List<Binding>();
    private Dictionary<string, Binding> bindingMap;

    public GameObject Root => root != null ? root : gameObject;
    public IReadOnlyList<Binding> Bindings
    {{
        get
        {{
            EnsureBindingMap();
            return bindings;
        }}
    }}

    private void Awake()
    {{
        EnsureBindingMap();
    }}

    private void OnValidate()
    {{
        if (root == null)
        {{
            root = gameObject;
        }}

        bindingMap = null;
        bindings.Clear();
    }}

    public Binding FindBinding(string key)
    {{
        EnsureBindingMap();
        return key != null && bindingMap.TryGetValue(key, out var binding) ? binding : null;
    }}

    public GameObject GetNode(string key)
    {{
        return FindBinding(key)?.node;
    }}

    public RectTransform GetRectTransform(string key)
    {{
        return FindBinding(key)?.rectTransform;
    }}

    public Image GetImage(string key)
    {{
        return FindBinding(key)?.image;
    }}

    public Button GetButton(string key)
    {{
        return FindBinding(key)?.button;
    }}

    public void Show()
    {{
        SetRootActive(true);
    }}

    public void Hide()
    {{
        SetRootActive(false);
    }}

    public void SetRootActive(bool active)
    {{
        Root.SetActive(active);
    }}

    public void SetNodeActive(string key, bool active)
    {{
        var node = GetNode(key);
        if (node != null)
        {{
            node.SetActive(active);
        }}
    }}

    public void SetText(string key, string value)
    {{
        var node = GetNode(key);
        if (node == null)
        {{
            return;
        }}

        var text = node.GetComponent<Text>();
        if (text != null)
        {{
            text.text = value;
        }}
    }}

    public void SetImageColor(string key, Color color)
    {{
        var image = GetImage(key);
        if (image != null)
        {{
            image.color = color;
        }}
    }}

    public void BindClick(string key, Action handler)
    {{
        if (handler == null)
        {{
            return;
        }}

        var button = GetButton(key);
        if (button != null)
        {{
            button.onClick.AddListener(() => handler());
        }}
    }}

    public void ClearClickListeners(string key)
    {{
        var button = GetButton(key);
        if (button != null)
        {{
            button.onClick.RemoveAllListeners();
        }}
    }}

    private void EnsureBindingMap()
    {{
        if (bindingMap != null)
        {{
            return;
        }}

        bindings.Clear();
        bindingMap = new Dictionary<string, Binding>(StringComparer.Ordinal);
        var rootTransform = Root.transform;
        foreach (var spec in specs)
        {{
            if (spec == null || string.IsNullOrEmpty(spec.key))
            {{
                continue;
            }}

            GameObject node = null;
            if (spec.childIndex >= 0 && spec.childIndex < rootTransform.childCount)
            {{
                node = rootTransform.GetChild(spec.childIndex).gameObject;
            }}

            var binding = new Binding
            {{
                key = spec.key,
                role = spec.role,
                node = node,
                rectTransform = node != null ? node.GetComponent<RectTransform>() : null,
                image = node != null ? node.GetComponent<Image>() : null,
                button = node != null ? node.GetComponent<Button>() : null,
            }};

            bindings.Add(binding);
            bindingMap[binding.key] = binding;
        }}
    }}
}}
"""


def generate_csharp_controller(class_name: str, view_class_name: str, nodes: list[dict[str, object]]) -> str:
    button_nodes = [node for node in nodes if node.get("role") == "button"]
    wire_lines = []
    for node in button_nodes:
        key = str(node["property"])
        handler = click_handler_name(key)
        wire_lines.append(f"        View.ClearClickListeners({q(key)});")
        wire_lines.append(f"        View.BindClick({q(key)}, {handler});")
    if not wire_lines:
        wire_lines.append("        // No button bindings were generated.")

    handler_lines = []
    for node in button_nodes:
        key = str(node["property"])
        handler = click_handler_name(key)
        handler_lines.append(
            f"""    protected virtual void {handler}()
    {{
    }}
"""
        )

    return f"""using UnityEngine;
using UnityEngine.UI;

[DisallowMultipleComponent]
[RequireComponent(typeof({view_class_name}))]
public class {class_name} : MonoBehaviour
{{
    [SerializeField] private {view_class_name} view;

    protected {view_class_name} View
    {{
        get
        {{
            if (view == null)
            {{
                view = GetComponent<{view_class_name}>();
            }}

            return view;
        }}
    }}

    protected virtual void Awake()
    {{
        wire_events();
    }}

    public void show()
    {{
        View.Show();
    }}

    public void hide()
    {{
        View.Hide();
    }}

    public void set_active(string key, bool active)
    {{
        View.SetNodeActive(key, active);
    }}

    public void set_text(string key, string value)
    {{
        View.SetText(key, value);
    }}

    public void set_image_color(string key, Color color)
    {{
        View.SetImageColor(key, color);
    }}

    public GameObject get_node(string key)
    {{
        return View.GetNode(key);
    }}

    public Image get_image(string key)
    {{
        return View.GetImage(key);
    }}

    public Button get_button(string key)
    {{
        return View.GetButton(key);
    }}

    protected virtual void wire_events()
    {{
{chr(10).join(wire_lines)}
    }}

{chr(10).join(handler_lines)}}}
"""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate C# UI control code from a PSD-to-UGUI binding manifest.")
    parser.add_argument("bindings", help="Path to <Name>.bindings.json generated by the prefab skill.")
    parser.add_argument("--out", help="Output folder. Defaults to the binding manifest folder.")
    parser.add_argument("--class-name", help="C# controller class name. Defaults to <Name>Controller.")
    parser.add_argument("--controller-class-name", help="C# controller class name. Overrides --class-name.")
    parser.add_argument("--view-class-name", help="C# UGUI bridge class name. Defaults to <Name>View.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    bindings_path = Path(args.bindings).expanduser().resolve()
    if not bindings_path.exists():
        raise SystemExit(f"Bindings not found: {bindings_path}")

    data = load_bindings(bindings_path)
    name = str(data["name"])
    nodes = data["nodes"]
    assert isinstance(nodes, list)

    out_dir = Path(args.out).expanduser().resolve() if args.out else bindings_path.parent
    class_name = args.controller_class_name or args.class_name or f"{pascal_case(name)}Controller"
    view_class_name = args.view_class_name or f"{pascal_case(name)}View"
    controller_path = out_dir / f"{class_name}.cs"
    view_path = out_dir / f"{view_class_name}.cs"

    write_text(controller_path, generate_csharp_controller(class_name, view_class_name, nodes))
    write_text(controller_path.with_suffix(controller_path.suffix + ".meta"), mono_script_meta(stable_guid(name, class_name, "csharp-controller")))
    write_text(view_path, generate_csharp_view(view_class_name, nodes))
    write_text(view_path.with_suffix(view_path.suffix + ".meta"), mono_script_meta(stable_guid(name, view_class_name, "csharp-view")))

    summary = {
        "name": name,
        "nodes": len(nodes),
        "buttons": sum(1 for node in nodes if node.get("role") == "button"),
        "outputs": {
            "controller": str(controller_path),
            "view": str(view_path),
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
