#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


IMAGE_SCRIPT_GUID = "fe87c0e1cc204ed48ad3b37840f39efc"
BUTTON_SCRIPT_GUID = "4e29b1a8efbd4b44bb3f3716e73f07ff"

DEFAULT_TRANSLATIONS = {
    "通用UI": "common_ui",
    "背景": "background",
    "图层": "layer",
    "按钮": "button",
    "按鈕": "button",
    "文本": "text",
    "文字": "text",
    "标题": "title",
    "標題": "title",
    "图片": "image",
    "圖像": "image",
    "图像": "image",
    "面板": "panel",
    "弹窗": "popup",
    "彈窗": "popup",
    "头像": "avatar",
    "用户": "user",
    "用戶": "user",
    "倒计时": "countdown",
    "椭圆": "ellipse",
    "橢圓": "ellipse",
    "矩形": "rectangle",
    "形状": "shape",
    "形狀": "shape",
    "时钟": "clock",
    "時鐘": "clock",
    "信号": "signal",
    "電量": "battery_level",
    "电量": "battery_level",
    "电池": "battery",
    "聊天": "chat",
    "表情": "emoji",
    "语音": "voice",
    "語音": "voice",
    "菜单": "menu",
    "菜單": "menu",
    "关闭": "close",
    "關閉": "close",
    "返回": "back",
    "确认": "confirm",
    "確認": "confirm",
    "取消": "cancel",
    "确定": "ok",
    "確定": "ok",
    "搜索": "search",
    "输入": "input",
    "輸入": "input",
    "列表": "list",
    "拷贝": "copy",
    "副本": "copy",
    "組": "group",
    "组": "group",
    "底": "base",
    "绿": "green",
    "綠": "green",
    "红": "red",
    "紅": "red",
    "蓝": "blue",
    "藍": "blue",
    "黄": "yellow",
    "黃": "yellow",
    "左": "left",
    "右": "right",
    "上": "top",
    "下": "bottom",
}


@dataclass
class LayerAsset:
    original_name: str
    psd_path: str
    asset_name: str
    node_name: str
    property_name: str
    role: str
    left: int
    top: int
    right: int
    bottom: int
    sprite_path: Path
    sprite_guid: str

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def anchored_position(self, canvas_width: int, canvas_height: int) -> tuple[float, float]:
        cx = self.left + self.width / 2
        cy = self.top + self.height / 2
        return cx - canvas_width / 2, canvas_height / 2 - cy


class FileIdAllocator:
    def __init__(self) -> None:
        self._next = 100000

    def take(self) -> int:
        self._next += 1
        return self._next


def stable_guid(*parts: object) -> str:
    seed = "|".join(str(part) for part in parts)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:32]


def safe_asset_name(value: str, fallback: str = "Layer") -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return name or fallback


def unity_object_name(value: str, fallback: str = "Layer") -> str:
    name = value.replace("\x00", "").strip()
    return name or fallback


def screen_asset_name(value: str, translations: dict[str, str] | None = None, fallback: str = "Screen") -> str:
    if re.search(r"[A-Za-z]", value):
        return safe_asset_name(value, fallback=fallback)
    return safe_asset_name(code_binding_name(value, translations, fallback=fallback.lower()), fallback=fallback)


