# Construct 3 Effects & Shaders Guide

Effects (also called shaders) apply visual transformations to objects and layers. This guide covers built-in effects and how to control them via events.

## Effect Basics

### Where Effects Can Be Applied

| Target | How to Apply |
|--------|--------------|
| Objects | Properties panel → Effects |
| Layers | Layer properties → Effects |
| Layouts | Global effects (via layer) |

### Effect Properties in JSON

Effects cannot be added via clipboard JSON, but their parameters can be modified at runtime via events.

## Built-in Effects Reference

### Color & Brightness

#### Adjust HSL
Adjusts hue, saturation, and lightness.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Hue | -180 to 180 | Color shift in degrees |
| Saturation | -100 to 100 | -100 = grayscale |
| Lightness | -100 to 100 | -100 = black, 100 = white |

**Events JSON** (modify HSL effect):
```json
{"eventType": "block",
 "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "DamageZone"}}],
 "actions": [
   {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"AdjustHSL\"", "index": 2, "value": "50"}}
 ]}
```

#### Tint
Applies a color tint to the object.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Red | 0-255 | Red channel |
| Green | 0-255 | Green channel |
| Blue | 0-255 | Blue channel |

#### Grayscale
Converts to grayscale.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Intensity | 0-100 | 100 = full grayscale |

#### Sepia
Applies sepia tone effect.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Intensity | 0-100 | 100 = full sepia |

#### Invert
Inverts colors.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Intensity | 0-100 | 100 = full invert |

### Blur Effects

#### Blur (Gaussian)
Standard blur effect.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Horizontal blur | 0+ | Pixels to blur horizontally |
| Vertical blur | 0+ | Pixels to blur vertically |

**Events JSON** (blur on pause):
```json
{"eventType": "block",
 "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "comparison": 0, "value": "true"}}],
 "actions": [
   {"id": "set-effect-enabled", "objectClass": "GameLayer", "parameters": {"effect": "\"Blur\"", "state": 1}},
   {"id": "set-effect-parameter", "objectClass": "GameLayer", "parameters": {"effect": "\"Blur\"", "index": 0, "value": "5"}}
 ]}
```

#### Radial Blur
Blur radiating from a center point.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Center X | 0-1 | Normalized center X |
| Center Y | 0-1 | Normalized center Y |
| Intensity | 0+ | Blur amount |
| Quality | 1-10 | Higher = smoother |

#### Motion Blur
Directional blur for movement effect.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Angle | 0-360 | Blur direction |
| Magnitude | 0+ | Blur distance |

### Distortion Effects

#### Warp
Distorts the object with wave effect.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Frequency X | 0+ | Wave frequency horizontal |
| Frequency Y | 0+ | Wave frequency vertical |
| Amplitude X | 0+ | Wave strength horizontal |
| Amplitude Y | 0+ | Wave strength vertical |
| Phase X | 0-360 | Wave offset horizontal |
| Phase Y | 0-360 | Wave offset vertical |

**Events JSON** (animate warp):
```json
{"eventType": "block",
 "conditions": [{"id": "every-tick", "objectClass": "System", "parameters": {}}],
 "actions": [
   {"id": "set-effect-parameter", "objectClass": "WaterSprite", "parameters": {"effect": "\"Warp\"", "index": 4, "value": "(time*100)%360"}}
 ]}
```

#### Bulge
Creates bulge/pinch distortion.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Center X | 0-1 | Normalized center X |
| Center Y | 0-1 | Normalized center Y |
| Radius | 0+ | Effect radius |
| Strength | -1 to 1 | Negative = pinch |

#### Glass
Applies glass-like refraction.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Magnification | 0+ | 1 = normal |
| Displacement | 0-1 | Distortion amount |

### Glow Effects

#### Glow
Adds glow around the object.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Intensity | 0+ | Glow brightness |
| Radius | 0+ | Glow spread |
| Color | RGB | Glow color |

**Events JSON** (pulse glow):
```json
{"eventType": "block",
 "conditions": [{"id": "every-tick", "objectClass": "System", "parameters": {}}],
 "actions": [
   {"id": "set-effect-parameter", "objectClass": "CollectibleGem", "parameters": {"effect": "\"Glow\"", "index": 0, "value": "50 + sin(time*5)*30"}}
 ]}
```

#### Outline
Draws outline around object.

| Parameter | Range | Description |
|-----------|-------|-------------|
| Width | 0+ | Outline thickness |
| Red | 0-255 | Outline color R |
| Green | 0-255 | Outline color G |
| Blue | 0-255 | Outline color B |

### Screen Effects

#### Screen (Multiply, Overlay, etc.)
Blend mode effects for the entire layer.

Common blend modes (set on layer):
- Normal
- Additive
- Multiply
- Screen
- Overlay

