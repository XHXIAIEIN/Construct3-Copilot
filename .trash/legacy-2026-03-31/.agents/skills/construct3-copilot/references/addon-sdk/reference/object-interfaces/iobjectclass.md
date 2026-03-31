---
title: "IObjectClass interface"
source: "https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/iobjectclass"
---

# IObjectClass interface

## On this page

- [Methods](#internalH1Link0)

---

The `IObjectClass` interface is the base class of [IObjectType](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/iobjecttype) and [IFamily](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/ifamily).

`IObjectClass` cannot be created directly. However any parameter that accepts an `IObjectClass` can accept any derivative, i.e. an object type or a family.

## Methods

**GetName()**  
Return the name of the object class.

**GetProject()**  
Return the [IProject](https://www.construct.net/make-games/manuals/addon-sdk/reference/model-interfaces/iproject) representing the object class's associated project.

**Delete()**  
Immediately deletes this object class from the project without any confirmation prompt. All events referencing it will also be removed. This cannot be undone.

> **Warning**  
> Use this with care as it does not warn the user and cannot be undone.
