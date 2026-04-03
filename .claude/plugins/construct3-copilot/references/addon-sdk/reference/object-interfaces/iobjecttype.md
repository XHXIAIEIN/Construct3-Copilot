---
title: "IObjectType interface"
source: "https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/iobjecttype"
---

# IObjectType interface

## On this page

- [Methods](#internalH1Link0)

---

The `IObjectType` interface represents an object type in Construct. It derives from [IObjectClass](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/iobjectclass).

## Methods

**GetImage()**  
Return an [IAnimationFrame](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/ianimationframe) representing the object type's image. The plugin must have specified `SetHasImage(true)` in [IPluginInfo](https://www.construct.net/make-games/manuals/addon-sdk/reference/iplugininfo).

**EditImage()**  
Open the Animations Editor in Construct to edit the object's image. The plugin must have specified `SetHasImage(true)`.

**GetAnimations()**  
Return an array of [IAnimation](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/ianimation) representing the animations in the object type. Note this is only applicable to animated plugin types, e.g. Sprite.

**AddAnimation(animName, frameBlob, frameWidth, frameHeight)**  
Add a new animation to the object type. The object type's plugin must be animated (e.g. the Sprite plugin). Animations must have at least one frame, so this method also adds an animation frame. The *frameBlob*, *frameWidth* and *frameHeight* parameters are all optional: if they are omitted, Construct will add a default empty animation frame. If they are provided they are interpreted the same way as [IAnimation.AddFrame()](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/ianimation); see the linked documentation for more details. The call returns a promise that resolves with the newly created [IAnimation](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/ianimation).

**GetAllInstances()**  
Return an array of all [IObjectInstances](https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/iobjectinstance) or [IWorldInstances](https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/iworldinstance) of this object type in the project. 

> **Tip**  
> The returned instances may be placed on different layouts.

**CreateWorldInstance(layer)**  
Create a new instance from this object type, and add it to the given [ILayer](https://www.construct.net/make-games/manuals/addon-sdk/reference/model-interfaces/ilayer). Returns a new [IWorldInstance](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/iworldinstance) interface representing the new instance. Note this method is only applicable to `"world"` type plugins.

**IsInContainer()**  
Return a boolean indicating if the object type belongs to a container.

**GetContainer()**  
Return the [IContainer](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/icontainer) the object type belongs to if any, else `null`.

**CreateContainer(initialObjectTypes)**  
Create a new container using an array of [IObjectType](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/iobjecttype) for the members of the container. The array must include the IObjectType this call is made on, must contain at least two elements, and the object type must not already be in a container. Returns an [IContainer](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/icontainer) representing the created container.
