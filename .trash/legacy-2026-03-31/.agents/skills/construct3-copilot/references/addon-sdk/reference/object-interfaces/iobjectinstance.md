---
title: "IObjectInstance interface"
source: "https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/iobjectinstance"
---

# IObjectInstance interface

## On this page

- [Methods](#internalH1Link0)

---

The `IObjectInstance` interface represents an instance in Construct.

## Methods

**GetProject()**  
Return the [IProject](https://www.construct.net/make-games/manuals/addon-sdk/reference/model-interfaces/iproject) representing the instance's associated project.

**GetObjectType()**  
Return the associated [IObjectType](https://www.construct.net/make-games/manuals/addon-sdk/reference/object-interfaces/iobjecttype) interface for this instance.

**GetUID()**  
Return the UID (unique ID) the editor has assigned to this instance.

**GetPropertyValue(id)**  
Get the value of a plugin property for this instance by its property ID. Color properties return a [SDK.Color](https://www.construct.net/make-games/manuals/addon-sdk/reference/geometry-interfaces/color).

**SetPropertyValue(id, value)**  
Set the value of a plugin property for this instance by its property ID. For color properties a [SDK.Color](https://www.construct.net/make-games/manuals/addon-sdk/reference/geometry-interfaces/color) must be passed as the value.

**GetExternalSdkInstance()**  
Return the custom plugin-specific SDK editor instance class for this object instance, which will be a derivative of [IInstanceBase](https://www.construct.net/en/make-games/manuals/addon-sdk/reference/base-classes/iinstancebase). For example if called for an instance of the addon SDK's *drawingPlugin* sample, this would return the `MyDrawingInstance` class. This method can only be used for installed addons - it will return `null` for any built-in plugins. 

> **Warning**  
> Be careful if taking a dependency on a class provided by another developer. Make sure to only use documented and supported methods. If you use features which are changed or removed by a future addon update, then your addon may crash the editor. Scirra will not provide support for crashes involving third-party addons and we will direct affected users to contact the addon developer.