def code_binding_name(value: str, translations: dict[str, str] | None = None, fallback: str = "node") -> str:
    translated = value
    merged = dict(DEFAULT_TRANSLATIONS)
    if translations:
        merged.update(translations)
    for source, replacement in sorted(merged.items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(source, f"_{replacement}_")
    translated = translated.replace("&", "_and_").replace("+", "_and_")
    translated = re.sub(r"[^A-Za-z0-9]+", "_", translated).strip("_").lower()
    translated = re.sub(r"_+", "_", translated)
    if not translated:
        translated = fallback
    if translated[:1].isdigit():
        translated = f"{fallback}_{translated}"
    return translated


def uniquify(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}{index}"
        index += 1
    used.add(candidate)
    return candidate


def uniquify_code_name(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def load_translation_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Translation map must be a JSON object of source text to English names.")
    translations: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise SystemExit("Translation map keys and values must be strings.")
        translations[key] = code_binding_name(value)
    return translations


def infer_role(name: str) -> str:
    lower_name = name.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lower_name).strip("_")
    tokens = set(normalized.split("_"))
    button_markers = ("按钮", "按鈕", "button")
    button_words = {"btn", "button", "play", "start", "submit", "confirm", "cancel", "close", "ok", "menu", "chat", "emoji", "search", "back", "next"}
    if (
        normalized.startswith(("btn_", "button_"))
        or any(marker in lower_name for marker in button_markers)
        or bool(button_words & tokens)
    ):
        return "button"
    text_markers = ("文本", "文字", "标题", "標題")
    if normalized.startswith(("txt_", "text_", "label_", "title_")) or any(marker in lower_name for marker in text_markers):
        return "text"
    if {"txt", "text", "label", "title"} & tokens:
        return "text"
    return "image"


def layer_is_clipping(layer: object) -> bool:
    if hasattr(layer, "clipping"):
        return bool(getattr(layer, "clipping"))
    return bool(getattr(layer, "clipping_layer", False))


def group_has_direct_clipping(layer: object, include_hidden: bool) -> bool:
    for child in layer:
        if not include_hidden and not child.is_visible():
            continue
        if layer_is_clipping(child):
            return True
    return False



def yn(value: bool) -> int:
    return 1 if value else 0


def fnum(value: float | int) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def clean_sprite_outputs(sprites_dir: Path) -> None:
    if not sprites_dir.exists():
        return
    for path in sprites_dir.iterdir():
        if path.is_file() and (path.suffix.lower() == ".png" or path.name.endswith(".png.meta")):
            path.unlink()


def write_solid_png(path: Path, width: int, height: int, rgba: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixel = bytes(rgba)
    row = b"\x00" + pixel * width
    raw = row * height

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def export_psd_layers(
    psd_path: Path,
    sprites_dir: Path,
    include_hidden: bool,
    translations: dict[str, str],
) -> tuple[int, int, list[LayerAsset]]:
    try:
        from psd_tools import PSDImage
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: psd-tools. Install with `python3 -m pip install psd-tools pillow`."
        ) from exc

    psd = PSDImage.open(psd_path)
    canvas_width, canvas_height = psd.size
    used_assets: set[str] = set()
    used_props: set[str] = set()
    layers: list[LayerAsset] = []

    def walk(container: Iterable[object], groups: list[str]) -> None:
        for layer in container:
            name = getattr(layer, "name", None) or "Layer"
            is_visible = bool(layer.is_visible())
            if not include_hidden and not is_visible:
                continue
            psd_layer_path = "/".join(groups + [name])
            if layer.is_group():
                if group_has_direct_clipping(layer, include_hidden):
                    bbox = tuple(int(v) for v in layer.bbox)
                    left, top, right, bottom = bbox
                    if right <= left or bottom <= top:
                        continue
                    image = layer.composite()
                    if image is None:
                        continue
                    if image.mode != "RGBA":
                        image = image.convert("RGBA")

                    base = safe_asset_name(psd_layer_path.replace("/", "_"))
                    asset_name = uniquify(base, used_assets)
                    property_name = uniquify_code_name(code_binding_name(psd_layer_path, translations), used_props)
                    node_name = property_name
                    sprite_path = sprites_dir / f"{asset_name}.png"
                    image.save(sprite_path)

                    layers.append(
                        LayerAsset(
                            original_name=name,
                            psd_path=psd_layer_path,
                            asset_name=asset_name,
                            node_name=node_name,
                            property_name=property_name,
                            role=infer_role(psd_layer_path),
                            left=left,
                            top=top,
                            right=right,
                            bottom=bottom,
                            sprite_path=sprite_path,
                            sprite_guid=stable_guid(psd_path.resolve(), psd_layer_path, bbox),
                        )
                    )
                    continue
                walk(layer, groups + [name])
                continue

            bbox = tuple(int(v) for v in layer.bbox)
            left, top, right, bottom = bbox
            if right <= left or bottom <= top:
                continue

            if hasattr(layer, "compose"):
                image = layer.compose()
            else:
                image = layer.composite()
            if image is None:
                continue
            if image.mode != "RGBA":
                image = image.convert("RGBA")

            base = safe_asset_name(psd_layer_path.replace("/", "_"))
            asset_name = uniquify(base, used_assets)
            property_name = uniquify_code_name(code_binding_name(psd_layer_path, translations), used_props)
            node_name = property_name
            sprite_path = sprites_dir / f"{asset_name}.png"
            image.save(sprite_path)

            layers.append(
                LayerAsset(
                    original_name=name,
                    psd_path=psd_layer_path,
                    asset_name=asset_name,
                    node_name=node_name,
                    property_name=property_name,
                    role=infer_role(psd_layer_path),
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                    sprite_path=sprite_path,
                    sprite_guid=stable_guid(psd_path.resolve(), psd_layer_path, bbox),
                )
            )

    walk(psd, [])
    return canvas_width, canvas_height, layers


def demo_layers(name: str, sprites_dir: Path, translations: dict[str, str] | None = None) -> tuple[int, int, list[LayerAsset]]:
    specs = [
        ("background", "image", 0, 0, 800, 480, (29, 36, 50, 255)),
        ("title", "text", 180, 54, 620, 118, (238, 241, 245, 255)),
        ("panel_main", "image", 96, 138, 704, 384, (64, 93, 114, 235)),
        ("btn_start", "button", 288, 306, 512, 370, (60, 174, 111, 255)),
    ]
    layers: list[LayerAsset] = []
    used_assets: set[str] = set()
    used_props: set[str] = set()
    for layer_name, role, left, top, right, bottom, color in specs:
        asset_name = uniquify(safe_asset_name(layer_name), used_assets)
        property_name = uniquify_code_name(code_binding_name(layer_name, translations), used_props)
        node_name = property_name
        sprite_path = sprites_dir / f"{asset_name}.png"
        write_solid_png(sprite_path, right - left, bottom - top, color)
        layers.append(
            LayerAsset(
                original_name=layer_name,
                psd_path=layer_name,
                asset_name=asset_name,
                node_name=node_name,
                property_name=property_name,
                role=role,
                left=left,
                top=top,
                right=right,
                bottom=bottom,
                sprite_path=sprite_path,
                sprite_guid=stable_guid("demo", name, layer_name),
            )
        )
    return 800, 480, layers


def sprite_meta(guid: str, pixels_per_unit: float) -> str:
    return f"""fileFormatVersion: 2
guid: {guid}
TextureImporter:
  internalIDToNameTable: []
  externalObjects: {{}}
  serializedVersion: 12
  mipmaps:
    mipMapMode: 0
    enableMipMap: 0
    sRGBTexture: 1
    linearTexture: 0
    fadeOut: 0
    borderMipMap: 0
    mipMapsPreserveCoverage: 0
    alphaTestReferenceValue: 0.5
    mipMapFadeDistanceStart: 1
    mipMapFadeDistanceEnd: 3
  bumpmap:
    convertToNormalMap: 0
    externalNormalMap: 0
    heightScale: 0.25
    normalMapFilter: 0
  isReadable: 0
  streamingMipmaps: 0
  streamingMipmapsPriority: 0
  vTOnly: 0
  ignoreMipmapLimit: 0
  grayScaleToAlpha: 0
  generateCubemap: 6
  cubemapConvolution: 0
  seamlessCubemap: 0
  textureFormat: 1
  maxTextureSize: 2048
  textureSettings:
    serializedVersion: 2
    filterMode: 1
    aniso: 1
    mipBias: 0
    wrapU: 1
    wrapV: 1
    wrapW: 1
  nPOTScale: 0
  lightmap: 0
  compressionQuality: 50
  spriteMode: 1
  spriteExtrude: 1
  spriteMeshType: 1
  alignment: 0
  spritePivot: {{x: 0.5, y: 0.5}}
  spritePixelsToUnits: {fnum(pixels_per_unit)}
  spriteBorder: {{x: 0, y: 0, z: 0, w: 0}}
  spriteGenerateFallbackPhysicsShape: 1
  alphaUsage: 1
  alphaIsTransparency: 1
  spriteTessellationDetail: -1
  textureType: 8
  textureShape: 1
  singleChannelComponent: 0
  flipbookRows: 1
  flipbookColumns: 1
  maxTextureSizeSet: 0
  compressionQualitySet: 0
  textureFormatSet: 0
  ignorePngGamma: 0
  applyGammaDecoding: 0
  platformSettings: []
  spriteSheet:
    serializedVersion: 2
    sprites: []
    outline: []
    physicsShape: []
    bones: []
    spriteID:
    internalID: 0
    vertices: []
    indices:
    edges: []
    weights: []
    secondaryTextures: []
  userData:
  assetBundleName:
  assetBundleVariant:
"""


def prefab_meta(guid: str) -> str:
    return f"""fileFormatVersion: 2
guid: {guid}
PrefabImporter:
  externalObjects: {{}}
  userData:
  assetBundleName:
  assetBundleVariant:
"""


def component_lines(component_ids: list[int]) -> str:
    return "\n".join(f"  - component: {{fileID: {component_id}}}" for component_id in component_ids)


def game_object_yaml(file_id: int, name: str, component_ids: list[int]) -> str:
    return f"""--- !u!1 &{file_id}
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  serializedVersion: 6
  m_Component:
{component_lines(component_ids)}
  m_Layer: 5
  m_Name: {q(name)}
  m_TagString: Untagged
  m_Icon: {{fileID: 0}}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
"""


def rect_transform_yaml(
    file_id: int,
    game_object_id: int,
    children: list[int],
    father_id: int,
    root_order: int,
    anchored_x: float,
    anchored_y: float,
    width: float,
    height: float,
) -> str:
    if children:
        child_lines = "\n".join(f"  - {{fileID: {child_id}}}" for child_id in children)
    else:
        child_lines = " []"
    return f"""--- !u!224 &{file_id}
RectTransform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {game_object_id}}}
  m_LocalRotation: {{x: 0, y: 0, z: 0, w: 1}}
  m_LocalPosition: {{x: 0, y: 0, z: 0}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
  m_ConstrainProportionsScale: 0
  m_Children:{chr(10) + child_lines if children else child_lines}
  m_Father: {{fileID: {father_id}}}
  m_RootOrder: {root_order}
  m_LocalEulerAnglesHint: {{x: 0, y: 0, z: 0}}
  m_AnchorMin: {{x: 0.5, y: 0.5}}
  m_AnchorMax: {{x: 0.5, y: 0.5}}
  m_AnchoredPosition: {{x: {fnum(anchored_x)}, y: {fnum(anchored_y)}}}
  m_SizeDelta: {{x: {fnum(width)}, y: {fnum(height)}}}
  m_Pivot: {{x: 0.5, y: 0.5}}
"""


def canvas_renderer_yaml(file_id: int, game_object_id: int) -> str:
    return f"""--- !u!222 &{file_id}
CanvasRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {game_object_id}}}
  m_CullTransparentMesh: 1
"""


def image_yaml(file_id: int, game_object_id: int, sprite_guid: str, raycast_target: bool) -> str:
    return f"""--- !u!114 &{file_id}
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {game_object_id}}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {IMAGE_SCRIPT_GUID}, type: 3}}
  m_Name:
  m_EditorClassIdentifier:
  m_Material: {{fileID: 0}}
  m_Color: {{r: 1, g: 1, b: 1, a: 1}}
  m_RaycastTarget: {yn(raycast_target)}
  m_RaycastPadding: {{x: 0, y: 0, z: 0, w: 0}}
  m_Maskable: 1
  m_OnCullStateChanged:
    m_PersistentCalls:
      m_Calls: []
  m_Sprite: {{fileID: 21300000, guid: {sprite_guid}, type: 3}}
  m_Type: 0
  m_PreserveAspect: 0
  m_FillCenter: 1
  m_FillMethod: 4
  m_FillAmount: 1
  m_FillClockwise: 1
  m_FillOrigin: 0
  m_UseSpriteMesh: 0
  m_PixelsPerUnitMultiplier: 1
"""


def button_yaml(file_id: int, game_object_id: int, target_graphic_id: int) -> str:
    return f"""--- !u!114 &{file_id}
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {game_object_id}}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {BUTTON_SCRIPT_GUID}, type: 3}}
  m_Name:
  m_EditorClassIdentifier:
  m_Navigation:
    m_Mode: 3
    m_WrapAround: 0
    m_SelectOnUp: {{fileID: 0}}
    m_SelectOnDown: {{fileID: 0}}
    m_SelectOnLeft: {{fileID: 0}}
    m_SelectOnRight: {{fileID: 0}}
  m_Transition: 1
  m_Colors:
    m_NormalColor: {{r: 1, g: 1, b: 1, a: 1}}
    m_HighlightedColor: {{r: 0.88235295, g: 0.88235295, b: 0.88235295, a: 1}}
    m_PressedColor: {{r: 0.69803923, g: 0.69803923, b: 0.69803923, a: 1}}
    m_SelectedColor: {{r: 0.88235295, g: 0.88235295, b: 0.88235295, a: 1}}
    m_DisabledColor: {{r: 0.52156866, g: 0.52156866, b: 0.52156866, a: 0.5}}
    m_ColorMultiplier: 1
    m_FadeDuration: 0.1
  m_SpriteState:
    m_HighlightedSprite: {{fileID: 0}}
    m_PressedSprite: {{fileID: 0}}
    m_SelectedSprite: {{fileID: 0}}
    m_DisabledSprite: {{fileID: 0}}
  m_AnimationTriggers:
    m_NormalTrigger: Normal
    m_HighlightedTrigger: Highlighted
    m_PressedTrigger: Pressed
    m_SelectedTrigger: Selected
    m_DisabledTrigger: Disabled
  m_Interactable: 1
  m_TargetGraphic: {{fileID: {target_graphic_id}}}
  m_OnClick:
    m_PersistentCalls:
      m_Calls: []
"""


def binding_view_yaml(
    file_id: int,
    game_object_id: int,
    script_guid: str,
    root_game_object_id: int,
    layer_ids: list[dict[str, int | LayerAsset]],
) -> str:
    entries = []
    for item in layer_ids:
        layer = item["layer"]
        assert isinstance(layer, LayerAsset)
        go_id = int(item["go"])
        rect_id = int(item["rect"])
        image_id = int(item["image"])
        button_id = int(item.get("button", 0))
        entries.append(
            f"""  - key: {layer.property_name}
    node: {{fileID: {go_id}}}
    rectTransform: {{fileID: {rect_id}}}
    image: {{fileID: {image_id}}}
    button: {{fileID: {button_id}}}"""
        )
    bindings = "\n".join(entries) if entries else "  []"
    return f"""--- !u!114 &{file_id}
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {game_object_id}}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {script_guid}, type: 3}}
  m_Name:
  m_EditorClassIdentifier:
  root: {{fileID: {root_game_object_id}}}
  bindings:
{bindings}
"""


def generate_prefab(
    name: str,
    canvas_width: int,
    canvas_height: int,
    layers: list[LayerAsset],
    view_script_guid: str | None,
) -> str:
    ids = FileIdAllocator()
    root_go = ids.take()
    root_rect = ids.take()
    root_components = [root_rect]
    root_view = ids.take() if view_script_guid else None
    if root_view is not None:
        root_components.append(root_view)

    layer_ids: list[dict[str, int | LayerAsset]] = []
    child_rects: list[int] = []
    for layer in layers:
        item: dict[str, int | LayerAsset] = {
            "layer": layer,
            "go": ids.take(),
            "rect": ids.take(),
            "canvas": ids.take(),
            "image": ids.take(),
        }
        if layer.role == "button":
            item["button"] = ids.take()
        layer_ids.append(item)
        child_rects.append(int(item["rect"]))

    chunks = ["%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n"]
    chunks.append(game_object_yaml(root_go, name, root_components))
    chunks.append(rect_transform_yaml(root_rect, root_go, child_rects, 0, 0, 0, 0, canvas_width, canvas_height))
    if root_view is not None and view_script_guid is not None:
        chunks.append(binding_view_yaml(root_view, root_go, view_script_guid, root_go, layer_ids))

    for index, item in enumerate(layer_ids):
        layer = item["layer"]
        assert isinstance(layer, LayerAsset)
        component_ids = [int(item["rect"]), int(item["canvas"]), int(item["image"])]
        if "button" in item:
            component_ids.append(int(item["button"]))
        chunks.append(game_object_yaml(int(item["go"]), layer.node_name, component_ids))
        x, y = layer.anchored_position(canvas_width, canvas_height)
        chunks.append(
            rect_transform_yaml(
                int(item["rect"]),
                int(item["go"]),
                [],
                root_rect,
                index,
                x,
                y,
                layer.width,
                layer.height,
            )
        )
        chunks.append(canvas_renderer_yaml(int(item["canvas"]), int(item["go"])))
        chunks.append(image_yaml(int(item["image"]), int(item["go"]), layer.sprite_guid, layer.role == "button"))
        if "button" in item:
            chunks.append(button_yaml(int(item["button"]), int(item["go"]), int(item["image"])))

    return "".join(chunks)


def generate_bindings(name: str, canvas_width: int, canvas_height: int, layers: list[LayerAsset], prefab_path: Path) -> dict[str, object]:
    nodes = []
    for layer in layers:
        x, y = layer.anchored_position(canvas_width, canvas_height)
        nodes.append(
            {
                "property": layer.property_name,
                "gameObject": layer.node_name,
                "role": layer.role,
                "psdName": layer.original_name,
                "sourceLayer": layer.psd_path,
                "sprite": str(layer.sprite_path),
                "spriteGuid": layer.sprite_guid,
                "bounds": {
                    "left": layer.left,
                    "top": layer.top,
                    "right": layer.right,
                    "bottom": layer.bottom,
                    "width": layer.width,
                    "height": layer.height,
                },
                "anchoredPosition": {"x": x, "y": y},
            }
        )
    return {
        "name": name,
        "prefab": str(prefab_path),
        "canvas": {"width": canvas_width, "height": canvas_height},
        "nodes": nodes,
    }


def write_outputs(
    name: str,
    out_dir: Path,
    canvas_width: int,
    canvas_height: int,
    layers: list[LayerAsset],
    pixels_per_unit: float,
) -> dict[str, Path]:
    prefab_path = out_dir / f"{name}.prefab"
    bindings_path = out_dir / f"{name}.bindings.json"

    for layer in layers:
        write_text(layer.sprite_path.with_suffix(layer.sprite_path.suffix + ".meta"), sprite_meta(layer.sprite_guid, pixels_per_unit))

    write_text(prefab_path, generate_prefab(name, canvas_width, canvas_height, layers, None))
    write_text(prefab_path.with_suffix(prefab_path.suffix + ".meta"), prefab_meta(stable_guid(name, "prefab")))
    write_text(bindings_path, json.dumps(generate_bindings(name, canvas_width, canvas_height, layers, prefab_path), ensure_ascii=False, indent=2))
    return {"prefab": prefab_path, "bindings": bindings_path}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a Photoshop PSD into Unity UGUI prefab assets and a binding manifest.")
    parser.add_argument("psd", nargs="?", help="Path to the PSD file. Omit only when using --demo.")
    parser.add_argument("--out", required=True, help="Output folder, ideally inside a Unity project's Assets directory.")
    parser.add_argument("--name", help="Screen/prefab name. Defaults to the PSD stem or DemoScreen.")
    parser.add_argument("--sprites-folder", default="Sprites", help="Sprite subfolder under --out.")
    parser.add_argument("--pixels-per-unit", type=float, default=100.0, help="Unity sprite pixels per unit for generated PNG .meta files.")
    parser.add_argument("--include-hidden", action="store_true", help="Export hidden PSD layers too.")
    parser.add_argument("--clean-sprites", action="store_true", help="Delete existing generated .png and .png.meta files in the sprite output folder before exporting.")
    parser.add_argument("--translation-map", help="Optional JSON object mapping PSD Chinese/source terms to English code-name terms.")
    parser.add_argument("--demo", action="store_true", help="Generate a deterministic demo without reading a PSD.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.demo and not args.psd:
        raise SystemExit("A PSD path is required unless --demo is used.")

    psd_path = Path(args.psd).expanduser().resolve() if args.psd else None
    if psd_path and not psd_path.exists():
        raise SystemExit(f"PSD not found: {psd_path}")

    translations = load_translation_map(args.translation_map)
    name = screen_asset_name(args.name or (psd_path.stem if psd_path else "DemoScreen"), translations, fallback="Screen")
    out_dir = Path(args.out).expanduser().resolve()
    sprites_dir = out_dir / args.sprites_folder
    out_dir.mkdir(parents=True, exist_ok=True)
    sprites_dir.mkdir(parents=True, exist_ok=True)
    if args.clean_sprites:
        clean_sprite_outputs(sprites_dir)

    if args.demo:
        canvas_width, canvas_height, layers = demo_layers(name, sprites_dir, translations)
    else:
        assert psd_path is not None
        canvas_width, canvas_height, layers = export_psd_layers(psd_path, sprites_dir, args.include_hidden, translations)

    if not layers:
        raise SystemExit("No exportable layers found.")

    outputs = write_outputs(name, out_dir, canvas_width, canvas_height, layers, args.pixels_per_unit)
    summary = {
        "name": name,
        "canvas": {"width": canvas_width, "height": canvas_height},
        "layers": len(layers),
        "outputs": {key: str(path) for key, path in outputs.items()},
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
