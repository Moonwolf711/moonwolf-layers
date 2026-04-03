"""
Build the Moonwolf Bridge .amxd device file.
Uses ampf binary format required by Ableton Live.

Patcher structure:
  [live.thisdevice] → bang → [loadmess init] → [js moonwolf_bridge.js]
  [udpreceive 8002] → [prepend incoming] → [js moonwolf_bridge.js]
  [js moonwolf_bridge.js] outlet 0 → [print MoonwolfBridge:]
"""

import json
import struct
import os
import shutil

DEVICE_NAME = "Moonwolf Bridge"
JS_FILENAME = "moonwolf_bridge.js"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "Moonwolf Bridge.amxd")

# Also copy to Ableton User Library
ABLETON_MIDI_EFFECTS = os.path.expandvars(
    r"C:\Users\Owner\OneDrive\Desktop\ONE DRIVE NEW\OneDrive\Documents\Ableton\User Library\Presets\MIDI Effects\Max MIDI Effect"
)

def build_patcher():
    """Build the Max patcher JSON for the Moonwolf Bridge device."""
    patcher = {
        "patcher": {
            "fileversion": 1,
            "appversion": {
                "major": 8,
                "minor": 6,
                "revision": 0,
                "architecture": "x64",
                "modernui": 1
            },
            "classnamespace": "box",
            "rect": [100, 100, 600, 400],
            "bglocked": 0,
            "openinpresentation": 0,
            "default_fontsize": 12.0,
            "default_fontface": 0,
            "default_fontname": "Arial",
            "gridonopen": 1,
            "gridsize": [15.0, 15.0],
            "gridsnaponopen": 1,
            "objectsnaponopen": 1,
            "statusbarvisible": 2,
            "toolbarvisible": 1,
            "lefttoolbarpinned": 0,
            "toptoolbarpinned": 0,
            "righttoolbarpinned": 0,
            "bottomtoolbarpinned": 0,
            "toolbars_unpinned_last_save": 0,
            "tallnewobj": 0,
            "boxanimatetime": 200,
            "enablehscroll": 1,
            "enablevscroll": 1,
            "devicewidth": 0,
            "description": "Moonwolf Layers — LiveAPI bridge for game-controlled Ableton sessions",
            "digest": "",
            "tags": "",
            "style": "",
            "subpatcher_template": "",
            "assistshowspatchername": 0,
            "boxes": [
                # live.thisdevice — triggers init on load
                {
                    "box": {
                        "id": "obj-1",
                        "maxclass": "live.thisdevice",
                        "numinlets": 0,
                        "numoutlets": 1,
                        "outlettype": [""],
                        "patching_rect": [30, 30, 120, 20]
                    }
                },
                # loadmess init — sends "init" to JS on device load
                {
                    "box": {
                        "id": "obj-2",
                        "maxclass": "message",
                        "numinlets": 2,
                        "numoutlets": 1,
                        "outlettype": [""],
                        "patching_rect": [30, 70, 50, 22],
                        "text": "init"
                    }
                },
                # js moonwolf_bridge.js — main logic
                {
                    "box": {
                        "id": "obj-3",
                        "maxclass": "newobj",
                        "numinlets": 1,
                        "numoutlets": 1,
                        "outlettype": [""],
                        "patching_rect": [30, 150, 200, 22],
                        "text": "js moonwolf_bridge.js"
                    }
                },
                # udpreceive 8002 — listens for game commands
                {
                    "box": {
                        "id": "obj-4",
                        "maxclass": "newobj",
                        "numinlets": 1,
                        "numoutlets": 1,
                        "outlettype": [""],
                        "patching_rect": [280, 30, 130, 22],
                        "text": "udpreceive 8002"
                    }
                },
                # prepend incoming — tags UDP messages
                {
                    "box": {
                        "id": "obj-5",
                        "maxclass": "newobj",
                        "numinlets": 1,
                        "numoutlets": 1,
                        "outlettype": [""],
                        "patching_rect": [280, 70, 120, 22],
                        "text": "prepend incoming"
                    }
                },
                # print — debug output
                {
                    "box": {
                        "id": "obj-6",
                        "maxclass": "newobj",
                        "numinlets": 1,
                        "numoutlets": 0,
                        "patching_rect": [30, 200, 160, 22],
                        "text": "print MoonwolfBridge:"
                    }
                },
                # comment — device title
                {
                    "box": {
                        "id": "obj-7",
                        "maxclass": "comment",
                        "numinlets": 1,
                        "numoutlets": 0,
                        "patching_rect": [30, 240, 350, 20],
                        "text": "Moonwolf Bridge v1.0 — UDP 8002 → LiveAPI → Ableton"
                    }
                },
                # comment — instructions
                {
                    "box": {
                        "id": "obj-8",
                        "maxclass": "comment",
                        "numinlets": 1,
                        "numoutlets": 0,
                        "patching_rect": [30, 260, 400, 20],
                        "text": "Game sends /moonwolf/... commands. Bridge executes via LiveAPI."
                    }
                },
                # toggle for enable/disable
                {
                    "box": {
                        "id": "obj-9",
                        "maxclass": "toggle",
                        "numinlets": 1,
                        "numoutlets": 1,
                        "outlettype": ["int"],
                        "patching_rect": [450, 30, 24, 24],
                        "parameter_enable": 1,
                        "parameter_mappable": 0,
                        "saved_attribute_attributes": {
                            "valueof": {
                                "parameter_longname": "Enable",
                                "parameter_shortname": "Enable",
                                "parameter_type": 2,
                                "parameter_initial_enable": 1,
                                "parameter_initial": [1]
                            }
                        }
                    }
                },
                # gate — enable/disable UDP processing
                {
                    "box": {
                        "id": "obj-10",
                        "maxclass": "newobj",
                        "numinlets": 2,
                        "numoutlets": 1,
                        "outlettype": [""],
                        "patching_rect": [280, 110, 50, 22],
                        "text": "gate"
                    }
                }
            ],
            "lines": [
                # live.thisdevice → init message
                {
                    "patchline": {
                        "destination": ["obj-2", 0],
                        "source": ["obj-1", 0]
                    }
                },
                # init message → js
                {
                    "patchline": {
                        "destination": ["obj-3", 0],
                        "source": ["obj-2", 0]
                    }
                },
                # udpreceive → prepend incoming
                {
                    "patchline": {
                        "destination": ["obj-5", 0],
                        "source": ["obj-4", 0]
                    }
                },
                # prepend → gate input
                {
                    "patchline": {
                        "destination": ["obj-10", 1],
                        "source": ["obj-5", 0]
                    }
                },
                # toggle → gate control
                {
                    "patchline": {
                        "destination": ["obj-10", 0],
                        "source": ["obj-9", 0]
                    }
                },
                # gate → js
                {
                    "patchline": {
                        "destination": ["obj-3", 0],
                        "source": ["obj-10", 0]
                    }
                },
                # js outlet → print
                {
                    "patchline": {
                        "destination": ["obj-6", 0],
                        "source": ["obj-3", 0]
                    }
                }
            ]
        }
    }
    return patcher


