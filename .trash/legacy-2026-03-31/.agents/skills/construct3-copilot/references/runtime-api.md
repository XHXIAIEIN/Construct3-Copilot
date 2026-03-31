# Construct 3 Runtime Scripting API

Reference for JavaScript/TypeScript code in event sheet script blocks.

## Script Block Context

When writing script actions in event sheets, these objects are automatically available:

| Object | Type | Description |
|--------|------|-------------|
| `runtime` | IRuntime | Main runtime API |
| `localVars` | object | Local variables in current scope |
| `eventSheetManager` | object | Event sheet manager |

## IRuntime

Main entry point to the Construct 3 scripting API.

### Properties

```typescript
// Object access
runtime.objects          // IConstructProjectObjects - all object types
runtime.globalVars       // Global variables

// Current state
runtime.layout           // Current layout (ILayout)
runtime.dt               // Delta time (seconds since last tick)
runtime.gameTime         // Total game time in seconds
runtime.timeScale        // Time scale (1.0 = normal)

// Viewport
runtime.viewportWidth    // Viewport width in pixels
runtime.viewportHeight   // Viewport height in pixels

// Input (if objects exist)
runtime.keyboard         // Keyboard object
runtime.mouse            // Mouse object
runtime.touch            // Touch object
```

### Methods

```typescript
// Layout navigation
runtime.goToLayout("LayoutName")
runtime.getLayout("LayoutName")        // Returns ILayout

// Instance management
runtime.getInstanceByUid(uid)          // Returns IInstance or null

// Event functions
runtime.callFunction("FuncName", arg1, arg2)  // Call event sheet function
runtime.setReturnValue(value)                  // Set return value in function

// Signals (async coordination)
runtime.signal("tag")                  // Send signal
await runtime.waitForSignal("tag")     // Wait for signal

// Utility
runtime.random()                       // Random 0-1 (respects Advanced Random)
runtime.invokeDownload(url, filename)  // Trigger download
await runtime.alert("message")         // Show alert
```

### Events

```typescript
runtime.addEventListener("tick", () => {
    // Called every tick
});

runtime.addEventListener("beforeprojectstart", () => {
    // Before first layout starts
});

runtime.addEventListener("keydown", (e) => {
    console.log(e.key);
});
```

**Available events**: `tick`, `beforeprojectstart`, `afterprojectstart`, `keydown`, `keyup`, `mousedown`, `mouseup`, `pointerdown`, `pointerup`, `save`, `load`

## IInstance

Base class for all object instances.

```typescript
const inst = runtime.objects.Player.getFirstInstance();

// Properties
inst.uid                  // Unique ID
inst.runtime              // IRuntime reference
inst.objectType           // Object type reference
inst.dt                   // Instance delta time

// Methods
inst.destroy()            // Destroy this instance
inst.hasTag("enemy")      // Check tag
```

## IWorldInstance

Extends IInstance for objects that appear in layouts (Sprite, Text, etc.).

```typescript
const player = runtime.objects.Player.getFirstInstance();

// Position
player.x = 100;
player.y = 200;
player.setPosition(100, 200);
player.offsetPosition(10, 0);       // Move relative

// Size
player.width = 64;
player.height = 64;
player.setSize(64, 64);

// Rotation
player.angle = Math.PI / 4;         // Radians
player.angleDegrees = 45;           // Degrees

// Appearance
player.isVisible = true;
player.opacity = 0.5;               // 0-1
player.colorRgb = [1, 0, 0];        // RGB tint

// Layer & Z-order
player.layer                        // Current layer
player.zIndex                       // Z index on layer
player.moveToTop();
player.moveToBottom();
player.moveToLayer(layer);
player.zElevation = 100;            // 3D elevation

// Collision
player.isCollisionEnabled = true;
player.containsPoint(x, y);         // Point inside?
player.testOverlap(otherInst);      // Overlapping?
player.getBoundingBox();            // DOMRect
```

## IObjectClass (runtime.objects.*)

Access object types and their instances.

```typescript
const Player = runtime.objects.Player;

// Get instances
Player.getFirstInstance()           // First instance or null
Player.getAllInstances()            // Array of all instances
Player.getPickedInstances()         // Currently picked instances

// Iterate
for (const inst of Player.instances()) {
    inst.x += 10;
}

// Create new instance
const newEnemy = runtime.objects.Enemy.createInstance("Main", 100, 200);
```

## ILayout

Represents a layout in the project.

```typescript
const layout = runtime.layout;

// Properties
layout.name                         // Layout name
layout.width                        // Layout width
layout.height                       // Layout height
layout.scrollX                      // Scroll X position
layout.scrollY                      // Scroll Y position
layout.scale                        // Zoom scale

// Methods
layout.scrollTo(x, y);
layout.getLayer("Main");            // Get layer by name
layout.getAllLayers();              // Array of all layers
```

## ILayer

Represents a layer in a layout.

```typescript
const layer = runtime.layout.getLayer("UI");

// Properties
layer.name                          // Layer name
layer.isVisible                     // Visibility
layer.opacity                       // Layer opacity
layer.parallaxX                     // Parallax X (0 = fixed)
layer.parallaxY                     // Parallax Y

// Coordinate conversion
layer.cssPxToLayer(clientX, clientY)   // Screen to layer coords
layer.layerToCssPx(layerX, layerY)     // Layer to screen coords
```

## IBehaviorInstance

Access behavior instances on objects.

