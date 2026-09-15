# PSSG research repo

This is a very loosely managed research project regarding pssg file format from Atelier Meruru. This research was done on the PC Steam version, but upon inspection of the PSVita files they seem to be mostly the same in structure.

This project is not meant to be a production-ready asset ripping pipeline, it is a simple research project, so don't expect miracles, but feel free to report any issues (or contribute a fix yourself as a PR). 

## Usage
If you are here just for the usage part you can skip the other sections. I used Python 3.13 when developing this program. Python does not care for compatibility between minor versions so I cannot guarantee it will work with any other version. First you need to install the requirements from ``requirements.txt`` file. 

Next, you need to obtain a legitimate copy of [Atelier Meruru \~The Apprentice of Arland\~ DX](https://store.steampowered.com/app/936190/Atelier_Meruru_The_Apprentice_of_Arland_DX/). You can also try this with legitimate copies of PS3, PS4 or PSVita versions, but you have to deal with virtual file systems used on the consoles using some other tools. Once you have obtained the copy of the game, go to your local Steam files (right click the game in your library and click browse local files or something like that) and then go into ``Res\x64\chara``. You will see many files with extensions ``*.PSSG.gz``. You need to unzip them (e.g. using built-in Windows archive manager) to get to the PSSG files.

Once you have the files, you can use the tool.

**View model:**
This will allow you to see the model in a 3D viewer without exporting
```
py pssgparser.py view --model .\samples\PC22B_MODEL.PSSG
```

**View model and motions:**
This will allow you to view the model and related motions in the 3D viewe window without exporting. Do note that some models share motions. The viewer supports this as long as it finds the bone names in the model tree.
```
py pssgparser.py view --model .\samples\PC22B_MODEL.PSSG --motion .\samples\PC22B_MOTION1.PSSG
```

**Export PSSG as XML:**
Sometimes the viewer will not work. Or the parser will not work. Or the displayed model will be bugged or have limbs or parts missing. It is useful to be able to inspect the scene graph. You can export it in a format similar to what EGO engine tools provide.
```
py pssgparser.py pssg --input .\samples\PC22B_MODEL.PSSG --output .\PC22B_MODEL.PSSG.xml
```

**Export PSSG as GLTF2:**
If you want to inspect the model in some other viewer you can use this command.
```
py pssgparser.py gltf --model .\samples\PC22B_MODEL.PSSG --motion .\samples\PC22B_MOTION1.PSSG --output PC22B.glb
```
**Note:** PSSG file format provides morph targets for positions, normals and uvs. While positions and normals are faily standard morph targets, uvs are not. Some GLTF2 readers/viewers will not like this and crash or display an error. You can modify the script if you don't want to export the UVs. Check the class ``PssgGltfBuilder`` for more info.

## Short introduction
PSSG probably stands for *Play Station Scene Graph*, apparently this file format stems from Sony's PhyreEngine, multiple studios picked it up for their own use in their own forks of the engine. The PSSG format itself seems to have been deprecated somewhere during the lifetime of PS3 and PSVita, where newer PhyreEngine versions did not ship with the format support enabled. 

This repository attempts to create an implementation of a PSSG file format parser written in Python.  

## PSSG file format
PSSG files are just container files. They are represented by a hierarchy of elements with attributes. A really good way to describe it is "binary XML". It is not possible to decode the files with no prior knowledge about types of different elements, e.g. it is not possible to know if the body of a given element is a binary blob (like texels or a GPU buffer) or a PSSG subtree, a schema is needed for that.

The file format represents a "generic" scene graph, as with most scene graphs it is a tree of nodes, which have certain properties. Multiple types of nodes can be found in the ``Chara`` files of the Atelier games.

- ``ROOTNODE`` - there is only a single copy of this node, it is the scene root
- ``NODE`` - a regular node, it has no special properties
- ``JOINTNODE`` - this seems to just be a regular transform-only node, but it is pretty much always referenced by some skin if it is a "joint" node
- ``RENDERNODE`` - this node will render some geometry
- ``SKINNODE`` - this node will render some geometry with skinning

Conceptually, the PSSG format is very similar to GLTF2. But it does not have a built-in concept of a "skin" or a "morph". Instead, all kinds of "dynamic" geometry is achieved through "modifier networks". The modifier networks can be very convoluted and they can even be chained together to achieve more complex results (for example, morph modifier can only have 2 or 3 weights, but one can achieve more wieghts by chaining the networks). Modifier networks are a very complex topic and don't have an exact one to one mapping with GLTF2 morphs. 

## Credits
Huge credits to the [Ego Engine Modding project](https://github.com/EgoEngineModding/Ego-Engine-Modding) for implementing (and open-sourcing) their PSSG parser. With certain modifications it was very easy to get their concept to work with Atelier models very nicely.