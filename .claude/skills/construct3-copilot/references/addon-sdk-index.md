# Construct 3 Addon SDK Quick Reference

Reference for developing custom Plugins and Behaviors for Construct 3.

## Addon Types

| Type | Purpose | Files |
|------|---------|-------|
| **Plugin** | New object type (Sprite, Text, etc.) | plugin.js, type.js, instance.js |
| **Behavior** | Attachable behavior (Platform, Bullet, etc.) | behavior.js, type.js, instance.js |
| **Effect** | WebGL/WebGPU shader effect | effect.fx, effect.wgsl |

## Project Structure

```
my-addon/
├── addon.json              # Addon metadata
├── aces.json               # ACE definitions
├── lang/
│   └── en-US.json          # Language strings
├── c3runtime/              # Runtime scripts
│   ├── main.js             # Entry point
│   ├── plugin.js           # Plugin class
│   ├── type.js             # Type class
│   └── instance.js         # Instance class
└── editor/                 # Editor scripts (optional)
```

## Core Files Reference

### addon.json
```json
{
  "is-c3-addon": true,
  "sdk-version": 2,
  "type": "plugin",
  "name": "My Plugin",
  "id": "MyCompany_MyPlugin",
  "version": "1.0.0.0",
  "author": "Your Name",
  "website": "https://example.com",
  "documentation": "https://example.com/docs",
  "description": "Plugin description",
  "editor-scripts": ["editor.js"],
  "file-list": [
    "c3runtime/main.js",
    "c3runtime/plugin.js",
    "c3runtime/type.js",
    "c3runtime/instance.js",
    "lang/en-US.json",
    "aces.json",
    "addon.json"
  ]
}
```

### aces.json (ACE Definitions)

```json
{
  "conditions": {
    "is-enabled": {
      "category": "general",
      "forward": "_IsEnabled",
      "autoScriptInterface": true,
      "highlight": false,
      "deprecated": false,
      "params": []
    }
  },
  "actions": {
    "set-enabled": {
      "category": "general",
      "forward": "_SetEnabled",
      "autoScriptInterface": true,
      "highlight": false,
      "deprecated": false,
      "params": [
        {
          "id": "enabled",
          "type": "boolean",
          "initialValue": "true"
        }
      ]
    }
  },
  "expressions": {
    "Speed": {
      "category": "general",
      "forward": "_Speed",
      "autoScriptInterface": true,
      "returnType": "number",
      "params": []
    }
  }
}
```

## Parameter Types

| Type | Description | Example |
|------|-------------|---------|
| `number` | Numeric value | `"initialValue": "0"` |
| `string` | Text string | `"initialValue": "\"\""` |
| `boolean` | True/false | `"initialValue": "true"` |
| `combo` | Dropdown list | `"items": ["option1", "option2"]` |
| `cmp` | Comparison operator | (=, ≠, <, ≤, >, ≥) |
| `object` | Object picker | For object references |
| `objectname` | Object name string | Object type name |
| `layer` | Layer picker | Layer reference |
| `layout` | Layout picker | Layout reference |
| `keyb` | Keyboard key | Key code |
| `instancevar` | Instance variable | Variable picker |
| `eventvar` | Event variable | Variable picker |
| `animation` | Animation name | For Sprite |
| `objinstancevar` | Object's instance variable | Combined picker |

## Runtime Classes

### Plugin (c3runtime/plugin.js)
```javascript
const C3 = globalThis.C3;

C3.Plugins.MyPlugin = class MyPlugin extends C3.SDKPluginBase {
    constructor(opts) {
        super(opts);
    }

    Release() {
        super.Release();
    }
};
```

### Type (c3runtime/type.js)
```javascript
const C3 = globalThis.C3;

C3.Plugins.MyPlugin.Type = class MyPluginType extends C3.SDKTypeBase {
    constructor(objectClass) {
        super(objectClass);
    }

    Release() {
        super.Release();
    }

    OnCreate() {
        // Called when first instance created
    }
};
```

### Instance (c3runtime/instance.js)
```javascript
const C3 = globalThis.C3;

C3.Plugins.MyPlugin.Instance = class MyPluginInstance extends C3.SDKInstanceBase {
    constructor(inst, properties) {
        super(inst);

        // Read properties
        if (properties) {
            this._myProperty = properties[0];
        }
    }

    Release() {
        super.Release();
    }

    // ACE implementations
    _IsEnabled() {
        return this._enabled;
    }

    _SetEnabled(enabled) {
        this._enabled = enabled;
    }

    _Speed() {
        return this._speed;
    }
};
```