def build_amxd(patcher_dict, output_path):
    """Build a valid .amxd file with ampf binary header."""
    patcher_json = json.dumps(patcher_dict, separators=(',', ' : ')).encode('utf-8')

    output = bytearray()
    output += b'ampf' + struct.pack('<I', 4)              # header magic + version
    output += b'mmmmmeta' + struct.pack('<I', 4)           # meta chunk header
    output += struct.pack('<I', 1)                          # meta version
    output += b'ptch' + struct.pack('<I', len(patcher_json))  # patcher chunk
    output += patcher_json

    with open(output_path, 'wb') as f:
        f.write(output)

    print(f"  Built: {output_path} ({len(output)} bytes)")
    return output_path


def main():
    print("Building Moonwolf Bridge .amxd device...")

    patcher = build_patcher()
    amxd_path = build_amxd(patcher, OUTPUT_PATH)

    # Copy JS file next to the .amxd
    js_src = os.path.join(OUTPUT_DIR, JS_FILENAME)
    if os.path.exists(js_src):
        print(f"  JS file: {js_src}")

    # Copy to Ableton User Library
    if os.path.isdir(ABLETON_MIDI_EFFECTS):
        dest_amxd = os.path.join(ABLETON_MIDI_EFFECTS, "Moonwolf Bridge.amxd")
        dest_js = os.path.join(ABLETON_MIDI_EFFECTS, JS_FILENAME)
        shutil.copy2(amxd_path, dest_amxd)
        shutil.copy2(js_src, dest_js)
        print(f"  Installed to Ableton User Library:")
        print(f"    {dest_amxd}")
        print(f"    {dest_js}")
    else:
        print(f"  Ableton User Library not found at: {ABLETON_MIDI_EFFECTS}")
        print(f"  Manually copy {amxd_path} and {JS_FILENAME} to your MIDI Effects folder")

    print("\nDone! Load 'Moonwolf Bridge' on any track in Ableton.")
    print("The game will auto-setup your session when you pick a song.")


if __name__ == "__main__":
    main()
