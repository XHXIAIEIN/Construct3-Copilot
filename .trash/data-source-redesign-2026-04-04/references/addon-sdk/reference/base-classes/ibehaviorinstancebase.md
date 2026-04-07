---
title: "IBehaviorInstanceBase interface"
source: "https://www.construct.net/en/make-games/manuals/addon-sdk/reference/base-classes/ibehaviorinstancebase"
---

# IBehaviorInstanceBase interface

## On this page

- [Properties](#internalH1Link0)
- [Methods](#internalH1Link1)

---

The `IBehaviorInstanceBase` interface is used as the base class for behavior instances in the SDK.

`IBehaviorInstanceBase` cannot be directly constructed; it should only be used as a base class.

## Properties

**this._sdkBehaviorType**  
Reference to the associated SDK type class.

**this._behaviorInstance**  
Reference to the [IBehaviorInstance](https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/ibehaviorinstance) interface representing this instance in the editor. This allows access to Construct's built-in features for behavior instances.

## Methods

**OnPropertyChanged(id, value)**  
Optional override for when a property with the given ID is changed. The value the property was changed to is also passed.

**GetBehaviorInstance()**  
Return the [IBehaviorInstance](https://www.construct.net/en/make-games/manuals/addon-sdk/reference/object-interfaces/ibehaviorinstance) interface representing this instance in the editor.

**GetSdkBehaviorType()**  
Return the associated SDK type class.

**OnAddedInEditor()**  
Optional override for when the behavior instance has been created due to the user adding a new behavior in the editor.
