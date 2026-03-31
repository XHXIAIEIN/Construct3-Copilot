# Construct's Project Format

Construct 3 projects are typically saved as single files with the `.c3p` extension, which stands for "Construct 3 Project." These files are standard ZIP archives containing a folder structure with the complete project. Users can rename a `.c3p` file to `.zip` and extract its contents to view all constituent files and folders.

Alternatively, browsers that support it allow saving projects as folders, skipping ZIP compression entirely. This approach benefits:

- Large projects that save faster since only modified files update
- Source control integration (GitHub) requiring folder-based projects for file-level change tracking
- External code editor workflows for JavaScript/TypeScript editing
- AI tools avoiding repeated ZIP decompression/recompression cycles
- Advanced developers creating custom project manipulation tools

Both Construct 3 and Construct Animate share the same project format, allowing compatible projects to open in either product.

**Important caveat:** "The Construct project format does not have any published specification. It is also subject to change over time as Construct is updated."

## The main project file

The file named `project.c3proj` is the main project file. It is in JSON format and acts as an index of all the content in the project. It stores:

- Project metadata (name, viewport size, etc.)
- References to all project content
- Complete listings of layouts, event sheets, object types, families, scripts, timelines, flowcharts, and 3D models
- Folder structure organization matching the Project Bar

The main file references all content; any additional files not referenced are ignored.

## Construct-specific content

### Object types

Object types define available objects (e.g., PlayerSprite) and are stored in the `objectTypes` subfolder in JSON format.

### Families

Families are groups of object types, stored in the `families` subfolder in JSON format.

### Layouts

Layouts consist of layers and arrangements of objects on those layers for purposes like menu and level design, stored in the `layouts` subfolder in JSON format. Layout JSON files comprise metadata and layer trees with object instances in Z-order. Each object instance has a "uid" (Unique ID) for reference; UIDs need only be unique, not sequential.

### Event sheets

Event sheets consist of Construct's visual blocks that it uses as an alternative to traditional programming languages, stored in the `eventSheets` folder in JSON format. Event sheet JSON maintains hierarchical event block structures.

### Timelines

Timelines consist of a sequence of changes over time, such as to control a title screen animation, stored in the `timelines` subfolder in JSON format.

### Flowcharts

Flowcharts consist of a series of connected nodes for purposes like conversation trees and finite state machines, stored in the `flowcharts` subfolder in JSON format.

### 3D models

3D models are stored in the `3dmodels` folder in JSON format. Construct supports importing GLTF (.gltf and .glb) models; these are processed during the import process and the saved JSON files are similar to but not necessarily exactly the same as GLTF files.

### Object images

Images are stored in a dedicated `images` subfolder using PNG format, though original lossy formats (JPG, AVIF) may persist if unedited. File naming follows two schemes (always lowercased):

- Single-image objects: `objectname.png` (e.g., `tiledbackground.png`)
- Animated objects: `objectname-animationname-framenumber.png` with zero-padded frame numbers (e.g., `player-default-000.png`)

Object type JSON files contain metadata and animation frame listings. While JSON includes image dimensions, Construct determines actual sizes from image files themselves to facilitate external editing.

### Serialization IDs

Many resources include "sid" (Serialization ID) values — 15-digit random numbers enabling content merging while minimizing collision risks.

## Additional project files

Scripts, audio, video, fonts, icons, and general files store metadata in `project.c3proj` with actual files in respective subfolders: `scripts`, `sounds`, `music`, `videos`, `fonts`, `icons`, and `files`.

### Format requirements

- **Scripts**: JavaScript (.js) and TypeScript (.ts) supported
- **Audio**: WebM Opus format (.webm) required for sound and music
- **Video**: Supports multiple codecs; H.264 MP4 is universally compatible
- **Fonts**: WOFF format exclusively for browser compatibility
- **Icons/Splash screens**: PNG format required
- **General files**: Any format; Construct doesn't use them directly but makes them available to project logic

## UI state files

Files with `.uistate.json` extensions store editor interface state and have no impact on project operation. They can be safely deleted without affecting functionality; tooling should typically ignore these files.

## LLM context file

Starting from r477, Construct projects saved as folders include a `llm-context.md` file. This file provides a brief explanation of the project format to assist large language models (LLMs) in understanding the project structure. It is not used by Construct itself.
