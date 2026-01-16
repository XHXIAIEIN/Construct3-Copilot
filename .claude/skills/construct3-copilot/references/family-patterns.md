# Construct 3 Family System Patterns

Families allow you to group object types together and reference them as a single unit in events. This enables code reuse and cleaner event organization.

## Family Basics

### What is a Family?

A Family is a collection of object types that share:
- Common behaviors
- Common instance variables
- Common effects
- Can be referenced together in events

### Creating a Family

Families are created in the Project Bar → Object types → Right-click → Add family.

**Important**: Families cannot be created via clipboard JSON. They must be set up manually in the editor, then referenced in events.

## Common Family Patterns

### Pattern 1: Enemy Family

Group all enemy types into one family to handle collision and damage uniformly.

**Setup**:
1. Create family named `Enemies`
2. Add object types: `Slime`, `Bat`, `Zombie`, etc.
3. Add shared instance variable: `Health` (number)
4. Add shared behavior: `Solid` or custom AI behavior

**Events JSON**:
```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "comment", "text": "=== Enemy Family Events ==="},
  {"eventType": "comment", "text": "All events apply to: Slime, Bat, Zombie (any object in Enemies family)"},

  {"eventType": "block",
   "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Bullet", "parameters": {"object": "Enemies"}}],
   "actions": [
     {"id": "subtract-from-instvar", "objectClass": "Enemies", "parameters": {"instance-variable": "Health", "value": "10"}},
     {"id": "destroy", "objectClass": "Bullet", "parameters": {}}
   ]},

  {"eventType": "block",
   "conditions": [{"id": "compare-instvar", "objectClass": "Enemies", "parameters": {"instance-variable": "Health", "comparison": 3, "value": "0"}}],
   "actions": [
     {"id": "spawn-another-object", "objectClass": "Enemies", "parameters": {"object": "ExplosionParticles", "layer": "0", "image-point": "0"}},
     {"id": "destroy", "objectClass": "Enemies", "parameters": {}}
   ]},

  {"eventType": "block",
   "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemies"}}],
   "actions": [
     {"id": "subtract-from-eventvar", "objectClass": "System", "parameters": {"variable": "PlayerHealth", "value": "1"}},
     {"id": "flash", "objectClass": "Player", "behaviorType": "Flash", "parameters": {"on-time": "0.1", "off-time": "0.1", "duration": "0.5"}}
   ]}
]}
```

### Pattern 2: Collectibles Family

Group all pickup items that the player can collect.

**Setup**:
1. Create family named `Collectibles`
2. Add object types: `Coin`, `Gem`, `Heart`, `Key`
3. Add shared instance variable: `PointValue` (number)

**Events JSON**:
```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "group", "disabled": false, "title": "Collectibles System", "description": "Handle all pickup items uniformly", "isActiveOnStart": true, "children": [
    {"eventType": "block",
     "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Collectibles"}}],
     "actions": [
       {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "Score", "value": "Collectibles.PointValue"}},
       {"id": "play", "objectClass": "Audio", "parameters": {"audio-file": "pickup", "loop": "not-looping", "volume": "0", "tag-optional": "\"\""}},
       {"id": "destroy", "objectClass": "Collectibles", "parameters": {}}
     ]},

    {"eventType": "comment", "text": "Special handling for specific collectible types"},
    {"eventType": "block",
     "conditions": [
       {"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Heart"}}
     ],
     "actions": [
       {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "PlayerHealth", "value": "1"}}
     ]},

    {"eventType": "block",
     "conditions": [
       {"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Key"}}
     ],
     "actions": [
       {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "KeyCount", "value": "1"}}
     ]}
  ]}
]}
```

### Pattern 3: Solid Obstacles Family

Group all objects that act as solid obstacles.

**Setup**:
1. Create family named `Obstacles`
2. Add object types: `Wall`, `Crate`, `Rock`
3. Add shared behavior: `Solid`