## Effect Control via Events

### Enable/Disable Effect

```json
{"id": "set-effect-enabled", "objectClass": "Player", "parameters": {"effect": "\"EffectName\"", "state": 1}}
```

- `state`: 1 = enabled, 0 = disabled

### Set Effect Parameter

```json
{"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"EffectName\"", "index": 0, "value": "50"}}
```

- `index`: Parameter index (0-based)
- `value`: New value (can be expression)

## Common Effect Patterns

### Pattern 1: Damage Flash (Red Tint)

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "group", "disabled": false, "title": "Damage Effects", "description": "Visual feedback on damage", "isActiveOnStart": true, "children": [
    {"eventType": "block",
     "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemy"}}],
     "actions": [
       {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"Tint\"", "index": 0, "value": "255"}},
       {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"Tint\"", "index": 1, "value": "100"}},
       {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"Tint\"", "index": 2, "value": "100"}},
       {"id": "wait", "objectClass": "System", "parameters": {"seconds": "0.2"}},
       {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"Tint\"", "index": 0, "value": "255"}},
       {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"Tint\"", "index": 1, "value": "255"}},
       {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"Tint\"", "index": 2, "value": "255"}}
     ]}
  ]}
]}
```

### Pattern 2: Pause Screen Blur

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "group", "disabled": false, "title": "Pause Visual Effects", "description": "Blur game layer when paused", "isActiveOnStart": true, "children": [
    {"eventType": "block",
     "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "comparison": 0, "value": "true"}}],
     "actions": [
       {"id": "set-effect-enabled", "objectClass": "GameLayer", "parameters": {"effect": "\"Blur\"", "state": 1}},
       {"id": "set-effect-parameter", "objectClass": "GameLayer", "parameters": {"effect": "\"Blur\"", "index": 0, "value": "3"}},
       {"id": "set-effect-parameter", "objectClass": "GameLayer", "parameters": {"effect": "\"Blur\"", "index": 1, "value": "3"}}
     ]},
    {"eventType": "block",
     "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "comparison": 0, "value": "false"}}],
     "actions": [
       {"id": "set-effect-enabled", "objectClass": "GameLayer", "parameters": {"effect": "\"Blur\"", "state": 0}}
     ]}
  ]}
]}
```

### Pattern 3: Power-up Glow

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "group", "disabled": false, "title": "Power-up Effects", "description": "Visual indicator for active power-up", "isActiveOnStart": true, "children": [
    {"eventType": "block",
     "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "HasSpeedBoost", "comparison": 0, "value": "true"}}],
     "actions": [
       {"id": "set-effect-enabled", "objectClass": "Player", "parameters": {"effect": "\"Glow\"", "state": 1}},
       {"id": "set-effect-parameter", "objectClass": "Player", "parameters": {"effect": "\"Glow\"", "index": 0, "value": "80"}}
     ]},
    {"eventType": "block",
     "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "HasSpeedBoost", "comparison": 0, "value": "false"}}],
     "actions": [
       {"id": "set-effect-enabled", "objectClass": "Player", "parameters": {"effect": "\"Glow\"", "state": 0}}
     ]}
  ]}
]}
```

### Pattern 4: Death Grayscale

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "block",
   "conditions": [{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "PlayerHealth", "comparison": 3, "value": "0"}}],
   "actions": [
     {"id": "set-effect-enabled", "objectClass": "GameLayer", "parameters": {"effect": "\"Grayscale\"", "state": 1}},
     {"id": "set-effect-parameter", "objectClass": "GameLayer", "parameters": {"effect": "\"Grayscale\"", "index": 0, "value": "100"}}
   ]}
]}
```

## Performance Considerations

1. **Blur is expensive** - Use sparingly, reduce quality on mobile
2. **Layer effects affect all objects** - More efficient than per-object
3. **Disable unused effects** - Don't just set intensity to 0
4. **Limit animated effects** - Updating every tick is costly

## Effect Parameter Index Reference

Quick reference for common effects:

| Effect | Index 0 | Index 1 | Index 2 |
|--------|---------|---------|---------|
| AdjustHSL | Hue | Saturation | Lightness |
| Tint | Red | Green | Blue |
| Blur | Horiz blur | Vert blur | - |
| Glow | Intensity | Radius | - |
| Grayscale | Intensity | - | - |
| Sepia | Intensity | - | - |
| Outline | Width | Red | Green (3=Blue) |

## Limitations

1. **Cannot add effects via JSON** - Effects must be added in editor
2. **Effect names are case-sensitive** - Use exact names
3. **Custom shaders require GLSL/WGSL** - Beyond clipboard scope
4. **Some effects are WebGL-only** - Check compatibility