```typescript
const player = runtime.objects.Player.getFirstInstance();

// Access behavior by name
const platform = player.behaviors.Platform;
platform.maxSpeed = 500;
platform.jumpStrength = 800;
platform.simulateControl("jump");

const bullet = enemy.behaviors.Bullet;
bullet.speed = 300;
bullet.angleOfMotion = Math.PI;
```

## Common Patterns

### Move toward position
```javascript
const player = runtime.objects.Player.getFirstInstance();
const target = runtime.objects.Target.getFirstInstance();
const angle = Math.atan2(target.y - player.y, target.x - player.x);
const speed = 200 * runtime.dt;
player.x += Math.cos(angle) * speed;
player.y += Math.sin(angle) * speed;
```

### Distance between instances
```javascript
function distance(a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    return Math.sqrt(dx * dx + dy * dy);
}
```

### Angle between instances
```javascript
function angleTo(from, to) {
    return Math.atan2(to.y - from.y, to.x - from.x);
}
```

### Spawn at position
```javascript
const bullet = runtime.objects.Bullet.createInstance("Main", player.x, player.y);
bullet.angleDegrees = player.angleDegrees;
```

### Check keyboard in script
```javascript
if (runtime.keyboard.isKeyDown("ArrowRight")) {
    player.x += 200 * runtime.dt;
}
```

### Get mouse position on layer
```javascript
const layer = runtime.layout.getLayer("Main");
const [mouseX, mouseY] = layer.cssPxToLayer(runtime.mouse.clientX, runtime.mouse.clientY);
```

## Script Action Examples

### Simple calculation
```json
{
  "type": "script",
  "language": "javascript",
  "script": ["localVars.result = localVars.a + localVars.b;"]
}
```

### Access runtime objects
```json
{
  "type": "script",
  "language": "javascript",
  "script": [
    "const player = runtime.objects.Player.getFirstInstance();",
    "player.x = localVars.targetX;",
    "player.y = localVars.targetY;"
  ]
}
```

### Return value from function
```json
{
  "type": "script",
  "language": "javascript",
  "script": ["runtime.setReturnValue(Math.sqrt(localVars.x * localVars.x + localVars.y * localVars.y));"]
}
```

### Async operation
```json
{
  "type": "script",
  "language": "javascript",
  "script": [
    "await runtime.waitForSignal('ready');",
    "localVars.isReady = true;"
  ]
}
```

---

## Complete Type Definitions

Full TypeScript definitions are available in `source/source/scripts/ts-defs/runtime/`.

### File Index

| File | Interface | Description |
|------|-----------|-------------|
| `IRuntime.d.ts` | IRuntime | Main runtime API entry point |
| `IInstance.d.ts` | IInstance | Base instance class |
| `IWorldInstance.d.ts` | IWorldInstance | Instances with position/size |
| `ILayout.d.ts` | ILayout | Layout management |
| `ILayer.d.ts` | ILayer | Layer properties and methods |
| `IObjectClass.d.ts` | IObjectClass | Object type with instance access |
| `IObjectType.d.ts` | IObjectType | Object type metadata |
| `IBehaviorInstance.d.ts` | IBehaviorInstance | Behavior instance base |
| `IBehaviorType.d.ts` | IBehaviorType | Behavior type metadata |
| `IAnimation.d.ts` | IAnimation | Sprite animation |
| `IAnimationFrame.d.ts` | IAnimationFrame | Animation frame data |
| `IAssetManager.d.ts` | IAssetManager | Asset loading |
| `ICollisionEngine.d.ts` | ICollisionEngine | Collision detection |
| `IEffectInstance.d.ts` | IEffectInstance | Effect/shader instance |
| `IRenderer.d.ts` | IRenderer | Low-level rendering |
| `IStorage.d.ts` | IStorage | Local storage API |
| `IPlatformInfo.d.ts` | IPlatformInfo | Platform detection |
| `ISDKInstanceBase.d.ts` | ISDKInstanceBase | Plugin SDK base |
| `ISDKWorldInstanceBase.d.ts` | ISDKWorldInstanceBase | World plugin SDK base |
| `ISDKBehaviorInstanceBase.d.ts` | ISDKBehaviorInstanceBase | Behavior SDK base |

### Quick Lookup

```bash
# Search for specific API
grep -r "methodName" references/source/source/scripts/ts-defs/runtime/

# Find interface definition
grep -l "IWorldInstance" references/source/source/scripts/ts-defs/runtime/
```

### Project-Specific Types (Auto-generated)

These files in `source/scripts/ts-defs/` are auto-generated by Construct for each project:

| File | Purpose |
|------|---------|
| `objects.d.ts` | Project object types (`runtime.objects.*`) |
| `globalVars.d.ts` | Global variables (`runtime.globalVars.*`) |
| `layers.d.ts` | Layer type extensions |
| `layouts.d.ts` | Layout type extensions |
| `instanceTypes.d.ts` | Instance type namespace |
| `eases.d.ts` | Custom tween eases |
| `localVars.d.ts` | Local variable types |

### Script Templates

**main.ts** - Entry point for project scripts:
```typescript
runOnStartup(async runtime => {
    runtime.addEventListener("beforeprojectstart", () => OnBeforeProjectStart(runtime));
});

async function OnBeforeProjectStart(runtime: IRuntime) {
    runtime.addEventListener("tick", () => Tick(runtime));
}

function Tick(runtime: IRuntime) {
    // Called every tick
}
```

**importsForEvents.ts** - Functions available in event sheet scripts:
```typescript
// Define functions here to use in script blocks
function myHelper(a: number, b: number): number {
    return a + b;
}
// Then call myHelper() in event sheet script actions
```