### World Instance (for visible objects)
```javascript
C3.Plugins.MyPlugin.Instance = class MyPluginInstance extends C3.SDKWorldInstanceBase {
    constructor(inst, properties) {
        super(inst);
    }

    Draw(renderer) {
        // Custom rendering
    }
};
```

## Behavior Classes

### Behavior (c3runtime/behavior.js)
```javascript
const C3 = globalThis.C3;

C3.Behaviors.MyBehavior = class MyBehavior extends C3.SDKBehaviorBase {
    constructor(opts) {
        super(opts);
    }
};
```

### Behavior Instance (c3runtime/instance.js)
```javascript
C3.Behaviors.MyBehavior.Instance = class MyBehaviorInstance extends C3.SDKBehaviorInstanceBase {
    constructor(behInst, properties) {
        super(behInst);

        this._speed = properties[0];

        // Enable Tick
        this._StartTicking();
    }

    Tick() {
        const dt = this._runtime.GetDt();
        const inst = this._inst;

        inst.SetX(inst.GetX() + this._speed * dt);
    }

    // ACE implementations
    _SetSpeed(speed) {
        this._speed = speed;
    }

    _Speed() {
        return this._speed;
    }
};
```

## Language File (lang/en-US.json)

```json
{
  "languageTag": "en-US",
  "fileDescription": "My Plugin language file",
  "text": {
    "plugins": {
      "myplugin": {
        "name": "My Plugin",
        "description": "Plugin description",
        "help-url": "https://example.com/docs",
        "properties": {
          "my-property": {
            "name": "My Property",
            "desc": "Description of this property"
          }
        },
        "aceCategories": {
          "general": "General"
        },
        "conditions": {
          "is-enabled": {
            "list-name": "Is enabled",
            "display-text": "Is [b]{my}[/b] enabled",
            "description": "Check if enabled"
          }
        },
        "actions": {
          "set-enabled": {
            "list-name": "Set enabled",
            "display-text": "Set [b]{my}[/b] enabled to [i]{0}[/i]",
            "description": "Enable or disable",
            "params": {
              "enabled": {
                "name": "Enabled",
                "desc": "Whether to enable"
              }
            }
          }
        },
        "expressions": {
          "Speed": {
            "description": "Get the current speed",
            "translated-name": "Speed"
          }
        }
      }
    }
  }
}
```

## Quick Lookup

```bash
# Search for ACE definition examples
grep -r "autoScriptInterface" references/addon-sdk/

# Find interface documentation
grep -r "IWorldInstance" references/addon-sdk/reference/

# Search for specific method
grep -r "GetX" references/addon-sdk/
```

## Documentation Index

### Guides
| File | Description |
|------|-------------|
| `guide/defining-aces.md` | ACE definition syntax and types |
| `guide/runtime-scripts.md` | Runtime script development |
| `guide/configuring-plugins.md` | Plugin configuration |
| `guide/configuring-behaviors.md` | Behavior configuration |
| `guide/addon-metadata.md` | addon.json structure |
| `guide/language-file.md` | Localization |
| `guide/typescript-support.md` | TypeScript in addons |
| `guide/editor-scripts.md` | Editor-side scripts |

### Reference
| File | Description |
|------|-------------|
| `reference/iplugininfo.md` | Plugin info interface |
| `reference/ibehaviorinfo.md` | Behavior info interface |
| `reference/pluginproperty.md` | Property definitions |
| `reference/object-interfaces/` | Runtime object interfaces |
| `reference/base-classes/` | SDK base classes |

## Common Patterns

### Enable Tick for per-frame updates
```javascript
constructor(inst, properties) {
    super(inst);
    this._StartTicking();
}

Tick() {
    const dt = this._runtime.GetDt();
    // Update logic
}
```

### Access instance position (World Instance)
```javascript
const x = this._inst.GetX();
const y = this._inst.GetY();
this._inst.SetXY(newX, newY);
```

### Get runtime reference
```javascript
const runtime = this._runtime;
const dt = runtime.GetDt();
const gameTime = runtime.GetGameTime();
```

### Trigger condition
```javascript
// In instance class
this.Trigger(C3.Plugins.MyPlugin.Cnds.OnSomething);
```

### Access other behaviors
```javascript
const inst = this._inst;
const platform = inst.GetBehaviorSdkInstanceFromCtor(C3.Behaviors.Platform);
if (platform) {
    platform.SetSpeed(100);
}
```