**Events JSON**:
```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "comment", "text": "=== Obstacle Interactions ==="},

  {"eventType": "block",
   "conditions": [{"id": "on-collision-with-another-object", "objectClass": "Bullet", "parameters": {"object": "Obstacles"}}],
   "actions": [
     {"id": "destroy", "objectClass": "Bullet", "parameters": {}}
   ]},

  {"eventType": "comment", "text": "Destructible obstacles (Crate only)"},
  {"eventType": "block",
   "conditions": [
     {"id": "on-collision-with-another-object", "objectClass": "Bullet", "parameters": {"object": "Crate"}}
   ],
   "actions": [
     {"id": "subtract-from-instvar", "objectClass": "Crate", "parameters": {"instance-variable": "Health", "value": "1"}}
   ]},

  {"eventType": "block",
   "conditions": [{"id": "compare-instvar", "objectClass": "Crate", "parameters": {"instance-variable": "Health", "comparison": 3, "value": "0"}}],
   "actions": [
     {"id": "spawn-another-object", "objectClass": "Crate", "parameters": {"object": "WoodParticles", "layer": "0", "image-point": "0"}},
     {"id": "destroy", "objectClass": "Crate", "parameters": {}}
   ]}
]}
```

### Pattern 4: UI Elements Family

Group UI elements for batch visibility control.

**Setup**:
1. Create family named `GameUI`
2. Add object types: `ScoreText`, `HealthBar`, `TimerText`, `ComboText`

**Events JSON**:
```json
{"is-c3-clipboard-data": true, "type": "events", "items": [
  {"eventType": "group", "disabled": false, "title": "UI Visibility Control", "description": "Show/hide UI based on game state", "isActiveOnStart": true, "children": [
    {"eventType": "comment", "text": "Hide all game UI when paused"},
    {"eventType": "block",
     "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "comparison": 0, "value": "true"}}],
     "actions": [
       {"id": "set-visible", "objectClass": "GameUI", "parameters": {"visibility": 0}}
     ]},

    {"eventType": "block",
     "conditions": [{"id": "compare-boolean-eventvar", "objectClass": "System", "parameters": {"variable": "IsPaused", "comparison": 0, "value": "false"}}],
     "actions": [
       {"id": "set-visible", "objectClass": "GameUI", "parameters": {"visibility": 1}}
     ]},

    {"eventType": "comment", "text": "Fade out UI on game over"},
    {"eventType": "block",
     "conditions": [{"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "GameState", "comparison": 0, "value": "2"}}],
     "actions": [
       {"id": "tween-one-property", "objectClass": "GameUI", "behaviorType": "Tween", "parameters": {"tags": "\"fade\"", "property": "opacity", "end-value": "0", "time": "1", "ease": "out-sine", "destroy-on-complete": "no", "loop": "no", "ping-pong": "no", "repeat-count": "1"}}
     ]}
  ]}
]}
```

## Family Best Practices

### 1. Naming Conventions

| Family Type | Suggested Names |
|-------------|-----------------|
| Enemies | `Enemies`, `Hostiles`, `Mobs` |
| Collectibles | `Collectibles`, `Pickups`, `Items` |
| Solid objects | `Obstacles`, `Solids`, `Walls` |
| UI elements | `GameUI`, `HUDElements`, `UIText` |
| Projectiles | `Projectiles`, `Bullets`, `Missiles` |

### 2. Shared Variables

Common instance variables to add to families:

```
Enemies:
  - Health (number)
  - Damage (number)
  - Speed (number)
  - PointValue (number)

Collectibles:
  - PointValue (number)
  - Type (string)

Projectiles:
  - Damage (number)
  - Owner (string) - "player" or "enemy"
```

### 3. Shared Behaviors

Common behaviors to add to families:

| Family | Typical Behaviors |
|--------|-------------------|
| Enemies | Solid, LOS, Pathfinding, Bullet |
| Collectibles | Sine (floating), Tween |
| Obstacles | Solid |
| UI | Tween, Anchor |
| Projectiles | Bullet, DestroyOutsideLayout |

## Limitations

1. **Cannot create families via JSON** - Must be set up manually in editor
2. **Cannot add/remove objects from family at runtime** - Family membership is static
3. **Picking applies per-instance** - When family event picks an instance, only that specific instance is affected
4. **No nested families** - Families cannot contain other families

## Family vs Object Type in Events

When to use family name vs specific object type:

```json
// Use FAMILY when behavior applies to ALL members
{"objectClass": "Enemies", ...}

// Use SPECIFIC OBJECT when behavior is unique
{"objectClass": "BossEnemy", ...}
```

## Clipboard JSON Reference

When referencing families in clipboard JSON, use the family name as `objectClass`:

```json
{
  "conditions": [
    {"id": "on-collision-with-another-object", "objectClass": "Player", "parameters": {"object": "Enemies"}}
  ],
  "actions": [
    {"id": "destroy", "objectClass": "Enemies", "parameters": {}}
  ]
}
```

The family name works exactly like an object type name in all ACE references.
