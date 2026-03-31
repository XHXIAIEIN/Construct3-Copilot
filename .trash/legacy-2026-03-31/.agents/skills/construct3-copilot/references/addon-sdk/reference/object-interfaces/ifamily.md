---
title: "IFamily interface"
source: "https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/ifamily"
---

# IFamily interface

## On this page

- [Methods](#internalH1Link0)

---

The `IFamily` interface represents a family in Construct, which is a group of object types that can be treated as one. All object types in the family must be from the same plugin. It derives from [IObjectClass](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/iobjectclass). Families can be created in the SDK using [IProject](https://www.construct.net/make-games/manuals/addon-sdk/reference/model-interfaces/iproject).`CreateFamily()`.

## Methods

**GetMembers()**  
Return an array of [IObjectType](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/iobjecttype) representing the object types in the family.

**SetMembers(objectTypes)**  
Set the members of the family by passing an array of [IObjectType](https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/iobjecttype). Note all the specified object types must be compatible with the family, including using the same plugin, and not having any naming conflicts between instance variables, behaviors and effects.
